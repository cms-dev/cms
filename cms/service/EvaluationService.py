#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2013 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging
import random
from datetime import timedelta
from collections import namedtuple
from functools import wraps

import gevent.coros

from cms import ServiceCoord, get_service_shards
from cms.io import Service, rpc_method
from cms.db import SessionGen, Contest, Dataset, Submission, \
    SubmissionResult, UserTest, UserTestResult
from cms.service import get_submission_results, get_datasets_to_judge
from cmscommon.datetime import make_datetime, make_timestamp
from cms.grading.Job import JobGroup


logger = logging.getLogger(__name__)


def to_compile(submission_result):
    """Return whether ES is interested in compiling the submission.

    submission_result (SubmissionResult): a submission result.

    return (bool): True if ES wants to compile the submission.

    """
    r = submission_result
    return r is None or \
        (not r.compiled() and
         r.compilation_tries < EvaluationService.MAX_COMPILATION_TRIES)


def to_evaluate(submission_result):
    """Return whether ES is interested in evaluating the submission.

    submission_result (SubmissionResult): a submission result.

    return (bool): True if ES wants to evaluate the submission.

    """
    r = submission_result
    return r is not None and r.compilation_succeeded() and \
        not r.evaluated() and \
        r.evaluation_tries < EvaluationService.MAX_EVALUATION_TRIES


def user_test_to_compile(user_test_result):
    """Return whether ES is interested in compiling the user test.

    user_test_result (UserTestResult): a user test result.

    return (bool): True if ES wants to compile the user test.

    """
    r = user_test_result
    return r is None or \
        (not r.compiled() and
         r.compilation_tries < EvaluationService.MAX_TEST_COMPILATION_TRIES)


def user_test_to_evaluate(user_test_result):
    """Return whether ES is interested in evaluating the user test.

    user_test_result (UserTestResult): a user test result.

    return (bool): True if ES wants to evaluate the user test.

    """
    r = user_test_result
    return r is not None and r.compilation_outcome == "ok" and \
        not r.evaluated() and \
        r.evaluation_tries < EvaluationService.MAX_TEST_EVALUATION_TRIES


# job_type is a constant defined in EvaluationService.
JobQueueEntry = namedtuple('JobQueueEntry',
                           ['job_type', 'object_id', 'dataset_id'])


def jqe_check(jqe):
    """
    Check that a JobQueueEntry object is actually to be enqueued.

    I.e., check that the associated action has not been performed
    yet. It is used in cases when the status of the underlying object
    may have changed since last check.

    jqe (JobQueueEntry): the queue entry to test.

    return (bool): True if jqe is still to be performed.

    """
    with SessionGen() as session:
        dataset = Dataset.get_from_id(jqe.dataset_id, session)
        if jqe.job_type == EvaluationService.JOB_TYPE_COMPILATION:
            submission = Submission.get_from_id(jqe.object_id, session)
            submission_result = submission.get_result_or_create(dataset)
            return to_compile(submission_result)
        elif jqe.job_type == EvaluationService.JOB_TYPE_EVALUATION:
            submission = Submission.get_from_id(jqe.object_id, session)
            submission_result = submission.get_result_or_create(dataset)
            return to_evaluate(submission_result)
        elif jqe.job_type == EvaluationService.JOB_TYPE_TEST_COMPILATION:
            user_test = UserTest.get_from_id(jqe.object_id, session)
            user_test_result = user_test.get_result_or_create(dataset)
            return user_test_to_compile(user_test_result)
        elif jqe.job_type == EvaluationService.JOB_TYPE_TEST_EVALUATION:
            user_test = UserTest.get_from_id(jqe.object_id, session)
            user_test_result = user_test.get_result_or_create(dataset)
            return user_test_to_evaluate(user_test_result)

    raise Exception("Should never arrive here")


class JobQueue(object):
    """An instance of this class will contains the (unique) priority
    queue of jobs (compilations, evaluations, ...) that the ES needs
    to process next.

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

        job (JobQueueEntry): a job to search.

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

        job (JobQueueEntry): the job to add to the queue.
        priority (int): the priority of the job.
        timestamp (datetime|None): the time of the submission, or None
            to use now.

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

        returns ((int, datetime, JobQueueEntry)): first element in the
            queue.

        raise (LookupError): on empty queue.

        """
        if len(self._queue) > 0:
            return self._queue[0]
        else:
            raise LookupError("Empty queue.")

    def pop(self):
        """Extracts (and returns) the first element in the queue.

        returns ((int, datetime, JobQueueEntry)): first element in the
            queue.

        raise (LookupError): on empty queue.

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

        job (JobQueueEntry): the job to remove.

        return (int, int, job): priority, timestamp, and job.

        raise (KeyError): if job not present.

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

        job (JobQueueEntry): the job whose priority needs to change.
        priority (int): the new priority.

        raise (LookupError): if job not present.

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


class WorkerPool(object):
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
        # Instruct GeventLibrary to connect ES to the Worker.
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

        job (JobQueueEntry): the job to assign to a worker.
        side_data (object): object to attach to the worker for later
            use.

        returns (int): None if no workers are available, the worker
            assigned to the job otherwise.

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
        job_type, object_id, dataset_id = job
        timestamp = side_data[1]
        queue_time = self._start_time[shard] - timestamp
        logger.info("Asking worker %s to %s submission/user test %d(%d) "
                    " (%s after submission)." %
                    (shard, job_type, object_id, dataset_id, queue_time))

        with SessionGen() as session:
            if job_type == EvaluationService.JOB_TYPE_COMPILATION:
                submission = Submission.get_from_id(object_id, session)
                dataset = Dataset.get_from_id(dataset_id, session)
                job_group = \
                    JobGroup.from_submission_compilation(submission, dataset)
            elif job_type == EvaluationService.JOB_TYPE_EVALUATION:
                submission = Submission.get_from_id(object_id, session)
                dataset = Dataset.get_from_id(dataset_id, session)
                job_group = \
                    JobGroup.from_submission_evaluation(submission, dataset)
            elif job_type == EvaluationService.JOB_TYPE_TEST_COMPILATION:
                user_test = UserTest.get_from_id(object_id, session)
                dataset = Dataset.get_from_id(dataset_id, session)
                job_group = \
                    JobGroup.from_user_test_compilation(user_test, dataset)
            elif job_type == EvaluationService.JOB_TYPE_TEST_EVALUATION:
                user_test = UserTest.get_from_id(object_id, session)
                dataset = Dataset.get_from_id(dataset_id, session)
                job_group = \
                    JobGroup.from_user_test_evaluation(user_test, dataset)

            self._worker[shard].execute_job_group(
                job_group_dict=job_group.export_to_dict(),
                callback=self._service.action_finished,
                plus=(job_type, object_id, dataset_id, side_data, shard))
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
        """Return a worker whose assigned job is job.

        Remember that there is a placeholder job to signal that the
        worker is not doing anything (or disabled).

        job (JobQueueEntry|unicode|None): the job we are looking for,
            or WorkerPool.WORKER_*.
        require_connection (bool): True if we want to find a worker
            doing the job and that is actually connected to us (i.e.,
            did not die).
        random_worker (bool): if True, choose uniformly amongst all
            workers doing the job.

        returns (int): the shard of the worker working on job.

        raise (LookupError): if nothing has been found.

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

        job (JobQueueEntry): the job to ignore.

        raise (LookupError): if job is not found.

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

            result["%d" % shard] = {
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
                                 "worker %d because of no response "
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


def with_post_finish_lock(func):
    @wraps(func)
    def wrapped(self, *args, **kwargs):
        with self.post_finish_lock:
            return func(self, *args, **kwargs)
    return wrapped


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
        Service.__init__(self, shard)

        self.contest_id = contest_id

        self.queue = JobQueue()
        self.pool = WorkerPool(self)
        self.post_finish_lock = gevent.coros.RLock()
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

    @rpc_method
    def search_jobs_not_done(self):
        """Look in the database for submissions that have not been
        compiled or evaluated for no good reasons. Put the missing job
        in the queue.

        """
        new_jobs = 0
        with SessionGen() as session:
            contest = session.query(Contest).\
                filter_by(id=self.contest_id).first()

            # Only adding submission not compiled/evaluated that have
            # not yet reached the limit of tries.
            for submission in contest.get_submissions():
                for dataset in get_datasets_to_judge(submission.task):
                    submission_result = \
                        submission.get_result_or_create(dataset)
                    if to_compile(submission_result):
                        if self.push_in_queue(
                                JobQueueEntry(
                                    EvaluationService.JOB_TYPE_COMPILATION,
                                    submission.id,
                                    dataset.id),
                                EvaluationService.JOB_PRIORITY_HIGH,
                                submission.timestamp,
                                check_again=True):
                            new_jobs += 1
                    elif to_evaluate(submission_result):
                        if self.push_in_queue(
                                JobQueueEntry(
                                    EvaluationService.JOB_TYPE_EVALUATION,
                                    submission.id,
                                    dataset.id),
                                EvaluationService.JOB_PRIORITY_MEDIUM,
                                submission.timestamp,
                                check_again=True):
                            new_jobs += 1

            # The same for user tests
            for user_test in contest.get_user_tests():
                for dataset in get_datasets_to_judge(user_test.task):
                    user_test_result = \
                        user_test.get_result_or_create(dataset)
                    if user_test_to_compile(user_test_result):
                        if self.push_in_queue(
                                JobQueueEntry(
                                    EvaluationService.
                                    JOB_TYPE_TEST_COMPILATION,
                                    user_test.id,
                                    dataset.id),
                                EvaluationService.JOB_PRIORITY_HIGH,
                                user_test.timestamp,
                                check_again=True):
                            new_jobs += 1
                    elif user_test_to_evaluate(user_test_result):
                        if self.push_in_queue(
                                JobQueueEntry(
                                    EvaluationService.JOB_TYPE_TEST_EVALUATION,
                                    user_test.id,
                                    dataset.id),
                                EvaluationService.JOB_PRIORITY_MEDIUM,
                                user_test.timestamp,
                                check_again=True):
                            new_jobs += 1

            session.commit()

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

        The status of a submission is checked on its result for the
        active dataset of its task.

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
        with SessionGen() as session:
            contest = Contest.get_from_id(self.contest_id, session)
            for submission_result in contest.get_submission_results():
                if submission_result.compilation_failed():
                    stats["compilation_fail"] += 1
                elif not submission_result.compiled():
                    if submission_result.compilation_tries >= \
                            EvaluationService.MAX_COMPILATION_TRIES:
                        stats["max_compilations"] += 1
                    else:
                        stats["compiling"] += 1
                elif submission_result.compilation_succeeded():
                    if submission_result.evaluated():
                        if submission_result.scored():
                            stats["scored"] += 1
                        else:
                            stats["evaluated"] += 1
                    else:
                        if submission_result.evaluation_tries >= \
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
            logger.info("Job %r put again in the queue because of "
                        "worker timeout." % (job,))
            self.push_in_queue(job, priority, timestamp)
        return True

    def check_workers_connection(self):
        """We ask WorkerPool for the unconnected workers, and we put
        again their jobs in the queue.

        """
        lost_jobs = self.pool.check_connections()
        for priority, timestamp, job in lost_jobs:
            logger.info("Job %r put again in the queue because of "
                        "disconnected worker." % (job,))
            self.push_in_queue(job, priority, timestamp)
        return True

    def submission_busy(self, submission_id, dataset_id):
        """Check if the submission has a related job in the queue or
        assigned to a worker.

        """
        jobs = [
            JobQueueEntry(
                EvaluationService.JOB_TYPE_COMPILATION,
                submission_id,
                dataset_id),
            JobQueueEntry(
                EvaluationService.JOB_TYPE_EVALUATION,
                submission_id,
                dataset_id),
        ]
        return any([job in self.queue or job in self.pool for job in jobs])

    def user_test_busy(self, user_test_id, dataset_id):
        """Check if the user test has a related job in the queue or
        assigned to a worker.

        """
        jobs = [
            JobQueueEntry(
                EvaluationService.JOB_TYPE_TEST_COMPILATION,
                user_test_id,
                dataset_id),
            JobQueueEntry(
                EvaluationService.JOB_TYPE_TEST_EVALUATION,
                user_test_id,
                dataset_id),
        ]
        return any([job in self.queue or job in self.pool for job in jobs])

    def job_busy(self, job):
        """Check the entity (submission or user test) related to a job
        has other related jobs in the queue or assigned to a worker.

        """
        job_type, object_id, dataset_id = job

        if job_type in (EvaluationService.JOB_TYPE_COMPILATION,
                        EvaluationService.JOB_TYPE_EVALUATION):
            return self.submission_busy(object_id, dataset_id)
        elif job_type in (EvaluationService.JOB_TYPE_TEST_COMPILATION,
                          EvaluationService.JOB_TYPE_TEST_EVALUATION):
            return self.user_test_busy(object_id, dataset_id)
        else:
            raise Exception("Wrong job type %s" % job_type)

    @with_post_finish_lock
    def push_in_queue(self, job, priority, timestamp, check_again=False):
        """Check a job and push it in the queue.

        Push a job in the job queue if the submission is not already
        in the queue or assigned to a worker. Optionally check that
        the job is actually still to be performed by running
        jqe_check() on it.

        job (JobQueueEntry): the job to put in the queue.
        priority (int): the priority of the job.
        timestamp (datetime): the time of the submission.
        check_again (bool): whether or not to run jqe_check() on the job.

        return (bool): True if pushed, False if not.

        """
        if self.job_busy(job):
            return False
        elif check_again and not jqe_check(job):
            return False
        else:
            self.queue.push(job, priority, timestamp)
            return True

    @with_post_finish_lock
    def action_finished(self, data, plus, error=None):
        """Callback from a worker, to signal that is finished some
        action (compilation or evaluation).

        data (dict): a dictionary that describes a JobGroup instance.
        plus (tuple): the tuple (job_type,
                                 object_id,
                                 dataset_id,
                                 side_data=(priority, timestamp),
                                 shard_of_worker)

        """
        # Unpack the plus tuple. It's built in the RPC call to Worker's
        # execute_job_group method inside WorkerPool.acquire_worker.
        job_type, object_id, dataset_id, side_data, shard = plus

        # We notify the pool that the worker is available again for
        # further work (no matter how the current request turned out,
        # even if the worker encountered an error). If the pool informs
        # us that the data produced by the worker has to be ignored (by
        # returning True) we interrupt the execution of this method and
        # do nothing because in that case we know the job has returned
        # to the queue and perhaps already been reassigned to another
        # worker.
        if self.pool.release_worker(shard):
            return

        job_success = True
        if error is not None:
            logger.error("Received error from Worker: `%s'." % error)
            job_success = False

        else:
            try:
                job_group = JobGroup.import_from_dict(data)
            except:
                logger.error("[action_finished] Couldn't build JobGroup for "
                             "data %s." % data, exc_info=True)
                job_success = False

            else:
                if not job_group.success:
                    logger.error("Worker %s signaled action "
                                 "not successful." % shard)
                    job_success = False

        _, timestamp = side_data

        logger.info("Action %s for submission %s completed. Success: %s." %
                    (job_type, object_id, job_success))

        # We get the submission from DB and update it.
        with SessionGen() as session:
            if job_type == EvaluationService.JOB_TYPE_COMPILATION:
                submission_result = SubmissionResult.get_from_id(
                    (object_id, dataset_id), session)
                if submission_result is None:
                    logger.error("[action_finished] Couldn't find "
                                 "submission %d(%d) in the database." %
                                 (object_id, dataset_id))
                    return

                submission_result.compilation_tries += 1

                if job_success:
                    job_group.to_submission_compilation(submission_result)

                self.compilation_ended(submission_result)

            elif job_type == EvaluationService.JOB_TYPE_EVALUATION:
                submission_result = SubmissionResult.get_from_id(
                    (object_id, dataset_id), session)
                if submission_result is None:
                    logger.error("[action_finished] Couldn't find "
                                 "submission %d(%d) in the database." %
                                 (object_id, dataset_id))
                    return

                submission_result.evaluation_tries += 1

                if job_success:
                    job_group.to_submission_evaluation(submission_result)

                self.evaluation_ended(submission_result)

            elif job_type == EvaluationService.JOB_TYPE_TEST_COMPILATION:
                user_test_result = UserTestResult.get_from_id(
                    (object_id, dataset_id), session)
                if user_test_result is None:
                    logger.error("[action_finished] Couldn't find "
                                 "user test %d(%d) in the database." %
                                 (object_id, dataset_id))
                    return

                user_test_result.compilation_tries += 1

                if job_success:
                    job_group.to_user_test_compilation(user_test_result)

                self.user_test_compilation_ended(user_test_result)

            elif job_type == EvaluationService.JOB_TYPE_TEST_EVALUATION:
                user_test_result = UserTestResult.get_from_id(
                    (object_id, dataset_id), session)
                if user_test_result is None:
                    logger.error("[action_finished] Couldn't find "
                                 "user test %d(%d) in the database." %
                                 (object_id, dataset_id))
                    return

                user_test_result.evaluation_tries += 1

                if job_success:
                    job_group.to_user_test_evaluation(user_test_result)

                self.user_test_evaluation_ended(user_test_result)

            else:
                logger.error("Invalid job type %r." % job_type)
                return

            session.commit()

    def compilation_ended(self, submission_result):
        """Actions to be performed when we have a submission that has
        ended compilation . In particular: we queue evaluation if
        compilation was ok, we inform ScoringService if the
        compilation failed for an error in the submission, or we
        requeue the compilation if there was an error in CMS.

        submission_result (SubmissionResult): the submission result.

        """
        submission = submission_result.submission
        # Compilation was ok, so we evaluate.
        if submission_result.compilation_succeeded():
            self.push_in_queue(
                JobQueueEntry(
                    EvaluationService.JOB_TYPE_EVALUATION,
                    submission_result.submission_id,
                    submission_result.dataset_id),
                EvaluationService.JOB_PRIORITY_MEDIUM,
                submission.timestamp)
        # If instead submission failed compilation, we don't evaluate,
        # but we inform ScoringService of the new submission. We need
        # to commit before so it has up to date information.
        elif submission_result.compilation_failed():
            logger.info("Submission %d(%d) did not compile. Not going to "
                        "evaluate." %
                        (submission_result.submission_id,
                         submission_result.dataset_id))
            submission_result.sa_session.commit()
            self.scoring_service.new_evaluation(
                submission_id=submission_result.submission_id,
                dataset_id=submission_result.dataset_id)
        # If compilation failed for our fault, we requeue or not.
        elif submission_result.compilation_outcome is None:
            if submission_result.compilation_tries > \
                    EvaluationService.MAX_COMPILATION_TRIES:
                logger.error("Maximum tries reached for the compilation of "
                             "submission %d(%d). I will not try again." %
                             (submission_result.submission_id,
                              submission_result.dataset_id))
            else:
                # Note: lower priority (MEDIUM instead of HIGH) for
                # compilations that are probably failing again.
                self.push_in_queue(
                    JobQueueEntry(
                        EvaluationService.JOB_TYPE_COMPILATION,
                        submission_result.submission_id,
                        submission_result.dataset_id),
                    EvaluationService.JOB_PRIORITY_MEDIUM,
                    submission.timestamp)
        # Otherwise, error.
        else:
            logger.error("Compilation outcome %r not recognized." %
                         submission_result.compilation_outcome)

    def evaluation_ended(self, submission_result):
        """Actions to be performed when we have a submission that has
        been evaluated. In particular: we inform ScoringService on
        success, we requeue on failure.

        submission_result (SubmissionResult): the submission result.

        """
        submission = submission_result.submission
        # Evaluation successful, we inform ScoringService so it can
        # update the score. We need to commit the session beforehand,
        # otherwise the ScoringService wouldn't receive the updated
        # submission.
        if submission_result.evaluated():
            submission_result.sa_session.commit()
            self.scoring_service.new_evaluation(
                submission_id=submission_result.submission_id,
                dataset_id=submission_result.dataset_id)
        # Evaluation unsuccessful, we requeue (or not).
        elif submission_result.evaluation_tries > \
                EvaluationService.MAX_EVALUATION_TRIES:
            logger.error("Maximum tries reached for the evaluation of "
                         "submission %d(%d). I will not try again." %
                         (submission_result.submission_id,
                          submission_result.dataset_id))
        else:
            # Note: lower priority (LOW instead of MEDIUM) for
            # evaluations that are probably failing again.
            self.push_in_queue(
                JobQueueEntry(
                    EvaluationService.JOB_TYPE_EVALUATION,
                    submission_result.submission_id,
                    submission_result.dataset_id),
                EvaluationService.JOB_PRIORITY_LOW,
                submission.timestamp)

    def user_test_compilation_ended(self, user_test_result):
        """Actions to be performed when we have a user test that has
        ended compilation. In particular: we queue evaluation if
        compilation was ok; we requeue compilation if it failed.

        user_test_result (UserTestResult): the user test result.

        """
        user_test = user_test_result.user_test
        # Compilation was ok, so we evaluate
        if user_test_result.compilation_succeeded():
            self.push_in_queue(
                JobQueueEntry(
                    EvaluationService.JOB_TYPE_TEST_EVALUATION,
                    user_test_result.user_test_id,
                    user_test_result.dataset_id),
                EvaluationService.JOB_PRIORITY_MEDIUM,
                user_test.timestamp)
        # If instead user test failed compilation, we don't evaluatate
        elif user_test_result.compilation_failed():
            logger.info("User test %d(%d) did not compile. Not going to "
                        "evaluate." %
                        (user_test_result.user_test_id,
                         user_test_result.dataset_id))
        # If compilation failed for our fault, we requeue or not
        elif not user_test_result.compiled():
            if user_test_result.compilation_tries > \
                    EvaluationService.MAX_TEST_COMPILATION_TRIES:
                logger.error("Maximum tries reached for the compilation of "
                             "user test %d(%d). I will not try again." %
                             (user_test_result.user_test_id,
                              user_test_result.dataset_id))
            else:
                # Note: lower priority (MEDIUM instead of HIGH) for
                # compilations that are probably failing again
                self.push_in_queue(
                    JobQueueEntry(
                        EvaluationService.JOB_TYPE_TEST_COMPILATION,
                        user_test_result.user_test_id,
                        user_test_result.dataset_id),
                    EvaluationService.JOB_PRIORITY_MEDIUM,
                    user_test.timestamp)
        # Otherwise, error.
        else:
            logger.error("Compilation outcome %r not recognized." %
                         user_test_result.compilation_outcome)

    def user_test_evaluation_ended(self, user_test_result):
        """Actions to be performed when we have a user test that has
        been evaluated. In particular: we do nothing on success, we
        requeue on failure.

        user_test_result (UserTestResult): the user test result.

        """
        user_test = user_test_result.user_test
        if not user_test_result.evaluated():
            if user_test_result.evaluation_tries > \
                    EvaluationService.MAX_TEST_EVALUATION_TRIES:
                logger.error("Maximum tries reached for the evaluation of "
                             "user test %d(%d). I will no try again." %
                             (user_test_result.user_test_id,
                              user_test_result.dataset_id))
            else:
                # Note: lower priority (LOW instead of MEDIUM) for
                # evaluations that are probably failing again.
                self.push_in_queue(
                    JobQueueEntry(
                        EvaluationService.JOB_TYPE_TEST_EVALUATION,
                        user_test_result.user_test_id,
                        user_test_result.dataset_id),
                    EvaluationService.JOB_PRIORITY_LOW,
                    user_test.timestamp)

    @rpc_method
    def new_submission(self, submission_id):
        """This RPC prompts ES of the existence of a new
        submission. ES takes the right countermeasures, i.e., it
        schedules it for compilation.

        submission_id (int): the id of the new submission.

        """
        with SessionGen() as session:
            submission = Submission.get_from_id(submission_id, session)
            if submission is None:
                logger.error("[new_submission] Couldn't find submission "
                             "%d in the database." % submission_id)
                return

            for dataset in get_datasets_to_judge(submission.task):
                submission_result = submission.get_result_or_create(dataset)

                if to_compile(submission_result):
                    self.push_in_queue(
                        JobQueueEntry(
                            EvaluationService.JOB_TYPE_COMPILATION,
                            submission.id,
                            dataset.id),
                        EvaluationService.JOB_PRIORITY_HIGH,
                        submission.timestamp)

            session.commit()

    @rpc_method
    def new_user_test(self, user_test_id):
        """This RPC prompts ES of the existence of a new user test. ES
        takes takes the right countermeasures, i.e., it schedules it
        for compilation.

        user_test_id (int): the id of the new user test.

        returns (bool): True if everything went well.

        """
        with SessionGen() as session:
            user_test = UserTest.get_from_id(user_test_id, session)
            if user_test is None:
                logger.error("[new_user_test] Couldn't find user test %d "
                             "in the database." % user_test_id)
                return

            for dataset in get_datasets_to_judge(user_test.task):
                user_test_result = user_test.get_result_or_create(dataset)

                if user_test_to_compile(user_test_result):
                    self.push_in_queue(
                        JobQueueEntry(
                            EvaluationService.JOB_TYPE_TEST_COMPILATION,
                            user_test.id,
                            dataset.id),
                        EvaluationService.JOB_PRIORITY_HIGH,
                        user_test.timestamp)

            session.commit()

    @rpc_method
    def invalidate_submission(self,
                              submission_id=None,
                              dataset_id=None,
                              user_id=None,
                              task_id=None,
                              level="compilation"):
        """Request to invalidate some computed data.

        Invalidate the compilation and/or evaluation data of the
        SubmissionResults that:
        - belong to submission_id or, if None, to any submission of
          user_id and/or task_id or, if both None, to any submission
          of the contest this service is running for.
        - belong to dataset_id or, if None, to any dataset of task_id
          or, if None, to any dataset of any task of the contest this
          service is running for.

        The data is cleared, the jobs involving the submissions
        currently enqueued are deleted, and the ones already assigned
        to the workers are ignored. New appropriate jobs are enqueued.

        submission_id (int|None): id of the submission to invalidate,
            or None.
        dataset_id (int|None): id of the dataset to invalidate, or
            None.
        user_id (int|None): id of the user to invalidate, or None.
        task_id (int|None): id of the task to invalidate, or None.
        level (string): 'compilation' or 'evaluation'

        """
        logger.info("Invalidation request received.")

        # Validate arguments
        # TODO Check that all these objects belong to this contest.
        if level not in ("compilation", "evaluation"):
            raise ValueError(
                "Unexpected invalidation level `%s'." % level)

        with SessionGen() as session:
            submission_results = get_submission_results(
                # Give contest_id only if all others are None.
                self.contest_id
                if {user_id, task_id, submission_id, dataset_id} == {None}
                else None,
                user_id, task_id, submission_id, dataset_id, session)

            logger.info("Submission results to invalidate %s for: %d." %
                        (level, len(submission_results)))
            if len(submission_results) == 0:
                return

            for submission_result in submission_results:
                jobs = [
                    JobQueueEntry(
                        EvaluationService.JOB_TYPE_COMPILATION,
                        submission_result.submission_id,
                        submission_result.dataset_id),
                    JobQueueEntry(
                        EvaluationService.JOB_TYPE_EVALUATION,
                        submission_result.submission_id,
                        submission_result.dataset_id),
                    ]
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
                if level == "compilation":
                    submission_result.invalidate_compilation()
                    if to_compile(submission_result):
                        self.push_in_queue(
                            JobQueueEntry(
                                EvaluationService.JOB_TYPE_COMPILATION,
                                submission_result.submission_id,
                                submission_result.dataset_id),
                            EvaluationService.JOB_PRIORITY_HIGH,
                            submission_result.submission.timestamp)
                elif level == "evaluation":
                    submission_result.invalidate_evaluation()
                    if to_evaluate(submission_result):
                        self.push_in_queue(
                            JobQueueEntry(
                                EvaluationService.JOB_TYPE_EVALUATION,
                                submission_result.submission_id,
                                submission_result.dataset_id),
                            EvaluationService.JOB_PRIORITY_MEDIUM,
                            submission_result.submission.timestamp)

            session.commit()
