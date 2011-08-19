#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2011 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2011 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2011 Matteo Boscariol <boscarim@hotmail.com>
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

"""Evaluation server. It takes care of receiving submissions from the
contestants, transforming them in jobs (compilation, execution, ...),
queuing them with the right priority, and dispatching them to the
workers. Also, it collects the results from the workers and build the
current ranking.

"""

import time

import heapq

from cms.async.AsyncLibrary import Service, rpc_method, rpc_callback, logger
from cms.async import ServiceCoord, get_service_shards
import cms.util.Utils as Utils

from cms.db.SQLAlchemyAll import Session, Contest, Submission, SessionGen


class JobQueue:
    """An instance of this class will contains the (unique) priority
    queue of jobs (compilations, evaluations, ...) that the ES needs
    to process next.

    A job is a couple (job_type, submission_id), where job_type is a
    constant defined in EvaluationServer.

    Elements of the queue are of the form (priority, timestamp, job),
    where priority is a constant defined in EvaluationServer.

    """

    def __init__(self):
        self.queue = []

    def push(self, job, priority, timestamp=None):
        """Push a job in the queue. If timestamp is not specified,
        uses the current time.

        job (job): a couple (job_type, submission_id)
        priority (int): the priority of the job
        timestamp (float): the time of the submission

        """
        if timestamp == None:
            timestamp = time.time()
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

        returns (int, float, job): the data corresponding to job
                                   (priority, timestamp, job)
        """
        for i in self.queue:
            if self.queue[i][2] == job:
                return i
        raise LookupError("Job not present in queue")

    def set_priority(self, job, priority):
        """Change the priority of a job inside the queue. Raises an
        exception if the job is not in the queue.

        Used (only?) when the user use a token, to increase the
        priority of the evaluation of its submission.

        job (job): the job whose priority needs to change
        priority (int): the new priority

        """
        pos = self.search(job)
        self.queue[pos][0] = priority
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
            ret.append({'job': repr(ext_job[2]),
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
        """service (Service): the EvaluationServer using this
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

    def add_worker(self, worker_coord):
        """Add a new worker to the worker pool. This is for
        non-foreseen worker that has no line in the configuration
        file, hence we need to specify manually the address.

        worker_coord (ServiceCoord): the coordinates of the worker

        """
        shard = worker_coord.shard
        # Instruct AsyncLibrary to connect ES to the Worker
        self.worker[shard] = self.service.connect_to(worker_coord)
        # And we fill all data.
        self.job[shard] = self.WORKER_INACTIVE
        self.start_time[shard] = None
        self.error_count[shard] = 0
        self.schedule_disabling[shard] = False
        self.side_data[shard] = None
        logger.debug("Worker %d added " % shard)

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
            shard = self.find_worker(self.WORKER_INACTIVE)
        except LookupError:
            return None

        # Then we fill the info for future memory
        self.job[shard] = job
        self.start_time[shard] = time.time()
        self.side_data[shard] = side_data
        logger.debug("Worker %d acquired" % shard)

        # And finally we ask the worker to do the job
        action, submission_id = job
        timestamp = side_data[1]
        queue_time = self.start_time[shard] - timestamp
        logger.info("Asking worker %d to %s submission %s "
                    " (after around %.2f seconds of queue)" %
                    (shard, action, submission_id, queue_time))
        logger.debug("Still %d jobs in the queue" %
                     self.service.queue.length())
        if action == EvaluationServer.JOB_TYPE_COMPILATION:
            self.worker[shard].compile(submission_id=submission_id,
                                       callback=self.service.action_finished.im_func,
                                       plus=(job, side_data, shard))
        elif action == EvaluationServer.JOB_TYPE_EVALUATION:
            self.worker[shard].evaluate(submission_id=submission_id,
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
            logger.error("Trying to release worker "
                         "while it's inactive")
            raise ValueError("Trying to release worker "
                             "while it's inactive")
        self.start_time[shard] = None
        self.side_data[shard] = None
        if self.schedule_disabling[shard]:
            self.job[shard] = self.WORKER_DISABLED
            self.schedule_disabling[shard] = False
            logger.info("Worker %d released and disabled" % shard)
            return True
        else:
            self.job[shard] = self.WORKER_INACTIVE
            logger.debug("Worker %d released" % shard)
            return False

    def find_worker(self, job):
        """Return the (a) worker whose assigned job is job. Remember
        that there is a placeholder job to signal that the worker is
        not doing anything (or disabled).

        job (job): the job we are looking for, or self.WORKER_*
        returns (int): the shard of the worker working on job, or
                       LookupError if nothing has been found.

        """
        for shard, worker_job in self.job.iteritems():
            if worker_job == job:
                return shard
        raise LookupError("No such job")

    def working_workers(self):
        """Returns the number of workers doing an actual work in this
        moment.

        returns (int): that number

        """
        return len([x for x in self.job.values()
                    if x != self.WORKER_INACTIVE and \
                    x != self.WORKER_DISABLED])

    def get_workers_status(self):
        """Returns a dict with info about the current status of all
        workers.

        return (dict): dict of info: current job, address, starting
                       time, number of errors, and additional data
                       specified in the job.

        """
        return dict([(str(shard), {
            'job': repr(self.job[shard]),
            'address': self.worker[shard].remote_service_coord,
            'start_time': self.start_time[shard],
            'error_count': self.error_count[shard],
            'side_data': self.side_data[shard]})
            for shard in self.worker.keys()])

    def check_timeouts(self):
        """Check if some worker is not responding in too much time. If
        this is the case, the worker is scheduled for disabling, and
        we send him a message trying to shut it down.

        """
        now = time.time()
        lost_jobs = []
        for shard in self.worker:
            if self.start_time[shard] != None:
                active_for = now - self.start_time[shard]
                if active_for > EvaluationServer.WORKER_TIMEOUT:
                    # Here shard is a working worker with no sign of
                    # intelligent life for too much time
                    logger.error("Disabling and shutting down "
                                 "worker %d because of no reponse "
                                 "in %.2f seconds" %
                                 (shard, active_for))
                    assert self.worker[shard] != self.WORKER_INACTIVE \
                        and self.worker[shard] != self.WORKER_DISABLED

                    # So we put again its current job in the queue
                    job = self.job[shard]
                    priority, timestamp = self.side_data[shard]
                    lost_jobs.append((priority, timestamp, job))

                    # Also, we are not trusting it, so we are not
                    # assigning him new jobs even if it comes back to
                    # life.
                    self.schedule_disabling[shard] = True
                    self.release_worker(shard)
                    self.worker[shard].shut_down("No response in %.2f "
                                                  "seconds" % active_for)

        return lost_jobs


class EvaluationServer(Service):
    """Evaluation server.

    """

    JOB_PRIORITY_EXTRA_HIGH = 0
    JOB_PRIORITY_HIGH = 1
    JOB_PRIORITY_MEDIUM = 2
    JOB_PRIORITY_LOW = 3
    JOB_PRIORITY_EXTRA_LOW = 4

    JOB_TYPE_COMPILATION = "compile"
    JOB_TYPE_EVALUATION = "evaluate"
    JOB_TYPE_BOMB = "bomb"

    MAX_COMPILATION_TRIES = 3
    MAX_EVALUATION_TRIES = 3

    # Time after which we declare a worker stale
    WORKER_TIMEOUT = 600.0
    # How often we check for stale workers
    WORKER_TIMEOUT_CHECK_TIME = 300.0

    # How often we check if we can assign a job to a worker
    CHECK_DISPATCH_TIME = 2.0

    def __init__(self, shard, contest):
        logger.initialize(ServiceCoord("EvaluationServer", shard))
        Service.__init__(self, shard)

        with SessionGen() as session:
            contest = session.query(Contest).\
                      filter_by(id=contest).first()
            logger.info("Loaded contest %s" % contest.name)
            submission_ids = [x.id for x in contest.get_submissions(session)]

        self.queue = JobQueue()
        self.pool = WorkerPool(self)

        for i in xrange(get_service_shards("Worker")):
            self.pool.add_worker(ServiceCoord("Worker", i))

        self.add_timeout(self.dispatch_jobs, None,
                         EvaluationServer.CHECK_DISPATCH_TIME,
                         immediately=False)
        self.add_timeout(self.check_workers, None,
                         EvaluationServer.WORKER_TIMEOUT_CHECK_TIME,
                         immediately=False)

        # Submit to compilation all the submissions already in DB
        # TODO - Make this configurable
        for submission_id in submission_ids:
            print submission_id
            self.new_submission(submission_id)

        self.dispatch_jobs()

    def dispatch_jobs(self):
        """Check if there are pending jobs, and tries to distribute as
        many of them to the available workers.

        """
        while self.dispatch_one_job():
            pass

        # We want this to run forever:
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
        if res != None:
            self.queue.pop()
            return True
        else:
            return False

    def check_workers(self):
        """We ask WorkerPool for the unresponsive workers, and we put
        their job in the queue again.

        """
        lost_jobs = self.pool.check_timeouts()
        for priority, timestamp, job in lost_jobs:
            self.queue.push(job, priority, timestamp)

    @rpc_callback
    def action_finished(self, data, plus, error=None):
        """Callback from a worker, to signal that is finished some
        action (compilation or evaluation).

        data (bool): report success of the action
        plus (tuple): the tuple (job=(job_type, submission_id),
                                 side_data=(priority, timestamp),
                                 shard_of_worker)

        """
        if error != None:
            logger.error("Received error from Worker: %s" % (error))
            return
        job, side_data, shard = plus
        # We notify the pool that the worker is free, but if the pool
        # wants to disable the worker, it's because it already
        # assigned its job to someone else, so we discard the data
        # from the worker.
        disabled = self.pool.release_worker(shard)
        if disabled:
            return
        job_type, submission_id = job
        priority, timestamp = side_data

        # We get the submission from db.
        with SessionGen() as session:
            submission = Submission.get_from_id(submission_id, session)
            submission_id = submission.id
            compilation_tries = submission.compilation_tries
            compilation_outcome = submission.compilation_outcome
            # These need to be implemented
            evaluation_tries = submission.evaluation_tries
            tokened = submission.tokened()

        if submission is None:
            logger.critical("[action_finished] Couldn't find submission %d "
                            "in the database" % submission_id)
            return

        if data == False:
            # Action was not successful, we requeue if we did not
            # already tried too many times.
            logger.info("Action %s for submission %s completed "
                        "unsuccessfully" % (job_type, submission_id))
            if job_type == EvaluationServer.JOB_TYPE_COMPILATION:
                if compilation_tries > \
                   EvaluationServer.MAX_COMPILATION_TRIES:
                    logger.error("Maximum tries reached for the "
                                 "compilation of submission %s. I will not "
                                 "try again" % submission_id)
                else:
                    self.queue.push(job, priority, timestamp)
            elif job_type == EvaluationServer.JOB_TYPE_EVALUATION:
                if evaluation_tries > \
                   EvaluationServer.MAX_EVALUATION_TRIES:
                    logger.error("Maximum tries reached for the "
                                 "evaluation of submission %s. I will not "
                                 "try again" % submission_id)
                else:
                    self.queue.push(job, priority, timestamp)
            else:
                logger.error("Invalid job type %s" % repr(job_type))
            return

        # The action was successful.
        logger.info("Action %s for submission %s completed "
                    "successfully" % (job_type, submission_id))

        if job_type == EvaluationServer.JOB_TYPE_COMPILATION:
            if compilation_outcome == "ok":
                # Compilation was ok, so we evaluate.
                priority = EvaluationServer.JOB_PRIORITY_LOW
                if tokened:
                    priority = EvaluationServer.JOB_PRIORITY_MEDIUM
                self.queue.push((EvaluationServer.JOB_TYPE_EVALUATION,
                                submission_id), priority, timestamp)
            elif compilation_outcome == "fail":
                # If instead submission failed compilation, we don't
                # evaluate.
                logger.info("Submission %s did not compile. Not going "
                            "to evaluate." % submission_id)
            else:
                logger.error("Compilation outcome %s not recognized." %
                             repr(compilation_outcome))

        elif job_type == EvaluationServer.JOB_TYPE_EVALUATION:
            # Evaluation successful, we update the score
            logger.info("Evaluation succeeded for submission %s" %
                        submission_id)
            scorer = submission.task.scorer
            scorer.add_submission(submission)
            # TODO: uncomment when implemented
            # self.contest.update_ranking_view()

        else:
            logger.error("Invalid job type %s" % repr(job_type))

    @rpc_method
    def new_submission(self, submission_id):
        """This RPC prompts ES of the existence of a new
        submission. ES takes the right countermeasures, i.e., it
        schedules it for compilation.

        submission_id (string): the id of the new submission
        returns (bool): True if everything went well

        """
        with SessionGen() as session:
            submission = Submission.get_from_id(submission_id, session)
            compilation_outcome = submission.compilation_outcome
            tokened = submission.tokened()
            timestamp = submission.timestamp

        if compilation_outcome == None:
            # If not compiled, I compile
            self.queue.push((EvaluationServer.JOB_TYPE_COMPILATION,
                             submission_id),
                            EvaluationServer.JOB_PRIORITY_HIGH,
                            timestamp)
        elif compilation_outcome == "ok":
            # If compiled correctly, I evaluate
            priority = EvaluationServer.JOB_PRIORITY_LOW
            if tokened:
                priority = EvaluationServer.JOB_PRIORITY_MEDIUM
            self.queue.push((EvaluationServer.JOB_TYPE_EVALUATION,
                             submission_id),
                            priority,
                            timestamp)
        elif compilation_outcome == "fail":
            # If compilation was unsuccessful, I do nothing
            pass
        else:
            logger.error("Compilation outcome for submission %s is %s." %
                         (submission_id, str(compilation_outcome)))


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print sys.argv[0], "shard [contest]"
    else:
        EvaluationServer(int(sys.argv[1]),
                         Utils.ask_for_contest(1)).run()
