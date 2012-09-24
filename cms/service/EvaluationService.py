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

from datetime import timedelta
import random

from cms import default_argument_parser, logger
from cms.async.AsyncLibrary import Service, rpc_method, rpc_callback
from cms.async import ServiceCoord, get_service_shards
from cms.db import ask_for_contest
from cms.db.SQLAlchemyAll import Contest, Evaluation, \
     Submission, SessionGen, UserTest, UserTestExecutable
from cms.service import get_submissions
from cmscommon.DateTime import make_datetime, make_timestamp
from cms.grading.Job import Job, CompilationJob, EvaluationJob


def to_compile(submission):
    """Return whether ES is interested in compiling the submission.

    submission (Submission): a submission.

    return (bool): True if ES wants to compile the submission.

    """
    return not submission.compiled() and \
        submission.compilation_tries < EvaluationService.MAX_COMPILATION_TRIES


def to_evaluate(submission):
    """Return whether ES is interested in evaluating the submission.

    submission (Submission): a submission.

    return (bool): True if ES wants to evaluate the submission.

    """
    return submission.compilation_outcome == "ok" and \
        not submission.evaluated() and \
        submission.evaluation_tries < EvaluationService.MAX_EVALUATION_TRIES


def user_test_to_compile(user_test):
    """Return whether ES is interested in compiling the user test.

    user_test (UserTest): a user test.

    return (bool): True if ES wants to compile the user test.

    """
    return not user_test.compiled() and \
        user_test.compilation_tries < EvaluationService. \
        MAX_TEST_COMPILATION_TRIES


def user_test_to_evaluate(user_test):
    """Return whether ES is interested in evaluating the user test.

    user_test (UserTest): a user test.

    return (bool): True if ES wants to evaluate the user test.

    """
    return user_test.compilation_outcome == "ok" and \
        not user_test.evaluated() and \
        user_test.evaluation_tries < EvaluationService. \
        MAX_TEST_EVALUATION_TRIES


class JobQueue:
    """An instance of this class will contains the (unique) priority
    queue of jobs (compilations, evaluations, ...) that the ES needs
    to process next.

    A job is a pair (job_type, submission_id), where job_type is a
    constant defined in EvaluationService.

    The queue is implemented as a custom min-heap.

    """

    def __init__(self):
        # The queue: a min-heap whose elements are of the form
        # (priority, timestamp, job), where job is the actual data.
        self._queue = []

        # Reverse lookup for the jobs in the queue: a dictionary
        # associating the index in the queue to each job.
        self._reverse = {}

    def __contains__(self, job):
        """Implement the 'in' operator for a job in the queue.

        job (job): a job to search.

        return (bool): True if job is in the queue.

        """
        return job in self._reverse

    def _swap(self, idx1, idx2):
        """Swap two elements in the queue, keeping their reverse
        indices up to date.

        idx1 (int): the index of the first element.
        idx2 (int): the index of the second element.

        """
        self._queue[idx1], self._queue[idx2] = \
                           self._queue[idx2], self._queue[idx1]
        self._reverse[self._queue[idx1][2]] = idx1
        self._reverse[self._queue[idx2][2]] = idx2

    def _up_heap(self, idx):
        """Take the element in position idx up in the heap until its
        position is the right one.

        idx (int): the index of the element to lift.

        return (int): the new index of the element.

        """
        while idx > 0:
            parent = (idx - 1) // 2
            if self._queue[parent] > self._queue[idx]:
                self._swap(parent, idx)
                idx = parent
            else:
                break
        return idx

    def _down_heap(self, idx):
        """Take the element in position idx down in the heap until its
        position is the right one.

        idx (int): the index of the element to lower.

        return (int): the new index of the element.

        """
        last = len(self._queue) - 1
        while 2 * idx + 1 <= last:
            child = 2 * idx + 1
            if 2 * idx + 2 <= last and \
                   self._queue[2 * idx + 2] < self._queue[child]:
                child = 2 * idx + 2
            if self._queue[child] < self._queue[idx]:
                self._swap(child, idx)
                idx = child
            else:
                break
        return idx

    def _updown_heap(self, idx):
        """Perform both operations of up_heap and down_heap on an
        element.

        idx (int): the index of the element to lift.

        return (int): the new index of the element.

        """
        idx = self._up_heap(idx)
        return self._down_heap(idx)

    def push(self, job, priority, timestamp=None):
        """Push a job in the queue. If timestamp is not specified,
        uses the current time.

        job (job): a couple (job_type, submission_id)
        priority (int): the priority of the job
        timestamp (int): the time of the submission

        """
        if timestamp is None:
            timestamp = make_datetime()
        self._queue.append((priority, timestamp, job))
        last = len(self._queue) - 1
        self._reverse[job] = last
        self._up_heap(last)

    def top(self):
        """Returns the first element in the queue without extracting
        it. If the queue is empty raises an exception.

        returns (job): first element in the queue

        raise: LookupError on empty queue.

        """
        if len(self._queue) > 0:
            return self._queue[0]
        else:
            raise LookupError("Empty queue.")

    def pop(self):
        """Extracts (and returns) the first element in the queue.

        returns (job): first element in the queue

        raise: LookupError on empty queue.

        """
        top = self.top()
        last = len(self._queue) - 1
        self._swap(0, last)

        del self._reverse[top[2]]
        del self._queue[last]
        if last > 0:
            self._down_heap(0)
        return top

    def remove(self, job):
        """Remove a job from the queue. Raise a KeyError if not present.

        job (job): the job to remove

        return (int, int, job): priority, timestamp, and job.

        raise: KeyError if job not present.

        """
        pos = self._reverse[job]
        last = len(self._queue) - 1
        self._swap(pos, last)

        del self._reverse[job]
        del self._queue[last]
        if pos != last:
            self._updown_heap(pos)

    def set_priority(self, job, priority):
        """Change the priority of a job inside the queue. Raises an
        exception if the job is not in the queue.

        job (job): the job whose priority needs to change.
        priority (int): the new priority.

        raise: LookupError if job not present.

        """
        pos = self._reverse[job]
        self._queue[pos] = (priority,
                            self._queue[pos][1],
                            self._queue[pos][2])
        self._updown_heap(pos)

    def length(self):
        """Returns the number of elements in the queue.

        returns (int): length of the queue
        """
        return len(self._queue)

    def empty(self):
        """Returns if the queue is empty.

        returns (bool): is the queue empty?
        """
        return self.length() == 0

    def get_status(self):
        """Returns the content of the queue. Note that the order may
        be not correct, but the first element is the one at the top.

        returns (list): a list of dictionary containing the
                        representation of the job, the priority and
                        the timestamp.
        """
        ret = []
        for data in self._queue:
            ret.append({'job': data[2],
                        'priority': data[0],
                        'timestamp': make_timestamp(data[1])})
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
        self._service = service
        self._worker = {}
        # These dictionary stores data about the workers (identified
        # by their shard number). Side data is anything one want to
        # attach to the worker. Schedule disabling to True means that
        # we are going to disable the worker as soon as possible (when
        # it finishes the current job). The current job is also
        # discarded because we already re-assigned it. Ignore is true
        # if the next result coming from the worker should be
        # discarded.
        self._job = {}
        self._start_time = {}
        self._side_data = {}
        self._schedule_disabling = {}
        self._ignore = {}

    def __contains__(self, job):
        for shard in self._worker:
            if job == self._job[shard] and not self._ignore[shard]:
                return True
        return False

    def add_worker(self, worker_coord):
        """Add a new worker to the worker pool.

        worker_coord (ServiceCoord): the coordinates of the worker.

        """
        shard = worker_coord.shard
        # Instruct AsyncLibrary to connect ES to the Worker.
        self._worker[shard] = self._service.connect_to(
            worker_coord,
            on_connect=self.on_worker_connected)

        # And we fill all data.
        self._job[shard] = WorkerPool.WORKER_INACTIVE
        self._start_time[shard] = None
        self._side_data[shard] = None
        self._schedule_disabling[shard] = False
        self._ignore[shard] = False
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
        self._worker[shard].precache_files(contest_id=self._service.contest_id)
        # We don't requeue the job, because a connection lost does not
        # invalidate a potential result given by the worker (as the
        # problem was the connection and not the machine on which the
        # worker is).

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
            shard = self.find_worker(WorkerPool.WORKER_INACTIVE,
                                     require_connection=True,
                                     random_worker=True)
        except LookupError:
            return None

        # Then we fill the info for future memory
        self._job[shard] = job
        self._start_time[shard] = make_datetime()
        self._side_data[shard] = side_data
        logger.debug("Worker %s acquired." % shard)

        # And finally we ask the worker to do the job
        action, object_id = job
        timestamp = side_data[1]
        queue_time = self._start_time[shard] - timestamp
        logger.info("Asking worker %s to %s submission/user test %d "
                    " (%s after submission)." %
                    (shard, action, object_id, queue_time))

        with SessionGen(commit=False) as session:
            if action == EvaluationService.JOB_TYPE_COMPILATION:
                submission = Submission.get_from_id(object_id,
                                                    session)
                job_ = CompilationJob.from_submission(submission)
            elif action == EvaluationService.JOB_TYPE_EVALUATION:
                submission = Submission.get_from_id(object_id,
                                                    session)
                job_ = EvaluationJob.from_submission(submission)
            elif action == EvaluationService.JOB_TYPE_TEST_COMPILATION:
                user_test = UserTest.get_from_id(object_id,
                                                 session)
                job_ = CompilationJob.from_user_test(user_test)
            elif action == EvaluationService.JOB_TYPE_TEST_EVALUATION:
                user_test = UserTest.get_from_id(object_id,
                                                 session)
                job_ = EvaluationJob.from_user_test(user_test)
                job_.get_output = True
                job_.only_execution = True

            self._worker[shard].execute_job(
                job_dict=job_.export_to_dict(),
                callback=self._service.action_finished.im_func,
                plus=(action, object_id, side_data, shard))

        return shard

    def release_worker(self, shard):
        """To be called by ES when it receives a notification that a
        job finished.

        Note: if the worker is scheduled to be disabled, then we
        disable it, and notify the ES to discard the outcome obtained
        by the worker.

        shard (int): the worker to release.

        returns (bool): if the result is to be ignored.

        """
        if self._job[shard] == WorkerPool.WORKER_INACTIVE:
            err_msg = "Trying to release worker while it's inactive."
            logger.error(err_msg)
            raise ValueError(err_msg)
        ret = self._ignore[shard]
        self._start_time[shard] = None
        self._side_data[shard] = None
        self._ignore[shard] = False
        if self._schedule_disabling[shard]:
            self._job[shard] = WorkerPool.WORKER_DISABLED
            self._schedule_disabling[shard] = False
            logger.info("Worker %s released and disabled." % shard)
        else:
            self._job[shard] = WorkerPool.WORKER_INACTIVE
            logger.debug("Worker %s released." % shard)
        return ret

    def find_worker(self, job, require_connection=False, random_worker=False):
        """Return a worker whose assigned job is job. Remember that
        there is a placeholder job to signal that the worker is not
        doing anything (or disabled).

        job (job): the job we are looking for, or WorkerPool.WORKER_*.
        require_connection (bool): True if we want to find a worker
                                   doing the job and that is actually
                                   connected to us (i.e., did not
                                   die).
        random_worker (bool): if True, choose uniformly amongst all
                       workers doing the job.

        returns (int): the shard of the worker working on job.

        raise: LookupError if nothing has been found.

        """
        pool = []
        for shard, worker_job in self._job.iteritems():
            if worker_job == job:
                if not require_connection or self._worker[shard].connected:
                    pool.append(shard)
                    if not random_worker:
                        return shard
        if pool == []:
            raise LookupError("No such job.")
        else:
            return random.choice(pool)

    def ignore_job(self, job):
        """Mark the job to be ignored, and try to inform the worker.

        job (job): the job to ignore.

        raise: LookupError if job is not found.

        """
        shard = self.find_worker(job)
        self._ignore[shard] = True
        self._worker[shard].ignore_job()

    def get_status(self):
        """Returns a dict with info about the current status of all
        workers.

        return (dict): dict of info: current job, starting time,
                       number of errors, and additional data specified
                       in the job.

        """
        result = dict()
        for shard in self._worker.keys():
            s_time = self._start_time[shard]
            s_time = make_timestamp(s_time) if s_time is not None else None
            s_data = self._side_data[shard]
            s_data = (s_data[0], make_timestamp(s_data[1])) \
                if s_data is not None else None

            result[str(shard)] = {
                'connected': self._worker[shard].connected,
                'job': self._job[shard],
                'start_time': s_time,
                'side_data': s_data}
        return result

    def check_timeouts(self):
        """Check if some worker is not responding in too much time. If
        this is the case, the worker is scheduled for disabling, and
        we send him a message trying to shut it down.

        return (list): list of tuples (priority, timestamp, job) of
                       jobs assigned to worker that timeout.

        """
        now = make_datetime()
        lost_jobs = []
        for shard in self._worker:
            if self._start_time[shard] is not None:
                active_for = now - self._start_time[shard]

                if active_for > EvaluationService.WORKER_TIMEOUT:
                    # Here shard is a working worker with no sign of
                    # intelligent life for too much time.
                    logger.error("Disabling and shutting down "
                                 "worker %d because of no reponse "
                                 "in %s." %
                                 (shard, active_for))
                    assert self._job[shard] != WorkerPool.WORKER_INACTIVE \
                        and self._job[shard] != WorkerPool.WORKER_DISABLED

                    # We return the job so ES can do what it needs.
                    if not self._ignore[shard]:
                        job = self._job[shard]
                        priority, timestamp = self._side_data[shard]
                        lost_jobs.append((priority, timestamp, job))

                    # Also, we are not trusting it, so we are not
                    # assigning him new jobs even if it comes back to
                    # life.
                    self._schedule_disabling[shard] = True
                    self._ignore[shard] = True
                    self.release_worker(shard)
                    self._worker[shard].quit("No response in %s." % active_for)

        return lost_jobs

    def check_connections(self):
        """Check if a worker we assigned a job to disconnects. In this
        case, requeue the job.

        return (list): list of tuples (priority, timestamp, job) of
                       jobs assigned to worker that disconnected.

        """
        lost_jobs = []
        for shard in self._worker:
            if not self._worker[shard].connected and \
                   self._job[shard] not in [WorkerPool.WORKER_DISABLED,
                                            WorkerPool.WORKER_INACTIVE]:
                if not self._ignore[shard]:
                    job = self._job[shard]
                    priority, timestamp = self._side_data[shard]
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
    JOB_TYPE_TEST_COMPILATION = "compile_test"
    JOB_TYPE_TEST_EVALUATION = "evaluate_test"

    MAX_COMPILATION_TRIES = 3
    MAX_EVALUATION_TRIES = 3
    MAX_TEST_COMPILATION_TRIES = 3
    MAX_TEST_EVALUATION_TRIES = 3

    INVALIDATE_COMPILATION = 0
    INVALIDATE_EVALUATION = 1

    # Seconds after which we declare a worker stale.
    WORKER_TIMEOUT = timedelta(seconds=600)
    # How often we check for stale workers.
    WORKER_TIMEOUT_CHECK_TIME = timedelta(seconds=300)

    # How often we check if a worker is connected.
    WORKER_CONNECTION_CHECK_TIME = timedelta(seconds=10)

    # How often we check if we can assign a job to a worker.
    CHECK_DISPATCH_TIME = timedelta(seconds=2)

    # How often we look for submission not compiled/evaluated.
    JOBS_NOT_DONE_CHECK_TIME = timedelta(seconds=117)

    def __init__(self, shard, contest_id):
        logger.initialize(ServiceCoord("EvaluationService", shard))
        Service.__init__(self, shard, custom_logger=logger)

        self.contest_id = contest_id

        self.queue = JobQueue()
        self.pool = WorkerPool(self)
        self.scoring_service = self.connect_to(
            ServiceCoord("ScoringService", 0))

        for i in xrange(get_service_shards("Worker")):
            worker = ServiceCoord("Worker", i)
            self.pool.add_worker(worker)

        self.add_timeout(self.dispatch_jobs, None,
                         EvaluationService.CHECK_DISPATCH_TIME
                         .total_seconds(),
                         immediately=True)
        self.add_timeout(self.check_workers_timeout, None,
                         EvaluationService.WORKER_TIMEOUT_CHECK_TIME
                         .total_seconds(),
                         immediately=False)
        self.add_timeout(self.check_workers_connection, None,
                         EvaluationService.WORKER_CONNECTION_CHECK_TIME
                         .total_seconds(),
                         immediately=False)
        self.add_timeout(self.search_jobs_not_done, None,
                         EvaluationService.JOBS_NOT_DONE_CHECK_TIME
                         .total_seconds(),
                         immediately=True)

    def search_jobs_not_done(self):
        """Look in the database for submissions that have not been
        compiled or evaluated for no good reasons. Put the missing job
        in the queue.

        """
        new_jobs = 0
        with SessionGen(commit=False) as session:
            contest = session.query(Contest).\
                      filter_by(id=self.contest_id).first()

            # Only adding submission not compiled/evaluated that have
            # not yet reached the limit of tries.
            for submission in contest.get_submissions():
                if to_compile(submission):
                    if self.push_in_queue(
                        (EvaluationService.JOB_TYPE_COMPILATION,
                         submission.id),
                        EvaluationService.JOB_PRIORITY_HIGH,
                        submission.timestamp):
                        new_jobs += 1
                elif to_evaluate(submission):
                    if self.push_in_queue(
                        (EvaluationService.JOB_TYPE_EVALUATION,
                         submission.id),
                        EvaluationService.JOB_PRIORITY_MEDIUM,
                        submission.timestamp):
                        new_jobs += 1

            # The same for user tests
            for user_test in contest.get_user_tests():
                if user_test_to_compile(user_test):
                    if self.push_in_queue(
                        (EvaluationService.JOB_TYPE_TEST_COMPILATION,
                         user_test.id),
                        EvaluationService.JOB_PRIORITY_HIGH,
                        user_test.timestamp):
                        new_jobs += 1
                elif user_test_to_evaluate(user_test):
                    if self.push_in_queue(
                        (EvaluationService.JOB_TYPE_TEST_EVALUATION,
                         user_test.id),
                        EvaluationService.JOB_PRIORITY_MEDIUM,
                        user_test.timestamp):
                        new_jobs += 1

        if new_jobs > 0:
            logger.info("Found %s submissions or user tests with "
                        "jobs to do." % new_jobs)

        # Run forever.
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
            for submission in contest.get_submissions():
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
                    # Should not happen.
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
            logger.info("Job %s for submission/user test %d put again "
                        "in the queue because of timeout worker."
                        % (job[0], job[1]))
            self.push_in_queue(job, priority, timestamp)
        return True

    def check_workers_connection(self):
        """We ask WorkerPool for the unconnected workers, and we put
        again their jobs in the queue.

        """
        lost_jobs = self.pool.check_connections()
        for priority, timestamp, job in lost_jobs:
            logger.info("Job %s for submission/user test %s put again "
                        "in the queue because of disconnected worker."
                        % (job[0], job[1]))
            self.push_in_queue(job, priority, timestamp)
        return True

    def submission_busy(self, submission_id):
        """Check if the submission has a related job in the queue or
        assigned to a worker.

        """
        jobs = [(EvaluationService.JOB_TYPE_COMPILATION, submission_id),
                (EvaluationService.JOB_TYPE_EVALUATION, submission_id)]
        return any([job in self.queue or job in self.pool for job in jobs])

    def user_test_busy(self, user_test_id):
        """Check if the user test has a related job in the queue or
        assigned to a worker.

        """
        jobs = [(EvaluationService.JOB_TYPE_TEST_COMPILATION, user_test_id),
                (EvaluationService.JOB_TYPE_TEST_EVALUATION, user_test_id)]
        return any([job in self.queue or job in self.pool for job in jobs])

    def job_busy(self, job):
        """Check the entity (submission or user test) related to a job
        has other related jobs in the queue or assigned to a worker.

        """
        if job[0] in [EvaluationService.JOB_TYPE_COMPILATION,
                      EvaluationService.JOB_TYPE_EVALUATION]:
            return self.submission_busy(job[1])
        elif job[0] in [EvaluationService.JOB_TYPE_TEST_COMPILATION,
                        EvaluationService.JOB_TYPE_TEST_EVALUATION]:
            return self.user_test_busy(job[1])
        else:
            raise Exception("Wrong job type %s" % (job[0]))

    def push_in_queue(self, job, priority, timestamp):
        """Push a job in the job queue if the submission is not
        already in the queue or assigned to a worker.

        job (job): a pair (job_type, submission_id) to push.

        return (bool): True if pushed, False if not.

        """
        if self.job_busy(job):
            return False
        else:
            self.queue.push(job, priority, timestamp)
            return True

    @rpc_callback
    def action_finished(self, data, plus, error=None):
        """Callback from a worker, to signal that is finished some
        action (compilation or evaluation).

        data (dict): a dictionary that describes a Job instance.
        plus (tuple): the tuple (job_type,
                                 object_id,
                                 side_data=(priority, timestamp),
                                 shard_of_worker)

        """
        # TODO - The next two comments are in the wrong place and
        # really little understandable anyway.

        # We notify the pool that the worker is free (even if it
        # replied with an error), but if the pool wants to disable the
        # worker, it's because it already assigned its job to someone
        # else, so we discard the data from the worker.
        job_type, object_id, side_data, shard = plus

        # If worker was ignored, do nothing.
        if self.pool.release_worker(shard):
            return

        job_success = True
        if error is not None:
            logger.error("Received error from Worker: `%s'." % error)
            job_success = False

        else:
            try:
                job = Job.import_from_dict_with_type(data)
            except:
                logger.critical("[action_finished] Couldn't build Job for data"
                            " %s." % (data))
                job_success = False

            else:
                if not job.success:
                    logger.error("Worker %s signaled action "
                                 "not successful." % shard)
                    job_success = False

        _, timestamp = side_data

        logger.info("Action %s for submission %s completed. Success: %s." %
                    (job_type, object_id, data["success"]))

        # We get the submission from DB and update it.
        with SessionGen(commit=False) as session:

            if job_type == EvaluationService.JOB_TYPE_COMPILATION:
                submission = Submission.get_from_id(object_id, session)
                if submission is None:
                    logger.critical("[action_finished] Couldn't find "
                                    "submission %d in the database." %
                                    object_id)
                    return

                submission.compilation_tries += 1

                if job_success:
                    submission.compilation_outcome = 'ok' \
                        if job.compilation_success else 'fail'
                    submission.compilation_text = job.text
                    submission.compilation_shard = job.shard
                    submission.compilation_sandbox = ":".join(job.sandboxes)
                    for executable in job.executables.itervalues():
                        submission.executables[executable.filename] = \
                            executable
                        session.add(executable)

                self.compilation_ended(submission)

            elif job_type == EvaluationService.JOB_TYPE_EVALUATION:
                submission = Submission.get_from_id(object_id, session)
                if submission is None:
                    logger.critical("[action_finished] Couldn't find "
                                    "submission %s in the database." %
                                    object_id)
                    return

                submission.evaluation_tries += 1

                if job_success:
                    submission.evaluation_outcome = "ok"
                    for test_number, info in job.evaluations.iteritems():
                        evaluation = Evaluation(
                            text=info['text'],
                            outcome=info['outcome'],
                            num=test_number,
                            memory_used=info['plus'].get('memory_used', None),
                            execution_time=info['plus']
                            .get('execution_time', None),
                            execution_wall_clock_time=info['plus']
                            .get('execution_wall_clock_time', None),
                            evaluation_shard=job.shard,
                            evaluation_sandbox=":".join(info['sandboxes']),
                            submission=submission)
                        session.add(evaluation)

                self.evaluation_ended(submission)

            elif job_type == EvaluationService.JOB_TYPE_TEST_COMPILATION:
                user_test = UserTest.get_from_id(object_id, session)
                if user_test is None:
                    logger.critical("[action_finished] Couldn't find "
                                    "user test %d in the database." %
                                    object_id)
                    return

                user_test.compilation_tries += 1

                if job_success:
                    user_test.compilation_outcome = 'ok' \
                        if job.compilation_success else 'fail'
                    user_test.compilation_text = job.text
                    user_test.compilation_shard = job.shard
                    user_test.compilation_sandbox = ":".join(job.sandboxes)
                    for executable in job.executables.itervalues():
                        ut_executable = UserTestExecutable.import_from_dict(
                            executable.export_to_dict())
                        user_test.executables[ut_executable.filename] = \
                            ut_executable
                        session.add(ut_executable)

                self.user_test_compilation_ended(user_test)

            elif job_type == EvaluationService.JOB_TYPE_TEST_EVALUATION:
                user_test = UserTest.get_from_id(object_id, session)
                if user_test is None:
                    logger.critical("[action_finished] Couldn't find "
                                    "user test %d in the database." %
                                    object_id)
                    return

                user_test.evaluation_tries += 1

                if job_success:
                    try:
                        [evaluation] = job.evaluations.values()
                    except ValueError:
                        logger.error("[action_finished] I expected the job "
                                     "for a user test to contain a single "
                                     "evaluation, while instead it has %d."
                                     % (len(job.evaluations.values())))
                        return
                    user_test.evaluation_outcome = 'ok'
                    user_test.evaluation_shard = job.shard
                    user_test.output = evaluation['output']
                    user_test.evaluation_text = evaluation['text']
                    user_test.evaluation_sandbox = \
                        ":".join(evaluation['sandboxes'])
                    user_test.memory_used = evaluation['plus']. \
                        get('memory_used', None),
                    user_test.execution_time = evaluation['plus'] \
                        .get('execution_time', None),

                self.user_test_evaluation_ended(user_test)

            else:
                logger.error("Invalid job type %r." % (job_type))
                return

            session.commit()

    def compilation_ended(self, submission):
        """Actions to be performed when we have a submission that has
        ended compilation . In particular: we queue evaluation if
        compilation was ok; we requeue compilation if we fail.

        submission (Submission): the submission.

        """
        # Compilation was ok, so we evaluate.
        if submission.compilation_outcome == "ok":
            self.push_in_queue((EvaluationService.JOB_TYPE_EVALUATION,
                                submission.id),
                               EvaluationService.JOB_PRIORITY_MEDIUM,
                               submission.timestamp)
        # If instead submission failed compilation, we don't evaluate.
        elif submission.compilation_outcome == "fail":
            logger.info("Submission %d did not compile. Not going "
                        "to evaluate." % submission.id)
        # If compilation failed for our fault, we requeue or not.
        elif submission.compilation_outcome is None:
            if submission.compilation_tries > \
                    EvaluationService.MAX_COMPILATION_TRIES:
                logger.error("Maximum tries reached for the "
                             "compilation of submission %d. I will "
                             "not try again." % submission.id)
            else:
                # Note: lower priority (MEDIUM instead of HIGH) for
                # compilations that are probably failing again.
                self.push_in_queue((EvaluationService.JOB_TYPE_COMPILATION,
                                    submission.id),
                                   EvaluationService.JOB_PRIORITY_MEDIUM,
                                   submission.timestamp)
        # Otherwise, error.
        else:
            logger.error("Compilation outcome %r not recognized." %
                         submission.compilation_outcome)

    def evaluation_ended(self, submission):
        """Actions to be performed when we have a submission that has
        been evaluated. In particular: we inform ScoringService on
        success, we requeue on failure.

        submission (Submission): the submission.

        """
        # Evaluation successful, we inform ScoringService so it can
        # update the score. We need to commit the session beforehand,
        # otherwise the ScoringService wouldn't receive the updated
        # submission.
        if submission.evaluated():
            submission.get_session().commit()
            self.scoring_service.new_evaluation(submission_id=submission.id)
        # Evaluation unsuccessful, we requeue (or not).
        elif submission.evaluation_tries > \
                EvaluationService.MAX_EVALUATION_TRIES:
            logger.error("Maximum tries reached for the "
                         "evaluation of submission %d. I will "
                         "not try again." % submission.id)
        else:
            # Note: lower priority (LOW instead of MEDIUM) for
            # evaluations that are probably failing again.
            self.push_in_queue((EvaluationService.JOB_TYPE_EVALUATION,
                                submission.id),
                               EvaluationService.JOB_PRIORITY_LOW,
                               submission.timestamp)

    def user_test_compilation_ended(self, user_test):
        """Actions to be performed when we have a user test that has
        ended compilation. In particular: we queue evaluation if
        compilation was ok; we requeue compilation if it failed.

        user_test (UserTest): the user test.

        """
        # Compilation was ok, so we evaluate
        if user_test.compilation_outcome == 'ok':
            self.push_in_queue((EvaluationService.JOB_TYPE_TEST_EVALUATION,
                                user_test.id),
                               EvaluationService.JOB_PRIORITY_MEDIUM,
                               user_test.timestamp)
        # If instead user test failed compilation, we don't evaluatate
        elif user_test.compilation_outcome == 'fail':
            logger.info("User test %d did not compile. Not going "
                        "to evaluate." % user_test.id)
        # If compilation failed for our fault, we requeue or not
        elif user_test.compilation_outcome is None:
            if user_test.compilation_tries > \
                    EvaluationService.MAX_TEST_COMPILATION_TRIES:
                logger.error("Maximum tries reached for the "
                             "compilation of user test %d. I will "
                             "not try again." % (user_test.id))
            else:
                # Note: lower priority (MEDIUM instead of HIGH) for
                # compilations that are probably failing again
                self.push_in_queue((EvaluationService.
                                    JOB_TYPE_TEST_COMPILATION,
                                    user_test.id),
                                   EvaluationService.JOB_PRIORITY_MEDIUM,
                                   user_test.timestamp)

    def user_test_evaluation_ended(self, user_test):
        """Actions to be performed when we have a user test that has
        been evaluated. In particular: we do nothing on success, we
        requeue on failure.

        user_test (UserTest): the user test.

        """
        if not user_test.evaluated():
            if user_test.evaluation_tries > \
                    EvaluationService.MAX_TEST_EVALUATION_TRIES:
                logger.error("Maximum tries reached for the "
                             "evaluation of user test %d. I will "
                             "no try again." % (user_test.id))
            else:
                # Note: lower priority (LOW instead of MEDIUM) for
                # evaluations that are probably failing again.
                self.push_in_queue((EvaluationService.JOB_TYPE_TEST_EVALUATION,
                                    user_test.id),
                                   EvaluationService.JOB_PRIORITY_LOW,
                                   user_test.timestamp)

    @rpc_method
    def new_submission(self, submission_id):
        """This RPC prompts ES of the existence of a new
        submission. ES takes the right countermeasures, i.e., it
        schedules it for compilation.

        submission_id (int): the id of the new submission.

        returns (bool): True if everything went well.

        """
        with SessionGen(commit=False) as session:
            submission = Submission.get_from_id(submission_id, session)
            if submission is None:
                logger.error("[new_submission] Couldn't find submission "
                             "%d in the database." % submission_id)
                return

            if to_compile(submission):
                self.push_in_queue((EvaluationService.JOB_TYPE_COMPILATION,
                                    submission_id),
                                   EvaluationService.JOB_PRIORITY_HIGH,
                                   submission.timestamp)

    @rpc_method
    def new_user_test(self, user_test_id):
        """This RPC prompts ES of the existence of a new user test. ES
        takes takes the right countermeasures, i.e., it schedules it
        for compilation.

        user_test_id (int): the id of the new user test.

        returns (bool): True if everything went well.

        """
        with SessionGen(commit=False) as session:
            user_test = UserTest.get_from_id(user_test_id, session)
            if user_test is None:
                logger.error("[new_user_test] Couldn't find user test %d "
                             "in the database." % (user_test_id))
                return

            if user_test_to_compile(user_test):
                self.push_in_queue((EvaluationService.
                                    JOB_TYPE_TEST_COMPILATION,
                                    user_test_id),
                                   EvaluationService.JOB_PRIORITY_HIGH,
                                   user_test.timestamp)

    @rpc_method
    def invalidate_submission(self,
                              submission_id=None,
                              user_id=None,
                              task_id=None,
                              level="compilation"):
        """Request for invalidating some computed data.

        The data (compilations and evaluations, or evaluations only)
        to be cleared are the one regarding 1) a submission or 2) all
        submissions of a user or 3) all submissions of a task or 4)
        all submission (if all parameters are None).

        The data are cleared, the jobs involving the submissions
        currently enqueued are deleted, and the one already assigned
        to the workers are ignored. New appropriate jobs are enqueued.

        submission_id (int): id of the submission to invalidate, or
                             None.
        user_id (int): id of the user we want to invalidate, or None.
        task_id (int): id of the task we want to invalidate, or None.
        level (string): 'compilation' or 'evaluation'

        """
        logger.info("Invalidation request received.")
        if level not in ["compilation", "evaluation"]:
            err_msg = "Unexpected invalidation level `%s'." % level
            logger.warning(err_msg)
            raise ValueError(err_msg)

        submission_ids = get_submissions(
            self.contest_id,
            submission_id, user_id, task_id)

        logger.info("Submissions to invalidate for %s: %s." %
                    (level, len(submission_ids)))
        if len(submission_ids) == 0:
            return

        for submission_id in submission_ids:
            jobs = [(EvaluationService.JOB_TYPE_COMPILATION, submission_id),
                    (EvaluationService.JOB_TYPE_EVALUATION, submission_id)]
            for job in jobs:
                try:
                    self.queue.remove(job)
                except KeyError:
                    pass  # Ok, the job wasn't in the queue.
                try:
                    self.pool.ignore_job(job)
                except LookupError:
                    pass  # Ok, the job wasn't in the pool.

        # We invalidate the appropriate data and queue the jobs to
        # recompute those data.
        with SessionGen(commit=True) as session:
            for submission_id in submission_ids:
                submission = Submission.get_from_id(submission_id, session)

                if level == "compilation":
                    submission.invalidate_compilation()
                    if to_compile(submission):
                        self.push_in_queue(
                            (EvaluationService.JOB_TYPE_COMPILATION,
                             submission_id),
                            EvaluationService.JOB_PRIORITY_HIGH,
                            submission.timestamp)
                elif level == "evaluation":
                    submission.invalidate_evaluation()
                    if to_evaluate(submission):
                        self.push_in_queue(
                            (EvaluationService.JOB_TYPE_EVALUATION,
                             submission_id),
                            EvaluationService.JOB_PRIORITY_MEDIUM,
                            submission.timestamp)


def main():
    """Parse arguments and launch service.

    """
    default_argument_parser("Submission's compiler and evaluator for CMS.",
                            EvaluationService,
                            ask_contest=ask_for_contest).run()


if __name__ == "__main__":
    main()
