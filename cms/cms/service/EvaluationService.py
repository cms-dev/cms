#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Evaluation service. It takes care of receiving submissions from the
contestants, transforming them in jobs (compilation, execution, ...),
queuing them with the right priority, and dispatching them to the
workers. Also, it collects the results from the workers and build the
current ranking.

"""

import time
import random

import heapq

from cms import default_argument_parser, logger
from cms.async.AsyncLibrary import Service, rpc_method, rpc_callback
from cms.async import ServiceCoord, get_service_shards
from cms.db import ask_for_contest
from cms.db.SQLAlchemyAll import Contest, Submission, SessionGen


class JobQueue:
    """An instance of this class will contains the (unique) priority
    queue of jobs (compilations, evaluations, ...) that the ES needs
    to process next.

    A job is a couple (job_type, submission_id), where job_type is a
    constant defined in EvaluationService.

    Elements of the queue are of the form (priority, timestamp, job),
    where priority is a constant defined in EvaluationService.

    """

    def __init__(self):
        self.queue = []

    def __contains__(self, job):
        return job in (x[2] for x in self.queue)

    def push(self, job, priority, timestamp=None):
        """Push a job in the queue. If timestamp is not specified,
        uses the current time.

        job (job): a couple (job_type, submission_id)
        priority (int): the priority of the job
        timestamp (int): the time of the submission

        """
        if timestamp is None:
            timestamp = int(time.time())
        heapq.heappush(self.queue, (priority, timestamp, job))

    def top(self):
        """Returns the first element in the queue without extracting
        it. If the queue is empty raises an exception.

        returns (job): first element in the queue

        """
        if len(self.queue) > 0:
            return self.queue[0]
        else:
            raise LookupError("Empty queue")

    def pop(self):
        """Extracts (and returns) the first element in the queue.

        returns (job): first element in the queue
        """
        return heapq.heappop(self.queue)

    def search(self, job):
        """Returns a specific job in the queue, if present. If not,
        raises an exception.

        returns (int, int, job): the data corresponding to job
                                 (priority, timestamp, job)
        """
        for i, element in enumerate(self.queue):
            if element[2] == job:
                return i
        raise LookupError("Job not present in queue")

    def set_priority(self, job, priority):
        """Change the priority of a job inside the queue. Raises an
        exception if the job is not in the queue.

        Used (only?) when the user uses a token, to increase the
        priority of the evaluation of its submission.

        job (job): the job whose priority needs to change.
        priority (int): the new priority.

        """
        pos = self.search(job)
        self.queue[pos] = (priority,
                           self.queue[pos][1],
                           self.queue[pos][2])
        heapq.heapify(self.queue)

    def length(self):
        """Returns the number of elements in the queue.

        returns (int): length of the queue
        """
        return len(self.queue)

    def empty(self):
        """Returns if the queue is empty.

        returns (bool): is the queue empty?
        """
        return self.length() == 0

    def get_status(self):
        """Returns the content of the queue.

        returns (list): a list of dictionary containing the
                        representation of the job, the priority and
                        the timestamp
        """
        myqueue = self.queue[:]
        ret = []
        while myqueue != []:
            ext_job = heapq.heappop(myqueue)
            ret.append({'job': ext_job[2],
                        'priority': ext_job[0],
                        'timestamp': ext_job[1]})
        return ret


class WorkerPool:
    """This class keeps the state of the workers attached to ES, and
    allow the ES to get a usable worker when it needs it.

    """

    WORKER_INACTIVE = None
    WORKER_DISABLED = "disabled"

    def __init__(self, service):
        """service (Service): the EvaluationService using this
        WorkerPool.

        """
        self.service = service
        self.worker = {}
        # These dictionary stores data about the workers (identified
        # by their shard number). Side data is anything one want to
        # attach to the worker. Schedule disabling to True means that
        # we are going to disable the worker as soon as possible (when
        # it finishes the current job). The current job is also
        # discarded because we already re-assigned it.
        self.job = {}
        self.start_time = {}
        self.error_count = {}
        self.side_data = {}
        self.schedule_disabling = {}

    def __contains__(self, job):
        return job in self.job.values()

    def add_worker(self, worker_coord):
        """Add a new worker to the worker pool. This is for
        non-foreseen worker that has no line in the configuration
        file, hence we need to specify manually the address.

        worker_coord (ServiceCoord): the coordinates of the worker.

        """
        shard = worker_coord.shard
        # Instruct AsyncLibrary to connect ES to the Worker
        self.worker[shard] = self.service.connect_to(
            worker_coord,
            on_connect=self.on_worker_connected)

        # And we fill all data.
        self.job[shard] = self.WORKER_INACTIVE
        self.start_time[shard] = None
        self.error_count[shard] = 0
        self.schedule_disabling[shard] = False
        self.side_data[shard] = None
        logger.debug("Worker %s added." % shard)

    def on_worker_connected(self, worker_coord):
        """To be called when a worker comes alive after being
        offline. We use this callback to instruct the worker to
        precache all files concerning the contest.

        worker_coord (ServiceCoord): the coordinates of the worker
                                     that came online.

        """
        shard = worker_coord.shard
        logger.info("Worker %s online again." % shard)
        self.worker[shard].precache_files(contest_id=self.service.contest_id)
        # If we know that the worker was doing some job, we requeue
        # the job.
        if self.job[shard] not in [self.WORKER_DISABLED,
                                   self.WORKER_INACTIVE]:
            job = self.job[shard]
            logger.info("Job %s for submission %s put again in the queue "
                        "because of worker online again." % (job[0], job[1]))
            priority, timestamp = self.side_data[shard]
            self.release_worker(shard)
            self.service.queue.push(job, priority, timestamp)

    def acquire_worker(self, job, side_data=None):
        """Tries to assign a job to an available worker. If no workers
        are available then this returns None, otherwise this returns
        the chosen worker.

        job (job): the job to assign to a worker
        side_data (object): object to attach to the worker for later
                            use

        returns (int): None if no workers are available, the worker
                       assigned to the job otherwise
        """
        # We look for an available worker
        try:
            shard = self.find_worker(self.WORKER_INACTIVE,
                                     require_connection=True,
                                     random_worker=True)
        except LookupError:
            return None

        # Then we fill the info for future memory
        self.job[shard] = job
        self.start_time[shard] = int(time.time())
        self.side_data[shard] = side_data
        logger.debug("Worker %s acquired." % shard)

        # And finally we ask the worker to do the job
        action, submission_id = job
        timestamp = side_data[1]
        queue_time = self.start_time[shard] - timestamp
        logger.info("Asking worker %s to %s submission %s "
                    " (%s seconds after submission)" %
                    (shard, action, submission_id, queue_time))
        logger.debug("Still %s jobs in the queue." %
                     self.service.queue.length())
        if action == EvaluationService.JOB_TYPE_COMPILATION:
            self.worker[shard].compile(
                submission_id=submission_id,
                callback=self.service.action_finished.im_func,
                plus=(job, side_data, shard))
        elif action == EvaluationService.JOB_TYPE_EVALUATION:
            self.worker[shard].evaluate(
                submission_id=submission_id,
                callback=self.service.action_finished.im_func,
                plus=(job, side_data, shard))

        return shard

    def release_worker(self, shard):
        """To be called by ES when it receives a notification that a
        job finished.

        Note: if the worker is scheduled to be disabled, then we
        disable it, and notify the ES to discard the outcome obtained
        by the worker.

        shard (int): the worker to release
        returns (bool): if the worker is going to be disabled

        """
        if self.job[shard] == self.WORKER_INACTIVE or \
                self.job[shard] == self.WORKER_DISABLED:
            err_msg = "Trying to release worker while it's inactive."
            logger.error(err_msg)
            raise ValueError(err_msg)
        self.start_time[shard] = None
        self.side_data[shard] = None
        if self.schedule_disabling[shard]:
            self.job[shard] = self.WORKER_DISABLED
            self.schedule_disabling[shard] = False
            logger.info("Worker %s released and disabled." % shard)
            return True
        else:
            self.job[shard] = self.WORKER_INACTIVE
            logger.debug("Worker %s released." % shard)
            return False

    def find_worker(self, job, require_connection=False, random_worker=False):
        """Return a worker whose assigned job is job. Remember that
        there is a placeholder job to signal that the worker is not
        doing anything (or disabled).

        job (job): the job we are looking for, or self.WORKER_*.
        require_connection (bool): True if we want to find a worker
                                   doing the job and that is actually
                                   connected to us (i.e., did not
                                   die).
        random_worker (bool): if True, choose uniformly amongst all
                       workers doing the job.
        returns (int): the shard of the worker working on job, or
                       LookupError if nothing has been found.

        """
        pool = []
        for shard, worker_job in self.job.iteritems():
            if worker_job == job:
                if not require_connection or self.worker[shard].connected:
                    pool.append(shard)
                    if not random_worker:
                        return shard
        if pool == []:
            raise LookupError("No such job")
        else:
            return random.choice(pool)

    def working_workers(self):
        """Returns the number of workers doing an actual work in this
        moment.

        returns (int): that number

        """
        return len([x for x in self.job.values()
                    if x != self.WORKER_INACTIVE and \
                    x != self.WORKER_DISABLED])

    def get_status(self):
        """Returns a dict with info about the current status of all
        workers.

        return (dict): dict of info: current job, starting time,
                       number of errors, and additional data specified
                       in the job.

        """
        return dict([(str(shard), {
            'connected': self.worker[shard].connected,
            'job': self.job[shard],
            'start_time': self.start_time[shard],
            'error_count': self.error_count[shard],
            'side_data': self.side_data[shard]})
            for shard in self.worker.keys()])

    def check_timeouts(self):
        """Check if some worker is not responding in too much time. If
        this is the case, the worker is scheduled for disabling, and
        we send him a message trying to shut it down.

        return (list): list of tuples (priority, timestamp, job) of
                       jobs assigned to worker that timeout.

        """
        now = int(time.time())
        lost_jobs = []
        for shard in self.worker:
            if self.start_time[shard] is not None:
                active_for = now - self.start_time[shard]

                if active_for > EvaluationService.WORKER_TIMEOUT:
                    # Here shard is a working worker with no sign of
                    # intelligent life for too much time.
                    logger.error("Disabling and shutting down "
                                 "worker %d because of no reponse "
                                 "in %.2f seconds." %
                                 (shard, active_for))
                    assert self.job[shard] != self.WORKER_INACTIVE \
                        and self.job[shard] != self.WORKER_DISABLED

                    # So we put again its current job in the queue.
                    job = self.job[shard]
                    priority, timestamp = self.side_data[shard]
                    lost_jobs.append((priority, timestamp, job))

                    # Also, we are not trusting it, so we are not
                    # assigning him new jobs even if it comes back to
                    # life.
                    self.schedule_disabling[shard] = True
                    self.release_worker(shard)
                    self.worker[shard].quit("No response in %.2f "
                                            "seconds" % active_for)

        return lost_jobs

    def check_connections(self):
        """Check if a worker we assigned a job to disconnects. In this
        case, requeue the job.

        return (list): list of tuples (priority, timestamp, job) of
                       jobs assigned to worker that disconnected.

        """
        lost_jobs = []
        for shard in self.worker:
            if not self.worker[shard].connected and \
                   self.job[shard] not in [self.WORKER_DISABLED,
                                           self.WORKER_INACTIVE]:
                job = self.job[shard]
                priority, timestamp = self.side_data[shard]
                lost_jobs.append((priority, timestamp, job))
                self.release_worker(shard)

        return lost_jobs


class EvaluationService(Service):
    """Evaluation service.

    """

    JOB_PRIORITY_EXTRA_HIGH = 0
    JOB_PRIORITY_HIGH = 1
    JOB_PRIORITY_MEDIUM = 2
    JOB_PRIORITY_LOW = 3
    JOB_PRIORITY_EXTRA_LOW = 4

    JOB_TYPE_COMPILATION = "compile"
    JOB_TYPE_EVALUATION = "evaluate"

    MAX_COMPILATION_TRIES = 3
    MAX_EVALUATION_TRIES = 3

    # Seconds after which we declare a worker stale.
    WORKER_TIMEOUT = 600.0
    # How often we check for stale workers.
    WORKER_TIMEOUT_CHECK_TIME = 300.0

    # How often we check if a worker is connected.
    WORKER_CONNECTION_CHECK_TIME = 10.0

    # How often we check if we can assign a job to a worker.
    CHECK_DISPATCH_TIME = 2.0

    # How often we look for submission not compiled/evaluated.
    JOBS_NOT_DONE_CHECK_TIME = 117.0

    def __init__(self, shard, contest_id):
        logger.initialize(ServiceCoord("EvaluationService", shard))
        Service.__init__(self, shard, custom_logger=logger)

        self.contest_id = contest_id

        self.queue = JobQueue()
        self.pool = WorkerPool(self)
        self.scoring_service = self.connect_to(
            ServiceCoord("ScoringService", 0))

        # If for some reason (ES switched off for a while, or broken
        # connection with CWS), submissions have been left with some
        # jobs to do, this is the list where you want to pur their
        # ids. Note that list != [] if and only if there is an alive
        # timeout for the method "check_old_submission".
        self.submission_ids_to_check = []

        for i in xrange(get_service_shards("Worker")):
            worker = ServiceCoord("Worker", i)
            self.pool.add_worker(worker)

        self.add_timeout(self.dispatch_jobs, None,
                         EvaluationService.CHECK_DISPATCH_TIME,
                         immediately=True)
        self.add_timeout(self.check_workers_timeout, None,
                         EvaluationService.WORKER_TIMEOUT_CHECK_TIME,
                         immediately=False)
        self.add_timeout(self.check_workers_connection, None,
                         EvaluationService.WORKER_CONNECTION_CHECK_TIME,
                         immediately=False)
        self.add_timeout(self.search_jobs_not_done, None,
                         EvaluationService.JOBS_NOT_DONE_CHECK_TIME,
                         immediately=True)

    def search_jobs_not_done(self):
        """Look in the database for submissions that have not been
        compiled or evaluated for no good reasons. Put the missing job
        in the queue.

        """
        with SessionGen(commit=False) as session:
            contest = session.query(Contest).\
                      filter_by(id=self.contest_id).first()

            # Only adding submission not compiled/evaluated that have
            # not yet reached the limit of tries.
            new_submission_ids_to_check = \
                [x.id for x in contest.get_submissions()
                 if (not x.compiled() and x.compilation_tries <
                     EvaluationService.MAX_COMPILATION_TRIES)
                    or (x.compilation_outcome == "ok" and
                        not x.evaluated() and x.evaluation_tries <
                        EvaluationService.MAX_EVALUATION_TRIES)]

        new = len(new_submission_ids_to_check)
        old = len(self.submission_ids_to_check)
        logger.info("Submissions found with jobs to do: %s." % new)
        if new > 0:
            self.submission_ids_to_check += new_submission_ids_to_check
            if old == 0:
                self.add_timeout(self.check_old_submissions, None,
                                 0.01, immediately=True)

        # Run forever.
        return True

    def check_old_submissions(self):
        """The submissions in the submission_ids_to_check list are to
        compile or evaluate, and this method starts one of this
        operation at a time. This method keeps getting called while
        the list is non-empty.

        Note: doing this way (instead of putting everything in the
        __init__ (prevent freezing the service at the beginning in
        case of many old submissions.

        """
        if self.submission_ids_to_check == []:
            logger.info("Finished loading old submissions.")
            return False
        else:
            self.new_submission(self.submission_ids_to_check[0])
            self.submission_ids_to_check = self.submission_ids_to_check[1:]
            return True

    def dispatch_jobs(self):
        """Check if there are pending jobs, and tries to distribute as
        many of them to the available workers.

        """
        pending = self.queue.length()
        if pending > 0:
            logger.info("%s jobs still pending." % pending)
        while self.dispatch_one_job():
            pass

        # We want this to run forever.
        return True

    def dispatch_one_job(self):
        """Try to dispatch exactly one job, if it exists, to one
        available worker, if it exists.

        return (bool): True if successfully dispatched, False if some
                       resource was missing.

        """
        try:
            priority, timestamp, job = self.queue.top()
        except LookupError:
            return False

        res = self.pool.acquire_worker(job, side_data=(priority, timestamp))
        if res is not None:
            self.queue.pop()
            return True
        else:
            return False

    @rpc_method
    def submissions_status(self):
        """Returns a dictionary of statistics about the number of
        submissions on a specific status. There are seven statuses:
        evaluated, compilation failed, evaluating, compiling, maximum
        number of attempts of compilations reached, the same for
        evaluations, and finally 'I have no idea what's
        happening'. The last three should not happen and require a
        check from the admin.

        return (dict): statistics on the submissions.

        """
        stats = {
            "scored": 0,
            "evaluated": 0,
            "compilation_fail": 0,
            "compiling": 0,
            "evaluating": 0,
            "max_compilations": 0,
            "max_evaluations": 0,
            "invalid": 0}
        with SessionGen(commit=False) as session:
            contest = session.query(Contest).\
                      filter_by(id=self.contest_id).first()
            for user in contest.users:
                for submission in user.submissions:
                    if submission.compilation_outcome == "fail":
                        stats["compilation_fail"] += 1
                    elif submission.compilation_outcome is None:
                        if submission.compilation_tries >= \
                               EvaluationService.MAX_COMPILATION_TRIES:
                            stats["max_compilations"] += 1
                        else:
                            stats["compiling"] += 1
                    elif submission.compilation_outcome == "ok":
                        if submission.evaluated():
                            if submission.scored():
                                stats["scored"] += 1
                            else:
                                stats["evaluated"] += 1
                        else:
                            if submission.evaluation_tries >= \
                                   EvaluationService.MAX_EVALUATION_TRIES:
                                stats["max_evaluations"] += 1
                            else:
                                stats["evaluating"] += 1
                    else:
                        # Should not happen
                        stats["invalid"] += 1
        return stats

    @rpc_method
    def queue_status(self):
        """Returns a list whose elements are the jobs currently in the
        queue (see Queue.get_status).

        returns (list): the list with the queued elements.

        """
        return self.queue.get_status()

    @rpc_method
    def workers_status(self):
        """Returns a dictionary (indexed by shard number) whose values
        are the information about the corresponding worker. See
        WorkerPool.get_status for more details.

        returns (dict): the dict with the workers information.

        """
        return self.pool.get_status()

    def check_workers_timeout(self):
        """We ask WorkerPool for the unresponsive workers, and we put
        again their jobs in the queue.

        """
        lost_jobs = self.pool.check_timeouts()
        for priority, timestamp, job in lost_jobs:
            logger.info("Job %s for submission %s put again in the queue "
                        "because of timeout worker." % (job[0], job[1]))
            self.push_in_queue(job, priority, timestamp)
        return True

    def check_workers_connection(self):
        """We ask WorkerPool for the unconnected workers, and we put
        again their jobs in the queue.

        """
        lost_jobs = self.pool.check_connections()
        for priority, timestamp, job in lost_jobs:
            logger.info("Job %s for submission %s put again in the queue "
                        "because of disconnected worker." % (job[0], job[1]))
            self.push_in_queue(job, priority, timestamp)
        return True

    def push_in_queue(self, job, priority, timestamp):
        """Push a job in the job queue if the job is not already in
        the queue or assigned to a worker.

        job (job): a couple (job_type, submission_id) to push.

        return (bool): True if pushed, False if not.

        """
        if job in self.queue or job in self.pool:
            return False
        else:
            self.queue.push(job, priority, timestamp)
            return True

    @rpc_callback
    def action_finished(self, data, plus, error=None):
        """Callback from a worker, to signal that is finished some
        action (compilation or evaluation).

        data (bool): report success of the action
        plus (tuple): the tuple (job=(job_type, submission_id),
                                 side_data=(priority, timestamp),
                                 shard_of_worker)

        """
        # We notify the pool that the worker is free (even if it
        # replied with ane error), but if the pool wants to disable the
        # worker, it's because it already assigned its job to someone
        # else, so we discard the data from the worker.
        job, side_data, shard = plus
        disabled = self.pool.release_worker(shard)
        if disabled:
            return

        if error is not None:
            logger.error("Received error from Worker: `%s'." % error)
            return

        job_type, submission_id = job
        priority, timestamp = side_data

        logger.info("Action %s for submission %s completed. "
                    "Success: %s" % (job_type, submission_id, data))

        # We get the submission from db.
        with SessionGen(commit=False) as session:
            submission = Submission.get_from_id(submission_id, session)
            if submission is None:
                logger.critical("[action_finished] Couldn't find submission "
                                "%s in the database." % submission_id)
                return

            if job_type == EvaluationService.JOB_TYPE_COMPILATION:
                submission.compilation_tries += 1
            if job_type == EvaluationService.JOB_TYPE_EVALUATION:
                submission.evaluation_tries += 1
            compilation_tries = submission.compilation_tries
            compilation_outcome = submission.compilation_outcome
            evaluation_tries = submission.evaluation_tries
            tokened = submission.tokened()
            evaluated = submission.evaluated()
            session.commit()

        # Compilation
        if job_type == EvaluationService.JOB_TYPE_COMPILATION:
            self.compilation_ended(submission_id,
                                   timestamp,
                                   compilation_tries,
                                   compilation_outcome,
                                   tokened)

        # Evaluation
        elif job_type == EvaluationService.JOB_TYPE_EVALUATION:
            self.evaluation_ended(submission_id,
                                  timestamp,
                                  evaluation_tries,
                                  evaluated,
                                  tokened)

        # Other (i.e. error)
        else:
            logger.error("Invalid job type %r." % job_type)
            return

    def compilation_ended(self, submission_id,
                          timestamp, compilation_tries,
                          compilation_outcome, tokened):
        """Actions to be performed when we have a submission that has
        ended compilation . In particular: we queue evaluation if
        compilation was ok; we requeue compilation if we fail.

        submission_id (string): db id of the submission.
        timestamp (int): time of submission.
        compilation_tries (int): # of tentative compilations.
        compilation_outcome (string): if submission compiled ok.
        tokened (bool): if the user played a token on submission.

        """
        # Compilation was ok, so we evaluate.
        if compilation_outcome == "ok":
            priority = EvaluationService.JOB_PRIORITY_LOW
            if tokened:
                priority = EvaluationService.JOB_PRIORITY_MEDIUM
            self.push_in_queue((EvaluationService.JOB_TYPE_EVALUATION,
                                submission_id), priority, timestamp)
        # If instead submission failed compilation, we don't evaluate.
        elif compilation_outcome == "fail":
            logger.info("Submission %s did not compile. Not going "
                        "to evaluate." % submission_id)
        # If compilation failed for our fault, we requeue or not.
        elif compilation_outcome is None:
            if compilation_tries > EvaluationService.MAX_COMPILATION_TRIES:
                logger.error("Maximum tries reached for the "
                             "compilation of submission %s. I will "
                             "not try again." % submission_id)
            else:
                # Note: lower priority (MEDIUM instead of HIGH) for
                # compilation that are probably failing again.
                self.push_in_queue((EvaluationService.JOB_TYPE_COMPILATION,
                                    submission_id),
                                   EvaluationService.JOB_PRIORITY_MEDIUM,
                                   timestamp)
        # Otherwise, error.
        else:
            logger.error("Compilation outcome %r not recognized." %
                         compilation_outcome)

    def evaluation_ended(self, submission_id,
                         timestamp, evaluation_tries,
                         evaluated, tokened):
        """Actions to be performed when we have a submission that has
        been evaluated. In particular: we inform ScoringService on
        success, we requeue on failure.

        submission_id (string): db id of the submission.
        timestamp (int): time of submission.
        compilation_tries (int): # of tentative evaluations.
        evaluated (bool): if the submission has been evaluated
                          successfully.
        tokened (bool): if the user played a token on submission.

        """
        # Evaluation successful, we inform ScoringService so it can
        # update the score.
        if evaluated:
            self.scoring_service.new_evaluation(submission_id=submission_id)
        # Evaluation unsuccessful, we requeue (or not).
        elif evaluation_tries <= EvaluationService.MAX_EVALUATION_TRIES:
            priority = EvaluationService.JOB_PRIORITY_LOW
            if tokened:
                priority = EvaluationService.JOB_PRIORITY_MEDIUM
            self.push_in_queue((EvaluationService.JOB_TYPE_EVALUATION,
                                submission_id), priority, timestamp)
        else:
            logger.error("Maximum tries reached for the "
                         "evaluation of submission %s. I will "
                         "not try again." % submission_id)

    @rpc_method
    def new_submission(self, submission_id):
        """This RPC prompts ES of the existence of a new
        submission. ES takes the right countermeasures, i.e., it
        schedules it for compilation.

        submission_id (string): the id of the new submission
        returns (bool): True if everything went well

        """
        with SessionGen(commit=False) as session:
            submission = Submission.get_from_id(submission_id, session)
            timestamp = submission.timestamp
            compilation_tries = submission.compilation_tries
            compilation_outcome = submission.compilation_outcome
            evaluation_tries = submission.evaluation_tries
            compiled = submission.compiled()
            evaluated = submission.evaluated()
            tokened = submission.tokened()

        if not compiled:
            # If not compiled, I compile. Note that we give here a
            # chance for submissions that already have too many
            # compilation tries.
            self.push_in_queue((EvaluationService.JOB_TYPE_COMPILATION,
                                submission_id),
                               EvaluationService.JOB_PRIORITY_HIGH,
                               timestamp)
        else:
            if not evaluated:
                self.compilation_ended(submission_id,
                                       timestamp,
                                       compilation_tries,
                                       compilation_outcome,
                                       tokened)

            else:
                self.evaluation_ended(submission_id,
                                      timestamp,
                                      evaluation_tries,
                                      evaluated,
                                      tokened)

    @rpc_method
    def submission_tokened(self, submission_id):
        """This RPC inform EvaluationService that the user has played
        the token on a submission.

        submission_id (int): the id of the submission that changed.

        """
        try:
            self.queue.set_priority((EvaluationService.JOB_TYPE_EVALUATION,
                                     submission_id),
                                    EvaluationService.JOB_PRIORITY_MEDIUM)
            logger.info("Increased priority of evaluation of submission "
                        "%s due to token." % submission_id)
        except LookupError:
            # The job is not in the queue, hence we already done it.
            pass


def main():
    """Parse arguments and launch service.

    """
    default_argument_parser("Submission's compiler and evaluator for CMS.",
                            EvaluationService,
                            ask_contest=ask_for_contest).run()


if __name__ == "__main__":
    main()
