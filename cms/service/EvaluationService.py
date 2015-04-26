#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2015 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
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
contestants, transforming them in operations (compilation, execution,
...), queuing them with the right priority, and dispatching them to
the workers. Also, it collects the results from the workers and build
the current ranking.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging
import random
from datetime import timedelta
from functools import wraps

import gevent.coros
from gevent.event import Event
from sqlalchemy import func, not_

from cms import ServiceCoord, get_service_shards
from cms.io import Executor, PriorityQueue, QueueItem, TriggeredService, \
    rpc_method
from cms.db import Session, SessionGen, Contest, Dataset, Submission, \
    SubmissionResult, Task, UserTest, UserTestResult
from cms.service import get_submissions, get_submission_results, \
    get_datasets_to_judge
from cmscommon.datetime import make_datetime, make_timestamp
from cms.grading.Job import JobGroup


logger = logging.getLogger(__name__)


def submission_to_compile(submission_result):
    """Return whether ES is interested in compiling the submission.

    submission_result (SubmissionResult): a submission result.

    return (bool): True if ES wants to compile the submission.

    """
    return submission_result is None or \
        (not submission_result.compiled() and
         (submission_result.compilation_tries <
          EvaluationService.MAX_COMPILATION_TRIES))


def submission_to_evaluate(submission_result):
    """Return whether ES is interested in evaluating the submission.

    submission_result (SubmissionResult): a submission result.

    return (bool): True if ES wants to evaluate the submission.

    """
    return submission_result is not None and \
        submission_result.compilation_succeeded() and \
        not submission_result.evaluated() and \
        (submission_result.evaluation_tries <
         EvaluationService.MAX_EVALUATION_TRIES)


def submission_to_evaluate_on_testcase(submission_result, testcase_codename):
    """Return whether ES is interested in evaluating the submission
    on the given testcase.

    submission_result (SubmissionResult): a submission result.
    testcase_codename (str): codename of a testcase.

    return (bool): True if ES wants to evaluate the submission.

    """
    if not submission_to_evaluate(submission_result):
        return False

    for evaluation in submission_result.evaluations:
        if evaluation.testcase.codename == testcase_codename:
            return False
    return True


def user_test_to_compile(user_test_result):
    """Return whether ES is interested in compiling the user test.

    user_test_result (UserTestResult): a user test result.

    return (bool): True if ES wants to compile the user test.

    """
    r = user_test_result
    return r is None or \
        (not r.compiled() and
         (r.compilation_tries <
          EvaluationService.MAX_USER_TEST_COMPILATION_TRIES))


def user_test_to_evaluate(user_test_result):
    """Return whether ES is interested in evaluating the user test.

    user_test_result (UserTestResult): a user test result.

    return (bool): True if ES wants to evaluate the user test.

    """
    r = user_test_result
    return r is not None and r.compilation_outcome == "ok" and \
        not r.evaluated() and \
        r.evaluation_tries < EvaluationService.MAX_USER_TEST_EVALUATION_TRIES


def submission_get_operations(submission, dataset):
    """Generate all operations originating from a submission for a given
    dataset.

    submission (Submission): a submission;
    dataset (Dataset): a dataset.

    yield (ESOperation, int, datetime): an iterator providing triplets
        consisting of a ESOperation for a certain operation to
        perform, its priority and its timestamp.

    """
    submission_result = submission.get_result_or_create(dataset)
    if submission_to_compile(submission_result):
        priority = PriorityQueue.PRIORITY_HIGH \
            if submission_result.compilation_tries == 0 \
            else PriorityQueue.PRIORITY_MEDIUM
        if not dataset.active:
            priority = PriorityQueue.PRIORITY_EXTRA_LOW
        yield ESOperation(ESOperation.COMPILATION,
                          submission.id,
                          dataset.id), \
            priority, \
            submission.timestamp

    elif submission_to_evaluate(submission_result):
        priority = PriorityQueue.PRIORITY_MEDIUM \
            if submission_result.evaluation_tries == 0 \
            else PriorityQueue.PRIORITY_LOW
        if not dataset.active:
            priority = PriorityQueue.PRIORITY_EXTRA_LOW
        for testcase_codename in sorted(dataset.testcases.iterkeys()):
            yield ESOperation(ESOperation.EVALUATION,
                              submission.id,
                              dataset.id,
                              testcase_codename), \
                priority, \
                submission.timestamp


def user_test_get_operations(user_test, dataset):
    """Generate all operations originating from a user test for a given
    dataset.

    user_test (UserTest): a user test;
    dataset (Dataset): a dataset.

    yield (ESOperation, int, datetime): an iterator providing triplets
        consisting of a ESOperation for a certain operation to
        perform, its priority and its timestamp.

    """
    user_test_result = user_test.get_result_or_create(dataset)
    if user_test_to_compile(user_test_result):
        priority = PriorityQueue.PRIORITY_HIGH \
            if user_test_result.compilation_tries == 0\
            else PriorityQueue.PRIORITY_MEDIUM
        if not dataset.active:
            priority = PriorityQueue.PRIORITY_EXTRA_LOW
        yield ESOperation(ESOperation.USER_TEST_COMPILATION,
                          user_test.id,
                          dataset.id), \
            priority, \
            user_test.timestamp

    elif user_test_to_evaluate(user_test_result):
        priority = PriorityQueue.PRIORITY_MEDIUM \
            if user_test_result.evaluation_tries == 0 \
            else PriorityQueue.PRIORITY_LOW
        if not dataset.active:
            priority = PriorityQueue.PRIORITY_EXTRA_LOW
        yield ESOperation(ESOperation.USER_TEST_EVALUATION,
                          user_test.id,
                          dataset.id), \
            priority, \
            user_test.timestamp


def get_relevant_operations_(level, submissions, dataset_id=None):
    """Return all possible operations involving the submissions

    level (string): the starting level; if 'compilation', then we
        return operations for both compilation and evaluation; if
        'evaluation', we return evaluations only.
    submissions ([Submission]): submissions we want the operations for.
    dataset_id (int|None): id of the dataset to select, or None for all
        datasets

    return ([ESOperation]): list of relevant operations.

    """
    operations = []
    for submission in submissions:
        # All involved datasets: all of the task's dataset unless
        # one was specified.
        datasets = submission.task.datasets
        if dataset_id is not None:
            for dataset in submission.task.datasets:
                if dataset.id == dataset_id:
                    datasets = [dataset]
                    break

        # For each submission and dataset, the operations are: one
        # compilation, and one evaluation per testcase.
        for dataset in datasets:
            if level == 'compilation':
                operations.append(ESOperation(
                    ESOperation.COMPILATION,
                    submission.id,
                    dataset.id))
            for codename in dataset.testcases:
                operations.append(ESOperation(
                    ESOperation.EVALUATION,
                    submission.id,
                    dataset.id,
                    codename))

    return operations


class ESOperation(QueueItem):

    COMPILATION = "compile"
    EVALUATION = "evaluate"
    USER_TEST_COMPILATION = "compile_test"
    USER_TEST_EVALUATION = "evaluate_test"

    # Testcase codename is only needed for EVALUATION type of operation
    def __init__(self, type_, object_id, dataset_id, testcase_codename=None):
        self.type_ = type_
        self.object_id = object_id
        self.dataset_id = dataset_id
        self.testcase_codename = testcase_codename

    def __eq__(self, other):
        # We may receive a non-ESOperation other when comparing with
        # operations in the worker pool (as these may also be unicode or
        # None)
        if self.__class__ != other.__class__:
            return False
        return self.type_ == other.type_ \
            and self.object_id == other.object_id \
            and self.dataset_id == other.dataset_id \
            and self.testcase_codename == other.testcase_codename

    def __hash__(self):
        return hash((self.type_, self.object_id, self.dataset_id,
                     self.testcase_codename))

    def __str__(self):
        if self.type_ == ESOperation.EVALUATION:
            return "%s on %d against dataset %d, testcase %s" % (
                self.type_, self.object_id, self.dataset_id,
                self.testcase_codename)
        else:
            return "%s on %d against dataset %d" % (
                self.type_, self.object_id, self.dataset_id)

    def to_dict(self):
        return {"type": self.type_,
                "object_id": self.object_id,
                "dataset_id": self.dataset_id,
                "testcase_codename": self.testcase_codename}

    def check(self, session=None, dataset=None, submission=None,
              submission_result=None):
        """Check that this operation is actually to be enqueued.

        I.e., check that the associated action has not been performed
        yet. It is used in cases when the status of the underlying object
        may have changed since last check.

        Additional parameters can be supplied in order to reduce the
        number of database queries.

        session (Session): the database session to use;
        dataset (Dataset): a dataset for this operation;
        submission (Submission): a submission for this operation;
        submission_result (SubmissionResult): a submission_result for
            this operation.

        return (bool): True if the operation is still to be performed.

        """
        if session is None:
            session = Session()
        result = True
        dataset = dataset or Dataset.get_from_id(self.dataset_id, session)
        if self.type_ == ESOperation.COMPILATION:
            submission = submission \
                or Submission.get_from_id(self.object_id, session)
            submission_result = submission_result \
                or submission.get_result_or_create(dataset)
            result = submission_to_compile(submission_result)
        elif self.type_ == ESOperation.EVALUATION:
            submission = submission \
                or Submission.get_from_id(self.object_id, session)
            submission_result = submission_result \
                or submission.get_result_or_create(dataset)
            result = submission_to_evaluate_on_testcase(
                submission_result, self.testcase_codename)
        elif self.type_ == ESOperation.USER_TEST_COMPILATION:
            user_test = UserTest.get_from_id(self.object_id, session)
            user_test_result = user_test.get_result_or_create(dataset)
            result = user_test_to_compile(user_test_result)
        elif self.type_ == ESOperation.USER_TEST_EVALUATION:
            user_test = UserTest.get_from_id(self.object_id, session)
            user_test_result = user_test.get_result_or_create(dataset)
            result = user_test_to_evaluate(user_test_result)
        return result


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
        # it finishes the current operation). The current operation is
        # also discarded because we already re-assigned it. Ignore is
        # true if the next result coming from the worker should be
        # discarded.

        # TODO: given the number of pieces data associated to each
        # worker, this class could be simplified by creating a new
        # WorkerPoolItem class.
        self._operation = {}
        self._start_time = {}
        self._side_data = {}
        self._schedule_disabling = {}
        self._ignore = {}

        # Event set when there are workers available to take jobs. It
        # is only guaranteed that if a worker is available, then this
        # event is set. In other words, the fact that this event is
        # set does not mean that there is a worker available.
        self._workers_available_event = Event()

    def __contains__(self, operation):
        for shard in self._worker:
            if operation == self._operation[shard] and not self._ignore[shard]:
                return True
        return False

    def wait_for_workers(self):
        """Wait until a worker might be available."""
        self._workers_available_event.wait()

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
        self._operation[shard] = WorkerPool.WORKER_INACTIVE
        self._start_time[shard] = None
        self._side_data[shard] = None
        self._schedule_disabling[shard] = False
        self._ignore[shard] = False
        self._workers_available_event.set()
        logger.debug("Worker %s added.", shard)

    def on_worker_connected(self, worker_coord):
        """To be called when a worker comes alive after being
        offline. We use this callback to instruct the worker to
        precache all files concerning the contest.

        worker_coord (ServiceCoord): the coordinates of the worker
                                     that came online.

        """
        shard = worker_coord.shard
        logger.info("Worker %s online again.", shard)
        self._worker[shard].precache_files(contest_id=self._service.contest_id)
        # We don't requeue the operation, because a connection lost
        # does not invalidate a potential result given by the worker
        # (as the problem was the connection and not the machine on
        # which the worker is). But the worker could have been idling,
        # so we wake up the consumers.
        self._workers_available_event.set()

    def acquire_worker(self, operation, side_data=None):
        """Tries to assign an operation to an available worker. If no workers
        are available then this returns None, otherwise this returns
        the chosen worker.

        operation (ESOperation): the operation to assign to a worker.
        side_data (object): object to attach to the worker for later
            use.

        return (int|None): None if no workers are available, the worker
            assigned to the operation otherwise.

        """
        # We look for an available worker.
        try:
            shard = self.find_worker(WorkerPool.WORKER_INACTIVE,
                                     require_connection=True,
                                     random_worker=True)
        except LookupError:
            self._workers_available_event.clear()
            return None

        # Then we fill the info for future memory.
        self._operation[shard] = operation
        self._start_time[shard] = make_datetime()
        self._side_data[shard] = side_data
        logger.debug("Worker %s acquired.", shard)

        # And finally we ask the worker to do the operation.
        timestamp = side_data[1]
        queue_time = self._start_time[shard] - timestamp
        logger.info("Asking worker %s to `%s' (%s after submission).",
                    shard, operation, queue_time)

        with SessionGen() as session:
            if operation.type_ == ESOperation.COMPILATION:
                submission = Submission.get_from_id(operation.object_id,
                                                    session)
                dataset = Dataset.get_from_id(operation.dataset_id, session)
                job_group = \
                    JobGroup.from_submission_compilation(submission, dataset)
            elif operation.type_ == ESOperation.EVALUATION:
                submission = Submission.get_from_id(operation.object_id,
                                                    session)
                dataset = Dataset.get_from_id(operation.dataset_id, session)
                job_group = JobGroup.from_submission_evaluation(
                    submission, dataset, operation.testcase_codename)
            elif operation.type_ == ESOperation.USER_TEST_COMPILATION:
                user_test = UserTest.get_from_id(operation.object_id, session)
                dataset = Dataset.get_from_id(operation.dataset_id, session)
                job_group = \
                    JobGroup.from_user_test_compilation(user_test, dataset)
            elif operation.type_ == ESOperation.USER_TEST_EVALUATION:
                user_test = UserTest.get_from_id(operation.object_id, session)
                dataset = Dataset.get_from_id(operation.dataset_id, session)
                job_group = \
                    JobGroup.from_user_test_evaluation(user_test, dataset)

            self._worker[shard].execute_job_group(
                job_group_dict=job_group.export_to_dict(),
                callback=self._service.action_finished,
                plus=(operation.type_, operation.object_id,
                      operation.dataset_id, operation.testcase_codename,
                      side_data, shard))
        return shard

    def release_worker(self, shard):
        """To be called by ES when it receives a notification that an
        operation finished.

        Note: if the worker is scheduled to be disabled, then we
        disable it, and notify the ES to discard the outcome obtained
        by the worker.

        shard (int): the worker to release.

        returns (bool): if the result is to be ignored.

        """
        if self._operation[shard] == WorkerPool.WORKER_INACTIVE:
            err_msg = "Trying to release worker while it's inactive."
            logger.error(err_msg)
            raise ValueError(err_msg)

        # If the worker has already been disabled, ignore the result
        # and keep the worker disabled.
        if self._operation[shard] == WorkerPool.WORKER_DISABLED:
            return True

        ret = self._ignore[shard]
        self._start_time[shard] = None
        self._side_data[shard] = None
        self._ignore[shard] = False
        if self._schedule_disabling[shard]:
            self._operation[shard] = WorkerPool.WORKER_DISABLED
            self._schedule_disabling[shard] = False
            logger.info("Worker %s released and disabled.", shard)
        else:
            self._operation[shard] = WorkerPool.WORKER_INACTIVE
            self._workers_available_event.set()
            logger.debug("Worker %s released.", shard)
        return ret

    def find_worker(self, operation, require_connection=False,
                    random_worker=False):
        """Return a worker whose assigned operation is operation.

        Remember that there is a placeholder operation to signal that the
        worker is not doing anything (or disabled).

        operation (ESOperation|unicode|None): the operation we are
            looking for, or WorkerPool.WORKER_*.
        require_connection (bool): True if we want to find a worker
            doing the operation and that is actually connected to us
            (i.e., did not die).
        random_worker (bool): if True, choose uniformly amongst all
            workers doing the operation.

        returns (int): the shard of a worker working on operation.

        raise (LookupError): if nothing has been found.

        """
        pool = []
        for shard, worker_operation in self._operation.iteritems():
            if worker_operation == operation:
                if not require_connection or self._worker[shard].connected:
                    pool.append(shard)
                    if not random_worker:
                        return shard
        if pool == []:
            raise LookupError("No such operation.")
        else:
            return random.choice(pool)

    def ignore_operation(self, operation):
        """Mark the operation to be ignored, and try to inform the worker.

        operation (ESOperation): the operation to ignore.

        raise (LookupError): if operation is not found.

        """
        try:
            shard = self.find_worker(operation)
        except LookupError:
            logger.debug("Asked to ignore operation `%s' "
                         "that cannot be found.", operation)
            raise
        self._ignore[shard] = True
        self._worker[shard].ignore_job()

    def get_status(self):
        """Returns a dict with info about the current status of all
        workers.

        return (dict): dict of info: current operation, starting time,
            number of errors, and additional data specified in the
            operation.

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
                'operation': (self._operation[shard]
                              if not isinstance(self._operation[shard],
                                                QueueItem)
                              else self._operation[shard].to_dict()),
                'start_time': s_time,
                'side_data': s_data}
        return result

    def check_timeouts(self):
        """Check if some worker is not responding in too much time. If
        this is the case, the worker is scheduled for disabling, and
        we send him a message trying to shut it down.

        return (list): list of tuples (priority, timestamp, operation)
            of operations assigned to worker that timeout.

        """
        now = make_datetime()
        lost_operations = []
        for shard in self._worker:
            if self._start_time[shard] is not None:
                active_for = now - self._start_time[shard]

                if active_for > EvaluationService.WORKER_TIMEOUT:
                    # Here shard is a working worker with no sign of
                    # intelligent life for too much time.
                    logger.error("Disabling and shutting down "
                                 "worker %d because of no response "
                                 "in %s.", shard, active_for)
                    is_busy = (self._operation[shard]
                               != WorkerPool.WORKER_INACTIVE
                               and self._operation[shard]
                               != WorkerPool.WORKER_DISABLED)
                    assert is_busy

                    # We return the operation so ES can do what it needs.
                    if not self._ignore[shard]:
                        operation = self._operation[shard]
                        priority, timestamp = self._side_data[shard]
                        lost_operations.append(
                            (priority, timestamp, operation))

                    # Also, we are not trusting it, so we are not
                    # assigning him new operations even if it comes back to
                    # life.
                    self._schedule_disabling[shard] = True
                    self._ignore[shard] = True
                    self.release_worker(shard)
                    self._worker[shard].quit("No response in %s." % active_for)

        return lost_operations

    def disable_worker(self, shard):
        """Disable a worker.

        shard (int): which worker to disable.

        return ([(int, datetime, ESOperation)]): list of tuples
            (priority, timestamp, operation) of operations assigned to
            the worker; it is going to be either empty or a singleton.

        raise (ValueError): if worker is already disabled.

        """
        if self._operation[shard] == WorkerPool.WORKER_DISABLED:
            err_msg = \
                "Trying to disable already disabled worker %s." % shard
            logger.warning(err_msg)
            raise ValueError(err_msg)

        lost_operations = []
        if self._operation[shard] == WorkerPool.WORKER_INACTIVE:
            self._operation[shard] = WorkerPool.WORKER_DISABLED

        else:
            # We return the operation so ES can do what it needs.
            if not self._ignore[shard]:
                operation = self._operation[shard]
                priority, timestamp = self._side_data[shard]
                lost_operations.append((priority, timestamp, operation))

            # And we mark the worker as disabled (until another action
            # is taken).
            self._schedule_disabling[shard] = True
            self._ignore[shard] = True
            self.release_worker(shard)

        logger.info("Worker %s disabled.", shard)
        return lost_operations

    def enable_worker(self, shard):
        """Enable a worker that previously was disabled.

        shard (int): which worker to enable.

        raise (ValueError): if worker is not disabled.

        """
        if self._operation[shard] != WorkerPool.WORKER_DISABLED:
            err_msg = \
                "Trying to enable worker %s which is not disabled." % shard
            logger.error(err_msg)
            raise ValueError(err_msg)

        self._operation[shard] = WorkerPool.WORKER_INACTIVE
        self._workers_available_event.set()
        logger.info("Worker %s enabled.", shard)

    def check_connections(self):
        """Check if a worker we assigned an operation to disconnects. In this
        case, requeue the operation.

        return (list): list of tuples (priority, timestamp, operation)
            of operations assigned to worker that disconnected.

        """
        lost_operations = []
        for shard in self._worker:
            if not self._worker[shard].connected and \
                    self._operation[shard] not in [WorkerPool.WORKER_DISABLED,
                                                   WorkerPool.WORKER_INACTIVE]:
                if not self._ignore[shard]:
                    operation = self._operation[shard]
                    priority, timestamp = self._side_data[shard]
                    lost_operations.append((priority, timestamp, operation))
                self.release_worker(shard)

        return lost_operations


class EvaluationExecutor(Executor):
    def __init__(self, evaluation_service):
        """Create the single executor for ES.

        The executor just delegates work to the worker pool.

        """
        super(EvaluationExecutor, self).__init__()

        self.evaluation_service = evaluation_service
        self.pool = WorkerPool(self.evaluation_service)

        # QueueItem (ESOperation) we have extracted from the queue,
        # but not yet finished to execute.
        self._currently_executing = None

        # Whether execute need to drop the currently executing
        # operation.
        self._drop_current = False

        for i in xrange(get_service_shards("Worker")):
            worker = ServiceCoord("Worker", i)
            self.pool.add_worker(worker)

    def execute(self, entry):
        """Execute an operation in the queue.

        The operation might not be executed immediately because of
        lack of workers.

        entry (QueueEntry): entry containing the operation to perform.

        """
        self._currently_executing = entry.item
        side_data = (entry.priority, entry.timestamp)
        res = None
        while res is None and not self._drop_current:
            self.pool.wait_for_workers()
            if self._drop_current:
                break
            res = self.pool.acquire_worker(entry.item,
                                           side_data=side_data)
        self._drop_current = False
        self._currently_executing = None

    def dequeue(self, operation):
        """Remove an item from the queue.

        We need to override dequeue because in execute we wait for a
        worker to become available to serve the operation, and if that
        operation needed to be dequeued, we need to remove it also
        from there.

        operation (ESOperation)

        """
        try:
            super(EvaluationExecutor, self).dequeue(operation)
        except KeyError:
            if self._currently_executing == operation:
                self._drop_current = True
            else:
                raise


def with_post_finish_lock(func):
    """Decorator for locking on self.post_finish_lock.

    Ensures that no more than one decorated function is executing at
    the same time.

    """
    @wraps(func)
    def wrapped(self, *args, **kwargs):
        with self.post_finish_lock:
            return func(self, *args, **kwargs)
    return wrapped


class EvaluationService(TriggeredService):
    """Evaluation service.

    """

    MAX_COMPILATION_TRIES = 3
    MAX_EVALUATION_TRIES = 3
    MAX_USER_TEST_COMPILATION_TRIES = 3
    MAX_USER_TEST_EVALUATION_TRIES = 3

    INVALIDATE_COMPILATION = 0
    INVALIDATE_EVALUATION = 1

    # Seconds after which we declare a worker stale.
    WORKER_TIMEOUT = timedelta(seconds=600)
    # How often we check for stale workers.
    WORKER_TIMEOUT_CHECK_TIME = timedelta(seconds=300)

    # How often we check if a worker is connected.
    WORKER_CONNECTION_CHECK_TIME = timedelta(seconds=10)

    def __init__(self, shard, contest_id):
        super(EvaluationService, self).__init__(shard)

        self.contest_id = contest_id
        self.post_finish_lock = gevent.coros.RLock()

        self.scoring_service = self.connect_to(
            ServiceCoord("ScoringService", 0))

        self.add_executor(EvaluationExecutor(self))
        self.start_sweeper(117.0)

        self.add_timeout(self.check_workers_timeout, None,
                         EvaluationService.WORKER_TIMEOUT_CHECK_TIME
                         .total_seconds(),
                         immediately=False)
        self.add_timeout(self.check_workers_connection, None,
                         EvaluationService.WORKER_CONNECTION_CHECK_TIME
                         .total_seconds(),
                         immediately=False)

    def submission_enqueue_operations(self, submission, check_again=False):
        """Push in queue the operations required by a submission.

        submission (Submission): a submission.
        check_again (bool): whether to run check() on the operation.

        return (int): the number of actually enqueued operations.

        """
        new_operations = 0
        with SessionGen() as session:
            for dataset in get_datasets_to_judge(submission.task):
                # Here and in the user test evaluation, we have multiple
                # evaluate operations for a submission. It is not
                # efficient to access the database multiple times to get
                # the same objects, so we pass them from here to all
                # evaluate operations of this submission.
                extra = {
                    "session": session,
                    "dataset": dataset,
                    "submission": submission,
                    "submission_result":
                    submission.get_result_or_create(dataset)
                }
                for operation, priority, timestamp in \
                        submission_get_operations(submission, dataset):
                    new_operations += \
                        self.enqueue(operation, priority, timestamp,
                                     check_again=check_again, extra=extra)
        return new_operations

    def user_test_enqueue_operations(self, user_test, check_again=False):
        """Push in queue the operations required by a user test.

        user_test (UserTest): a user test.
        check_again (bool): whether to run check() on the operation.

        return (int): the number of actually enqueued operations.

        """
        new_operations = 0
        for dataset in get_datasets_to_judge(user_test.task):
            for operation, priority, timestamp in user_test_get_operations(
                    user_test, dataset):
                if self.enqueue(operation, priority, timestamp,
                                check_again=check_again):
                    new_operations += 1

        return new_operations

    def _missing_operations(self):
        """Look in the database for submissions that have not been compiled or
        evaluated for no good reasons. Put the missing operation in
        the queue.

        """
        counter = 0
        with SessionGen() as session:
            contest = session.query(Contest).\
                filter_by(id=self.contest_id).first()

            # Scan through submissions and user tests
            for submission in contest.get_submissions():
                counter += self.submission_enqueue_operations(submission,
                                                              check_again=True)
            for user_test in contest.get_user_tests():
                counter += self.user_test_enqueue_operations(user_test,
                                                             check_again=True)

        return counter

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
        # TODO: at the moment this counts all submission results for
        # the live datasets. It is interesting to show also numbers
        # for the datasets with autojudge, and for all datasets.
        stats = {}
        with SessionGen() as session:
            base_query = session\
                .query(func.count(SubmissionResult.submission_id))\
                .select_from(SubmissionResult)\
                .join(Dataset)\
                .join(Task, Dataset.task_id == Task.id)\
                .filter(Task.active_dataset_id == SubmissionResult.dataset_id)\
                .filter(Task.contest_id == self.contest_id)

            compiled = base_query.filter(SubmissionResult.filter_compiled())
            evaluated = compiled.filter(SubmissionResult.filter_evaluated())
            not_compiled = base_query.filter(
                not_(SubmissionResult.filter_compiled()))
            not_evaluated = compiled.filter(
                SubmissionResult.filter_compilation_succeeded(),
                not_(SubmissionResult.filter_evaluated()))

            queries = {}
            queries['compiling'] = not_compiled.filter(
                SubmissionResult.compilation_tries
                < EvaluationService.MAX_COMPILATION_TRIES)
            queries['max_compilations'] = not_compiled.filter(
                SubmissionResult.compilation_tries
                >= EvaluationService.MAX_COMPILATION_TRIES)
            queries['compilation_fail'] = base_query.filter(
                SubmissionResult.filter_compilation_failed())
            queries['evaluating'] = not_evaluated.filter(
                SubmissionResult.evaluation_tries
                < EvaluationService.MAX_EVALUATION_TRIES)
            queries['max_evaluations'] = not_evaluated.filter(
                SubmissionResult.evaluation_tries
                >= EvaluationService.MAX_EVALUATION_TRIES)
            queries['scoring'] = evaluated.filter(
                not_(SubmissionResult.filter_scored()))
            queries['scored'] = evaluated.filter(
                SubmissionResult.filter_scored())
            queries['total'] = base_query

            stats = {}
            keys = queries.keys()
            results = queries[keys[0]].union_all(
                *(queries[key] for key in keys[1:])).all()

        for i in range(len(keys)):
            stats[keys[i]] = results[i][0]
        stats['invalid'] = 2 * stats['total'] - sum(stats.itervalues())

        return stats

    @rpc_method
    def workers_status(self):
        """Returns a dictionary (indexed by shard number) whose values
        are the information about the corresponding worker. See
        WorkerPool.get_status for more details.

        returns (dict): the dict with the workers information.

        """
        return self.get_executor().pool.get_status()

    def check_workers_timeout(self):
        """We ask WorkerPool for the unresponsive workers, and we put
        again their operations in the queue.

        """
        lost_operations = self.get_executor().pool.check_timeouts()
        for priority, timestamp, operation in lost_operations:
            logger.info("Operation %s put again in the queue because of "
                        "worker timeout.", operation)
            self.enqueue(operation, priority, timestamp)
        return True

    def check_workers_connection(self):
        """We ask WorkerPool for the unconnected workers, and we put
        again their operations in the queue.

        """
        lost_operations = self.get_executor().pool.check_connections()
        for priority, timestamp, operation in lost_operations:
            logger.info("Operation %s put again in the queue because of "
                        "disconnected worker.", operation)
            self.enqueue(operation, priority, timestamp)
        return True

    def submission_busy(self, submission_id, dataset_id,
                        testcase_codename=None):
        """Check if the submission has a related operation in the queue or
        assigned to a worker.

        This might be either the compilation of the submission, or the
        evaluation of the testcase.

        submission_id (int): the id of the submission.
        dataset_id (int): the id of the dataset.
        testcase_codename (unicode|None): if not set, we will only
            check for the presence of the compilation of the
            submission.

        return (bool): True when the submission / testcase is present
            in the queue.

        """
        operations = []
        operations.append(ESOperation(
            ESOperation.COMPILATION,
            submission_id,
            dataset_id))
        if testcase_codename is not None:
            operations.append(ESOperation(
                ESOperation.EVALUATION,
                submission_id,
                dataset_id,
                testcase_codename))
        return any([operation in self.get_executor().pool
                    or operation in self.get_executor()
                    for operation in operations])

    def user_test_busy(self, user_test_id, dataset_id):
        """Check if the user test has a related operation in the queue or
        assigned to a worker.

        """
        operations = [
            ESOperation(
                ESOperation.USER_TEST_COMPILATION,
                user_test_id,
                dataset_id),
            ESOperation(
                ESOperation.USER_TEST_EVALUATION,
                user_test_id,
                dataset_id),
        ]
        return any([operations in self.get_executor().pool
                    or operation in self.get_executor()
                    for operation in operations])

    def operation_busy(self, operation):
        """Check the entity (submission or user test) related to an operation
        has other related operations in the queue or assigned to a
        worker.

        """

        if operation.type_ in (ESOperation.COMPILATION,
                               ESOperation.EVALUATION):
            return self.submission_busy(operation.object_id,
                                        operation.dataset_id,
                                        operation.testcase_codename)
        elif operation.type_ in (ESOperation.USER_TEST_COMPILATION,
                                 ESOperation.USER_TEST_EVALUATION):
            return self.user_test_busy(operation.object_id,
                                       operation.dataset_id)
        else:
            raise Exception("Wrong operation type %s" % operation.type_)

    @with_post_finish_lock
    def enqueue(self, operation, priority, timestamp, check_again=False,
                extra=None):
        """Check an operation and push it in the queue.

        Push an operation in the operation queue if the submission is
        not already in the queue or assigned to a worker. Optionally
        check that the operation is actually still to be performed by
        running check() on it.

        operation (ESOperation): the operation to put in the queue.
        priority (int): the priority of the operation.
        timestamp (datetime): the time of the submission.
        check_again (bool): whether or not to run check() on the
            operation;
        extra (dict): contains cached entities, if any, to use in check().

        return (bool): True if pushed, False if not.

        """
        if self.operation_busy(operation):
            return False
        elif check_again and not operation.check(**extra):
            return False
        else:
            # enqueue() returns the number of successful pushes.
            return super(EvaluationService, self).enqueue(
                operation, priority, timestamp) > 0

    @with_post_finish_lock
    def action_finished(self, data, plus, error=None):
        """Callback from a worker, to signal that is finished some
        action (compilation or evaluation).

        data (dict): a dictionary that describes a JobGroup instance.
        plus (tuple): the tuple (type_,
                                 object_id,
                                 dataset_id,
                                 testcase_codename,
                                 side_data=(priority, timestamp),
                                 shard_of_worker)

        """
        # Unpack the plus tuple. It's built in the RPC call to Worker's
        # execute_job_group method inside WorkerPool.acquire_worker.
        type_, object_id, dataset_id, testcase_codename, _, \
            shard = plus

        # Restore operation from its fields.
        operation = ESOperation(
            type_, object_id, dataset_id, testcase_codename)

        # We notify the pool that the worker is available again for
        # further work (no matter how the current request turned out,
        # even if the worker encountered an error). If the pool
        # informs us that the data produced by the worker has to be
        # ignored (by returning True) we interrupt the execution of
        # this method and do nothing because in that case we know the
        # operation has returned to the queue and perhaps already been
        # reassigned to another worker.
        if self.get_executor().pool.release_worker(shard):
            logger.info("Ignored result from worker %s as requested.", shard)
            return

        job_success = True
        if error is not None:
            logger.error("Received error from Worker: `%s'.", error)
            job_success = False

        else:
            try:
                job_group = JobGroup.import_from_dict(data)
            except:
                logger.error("[action_finished] Couldn't build JobGroup for "
                             "data %s.", data, exc_info=True)
                job_success = False

            else:
                if not job_group.success:
                    logger.error("Worker %s signaled action "
                                 "not successful.", shard)
                    job_success = False

        logger.info("Operation `%s' for submission %s completed. Success: %s.",
                    operation, object_id, job_success)

        # We get the submission from DB and update it.
        with SessionGen() as session:
            if type_ == ESOperation.COMPILATION:
                submission_result = SubmissionResult.get_from_id(
                    (object_id, dataset_id), session)
                if submission_result is None:
                    logger.info("[action_finished] Couldn't find "
                                "submission %d(%d) in the database. "
                                "Creating it.", object_id, dataset_id)
                    submission = Submission.get_from_id(object_id, session)
                    dataset = Dataset.get_from_id(dataset_id, session)
                    if submission is None:
                        logger.error("[action_finished] Could not find "
                                     "submission %d in the database.",
                                     object_id)
                        return
                    if dataset is None:
                        logger.error("[action_finished] Could not find "
                                     "dataset %d in the database.", dataset_id)
                        return
                    submission_result = submission.get_result_or_create(
                        dataset)

                submission_result.compilation_tries += 1

                if job_success:
                    job_group.to_submission_compilation(submission_result)

                self.compilation_ended(submission_result)

            elif type_ == ESOperation.EVALUATION:
                submission_result = SubmissionResult.get_from_id(
                    (object_id, dataset_id), session)
                if submission_result is None:
                    logger.error("[action_finished] Couldn't find "
                                 "submission %d(%d) in the database.",
                                 object_id, dataset_id)
                    return

                if job_success:
                    job_group.to_submission_evaluation(submission_result)

                # Submission evaluation will be ended only when
                # evaluation for each testcase is available.

                dataset = Dataset.get_from_id(dataset_id, session)
                if len(submission_result.evaluations) == \
                        len(dataset.testcases):
                    submission_result.set_evaluation_outcome()
                    submission_result.evaluation_tries += 1
                    self.evaluation_ended(submission_result)

            elif type_ == ESOperation.USER_TEST_COMPILATION:
                user_test_result = UserTestResult.get_from_id(
                    (object_id, dataset_id), session)
                if user_test_result is None:
                    logger.error("[action_finished] Couldn't find "
                                 "user test %d(%d) in the database.",
                                 object_id, dataset_id)
                    return

                user_test_result.compilation_tries += 1

                if job_success:
                    job_group.to_user_test_compilation(user_test_result)

                self.user_test_compilation_ended(user_test_result)

            elif type_ == ESOperation.USER_TEST_EVALUATION:
                user_test_result = UserTestResult.get_from_id(
                    (object_id, dataset_id), session)
                if user_test_result is None:
                    logger.error("[action_finished] Couldn't find "
                                 "user test %d(%d) in the database.",
                                 object_id, dataset_id)
                    return

                user_test_result.evaluation_tries += 1

                if job_success:
                    job_group.to_user_test_evaluation(user_test_result)

                self.user_test_evaluation_ended(user_test_result)

            else:
                logger.error("Invalid operation type %r.", type_)
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

        # If compilation was ok, we emit a satisfied log message.
        if submission_result.compilation_succeeded():
            logger.info("Submission %d(%d) was compiled successfully.",
                        submission_result.submission_id,
                        submission_result.dataset_id)

        # If instead submission failed compilation, we inform
        # ScoringService of the new submission. We need to commit
        # before so it has up to date information.
        elif submission_result.compilation_failed():
            logger.info("Submission %d(%d) did not compile.",
                        submission_result.submission_id,
                        submission_result.dataset_id)
            submission_result.sa_session.commit()
            self.scoring_service.new_evaluation(
                submission_id=submission_result.submission_id,
                dataset_id=submission_result.dataset_id)

        # If compilation failed for our fault, we log the error.
        elif submission_result.compilation_outcome is None:
            logger.warning("Worker failed when compiling submission "
                           "%d(%d).",
                           submission_result.submission_id,
                           submission_result.dataset_id)
            if submission_result.compilation_tries >= \
                    EvaluationService.MAX_COMPILATION_TRIES:
                logger.error("Maximum tries reached for the compilation of "
                             "submission %d(%d).",
                             submission_result.submission_id,
                             submission_result.dataset_id)

        # Otherwise, error.
        else:
            logger.error("Compilation outcome %r not recognized.",
                         submission_result.compilation_outcome)

        # Enqueue next steps to be done
        submission_result.sa_session.commit()
        self.submission_enqueue_operations(submission)

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
            logger.info("Submission %d(%d) was evaluated successfully.",
                        submission_result.submission_id,
                        submission_result.dataset_id)
            submission_result.sa_session.commit()
            self.scoring_service.new_evaluation(
                submission_id=submission_result.submission_id,
                dataset_id=submission_result.dataset_id)

        # Evaluation unsuccessful, we log the error.
        else:
            logger.warning("Worker failed when evaluating submission "
                           "%d(%d).",
                           submission_result.submission_id,
                           submission_result.dataset_id)
            if submission_result.evaluation_tries >= \
                    EvaluationService.MAX_EVALUATION_TRIES:
                logger.error("Maximum tries reached for the evaluation of "
                             "submission %d(%d).",
                             submission_result.submission_id,
                             submission_result.dataset_id)

        # Enqueue next steps to be done (e.g., if evaluation failed).
        submission_result.sa_session.commit()
        self.submission_enqueue_operations(submission)

    def user_test_compilation_ended(self, user_test_result):
        """Actions to be performed when we have a user test that has
        ended compilation. In particular: we queue evaluation if
        compilation was ok; we requeue compilation if it failed.

        user_test_result (UserTestResult): the user test result.

        """
        user_test = user_test_result.user_test
        # If compilation was ok, we emit a satisfied log message.
        if user_test_result.compilation_succeeded():
            logger.info("User test %d(%d) was compiled successfully.",
                        user_test_result.user_test_id,
                        user_test_result.dataset_id)

        # If instead user test failed compilation, we don't evaluatate.
        elif user_test_result.compilation_failed():
            logger.info("User test %d(%d) did not compile.",
                        user_test_result.user_test_id,
                        user_test_result.dataset_id)

        # If compilation failed for our fault, we log the error.
        elif not user_test_result.compiled():
            logger.warning("Worker failed when compiling user test "
                           "%d(%d).",
                           user_test_result.submission_id,
                           user_test_result.dataset_id)
            if user_test_result.compilation_tries >= \
                    EvaluationService.MAX_USER_TEST_COMPILATION_TRIES:
                logger.error("Maximum tries reached for the compilation of "
                             "user test %d(%d).",
                             user_test_result.user_test_id,
                             user_test_result.dataset_id)

        # Otherwise, error.
        else:
            logger.error("Compilation outcome %r not recognized.",
                         user_test_result.compilation_outcome)

        # Enqueue next steps to be done
        user_test_result.sa_session.commit()
        self.user_test_enqueue_operations(user_test)

    def user_test_evaluation_ended(self, user_test_result):
        """Actions to be performed when we have a user test that has
        been evaluated. In particular: we do nothing on success, we
        requeue on failure.

        user_test_result (UserTestResult): the user test result.

        """
        user_test = user_test_result.user_test

        # Evaluation successful, we emit a satisfied log message.
        if user_test_result.evaluated():
            logger.info("User test %d(%d) was evaluated successfully.",
                        user_test_result.user_test_id,
                        user_test_result.dataset_id)

        # Evaluation unsuccessful, we log the error.
        else:
            logger.warning("Worker failed when evaluating submission "
                           "%d(%d).",
                           user_test_result.submission_id,
                           user_test_result.dataset_id)
            if user_test_result.evaluation_tries >= \
                    EvaluationService.MAX_USER_TEST_EVALUATION_TRIES:
                logger.error("Maximum tries reached for the evaluation of "
                             "user test %d(%d).",
                             user_test_result.user_test_id,
                             user_test_result.dataset_id)

        # Enqueue next steps to be done (e.g., if evaluation failed).
        user_test_result.sa_session.commit()
        self.user_test_enqueue_operations(user_test)

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
                             "%d in the database.", submission_id)
                return

            self.submission_enqueue_operations(submission)

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
                             "in the database.", user_test_id)
                return

            self.user_test_enqueue_operations(user_test)

            session.commit()

    @rpc_method
    @with_post_finish_lock
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

        The data is cleared, the operations involving the submissions
        currently enqueued are deleted, and the ones already assigned to
        the workers are ignored. New appropriate operations are
        enqueued.

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
            # First we load all involved submissions.
            submissions = get_submissions(
                # Give contest_id only if all others are None.
                self.contest_id
                if {user_id, task_id, submission_id} == {None}
                else None,
                user_id, task_id, submission_id, session)

            # Then we get all relevant operations, and we remove them
            # both from the queue and from the pool (i.e., we ignore
            # the workers involved in those operations).
            operations = get_relevant_operations_(
                level, submissions, dataset_id)
            for operation in operations:
                try:
                    self.dequeue(operation)
                except KeyError:
                    pass  # Ok, the operation wasn't in the queue.
                try:
                    self.get_executor().pool.ignore_operation(operation)
                except LookupError:
                    pass  # Ok, the operation wasn't in the pool.

            # Then we find all existing results in the database, and
            # we remove them.
            submission_results = get_submission_results(
                # Give contest_id only if all others are None.
                self.contest_id
                if {user_id, task_id, submission_id, dataset_id} == {None}
                else None,
                user_id, task_id, submission_id, dataset_id, session)
            logger.info("Submission results to invalidate %s for: %d.",
                        level, len(submission_results))
            for submission_result in submission_results:
                # We invalidate the appropriate data and queue the
                # operations to recompute those data.
                if level == "compilation":
                    submission_result.invalidate_compilation()
                elif level == "evaluation":
                    submission_result.invalidate_evaluation()

            # Finally, we re-enqueue the operations for the
            # submissions.
            for submission in submissions:
                self.submission_enqueue_operations(submission)

            session.commit()

    @rpc_method
    def disable_worker(self, shard):
        """Disable a specific worker (recovering its assigned operations).

        shard (int): the shard of the worker.

        returns (bool): True if everything went well.

        """
        logger.info("Received request to disable worker %s.", shard)

        lost_operations = []
        try:
            lost_operations = self.get_executor().pool.disable_worker(shard)
        except ValueError:
            return False

        for priority, timestamp, operation in lost_operations:
            logger.info("Operation %s put again in the queue because "
                        "the worker was disabled.", operation)
            self.enqueue(operation, priority, timestamp)
        return True

    @rpc_method
    def enable_worker(self, shard):
        """Enable a specific worker.

        shard (int): the shard of the worker.

        returns (bool): True if everything went well.

        """
        logger.info("Received request to enable worker %s.", shard)
        try:
            self.get_executor().pool.enable_worker(shard)
        except ValueError:
            return False

        return True

    @rpc_method
    def queue_status(self):
        """Return the status of the queue.

        Parent method returns list of queues of each executor, but in
        EvaluationService we have only one executor, so we can just take
        the first queue.

        As evaluate operations are split by testcases, there are too
        many entries in the queue to display, so we just take only one
        operation of each (type, object_id, dataset_id)
        tuple. Generally, we will see only one evaluate operation for
        each submission in the queue status with the number of
        testcase which will be evaluated next. Moreover, we pass also
        the number of testcases in the queue.

        The entries are then ordered by priority and timestamp (the
        same criteria used to look at what to complete next).

        return ([QueueEntry]): the list with the queued elements.

        """
        entries = super(EvaluationService, self).queue_status()[0]
        entries_by_key = dict()
        for entry in entries:
            key = (str(entry["item"]["type"]),
                   str(entry["item"]["object_id"]),
                   str(entry["item"]["dataset_id"]))
            if key in entries_by_key:
                entries_by_key[key]["item"]["multiplicity"] += 1
            else:
                entries_by_key[key] = entry
                entries_by_key[key]["item"]["multiplicity"] = 1
        return sorted(
            entries_by_key.values(),
            lambda x, y: cmp((x["priority"], x["timestamp"]),
                             (y["priority"], y["timestamp"])))
