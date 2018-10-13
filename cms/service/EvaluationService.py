#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013-2015 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2016 Luca Versari <veluca93@gmail.com>
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

import logging
from collections import defaultdict
from datetime import timedelta
from functools import wraps

import gevent.lock
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from cms import ServiceCoord, get_service_shards
from cms.db import SessionGen, Digest, Dataset, Evaluation, Submission, \
    SubmissionResult, Testcase, UserTest, UserTestResult, get_submissions, \
    get_submission_results, get_datasets_to_judge
from cms.grading.Job import JobGroup
from cms.io import Executor, TriggeredService, rpc_method
from .esoperations import ESOperation, get_relevant_operations, \
    get_submissions_operations, get_user_tests_operations, \
    submission_get_operations, submission_to_evaluate, \
    user_test_get_operations
from .flushingdict import FlushingDict
from .workerpool import WorkerPool


logger = logging.getLogger(__name__)


class EvaluationExecutor(Executor):

    # Real maximum number of operations to be sent to a worker.
    MAX_OPERATIONS_PER_BATCH = 25

    def __init__(self, evaluation_service):
        """Create the single executor for ES.

        The executor just delegates work to the worker pool.

        """
        super().__init__(True)

        self.evaluation_service = evaluation_service
        self.pool = WorkerPool(self.evaluation_service)

        # List of QueueItem (ESOperation) we have extracted from the
        # queue, but not yet finished to execute.
        self._currently_executing = []

        # Lock used to guard the currently executing operations
        self._current_execution_lock = gevent.lock.RLock()

        for i in range(get_service_shards("Worker")):
            worker = ServiceCoord("Worker", i)
            self.pool.add_worker(worker)

    def __contains__(self, item):
        """Return whether the item is in execution.

        item (QueueItem): an item to search.

        return (bool): True if item is in the queue, or if it is the
            item already extracted but not given to the workers yet,
            or if it is being executed by a worker.

        """
        return (super().__contains__(item)
                or item in self._currently_executing
                or item in self.pool)

    def max_operations_per_batch(self):
        """Return the maximum number of operations per batch.

        We derive the number from the length of the queue divided by
        the number of workers, with a cap at MAX_OPERATIONS_PER_BATCH.

        """
        # TODO: len(self.pool) is the total number of workers,
        # included those that are disabled.
        ratio = len(self._operation_queue) // len(self.pool) + 1
        ret = min(max(ratio, 1), EvaluationExecutor.MAX_OPERATIONS_PER_BATCH)
        logger.info("Ratio is %d, executing %d operations together.",
                    ratio, ret)
        return ret

    def execute(self, entries):
        """Execute a batch of operations in the queue.

        The operations might not be executed immediately because of
        lack of workers.

        entries ([QueueEntry]): entries containing the operations to
            perform.

        """
        with self._current_execution_lock:
            self._currently_executing = []
            for entry in entries:
                operation = entry.item
                # Side data is attached to the operation sent to the
                # worker pool. In case the operation is lost, the pool
                # will return it to us, and we will use it to
                # re-enqueue it.
                operation.side_data = (entry.priority, entry.timestamp)
                self._currently_executing.append(operation)
        while self._currently_executing:
            self.pool.wait_for_workers()
            with self._current_execution_lock:
                if not self._currently_executing:
                    break
                res = self.pool.acquire_worker(self._currently_executing)
                if res is not None:
                    self._currently_executing = []
                    break

    def dequeue(self, operation):
        """Remove an item from the queue.

        We need to override dequeue because the operation to dequeue
        might have already been extracted, but not yet executed.

        operation (ESOperation)

        """
        try:
            super().dequeue(operation)
        except KeyError:
            with self._current_execution_lock:
                for i in range(len(self._currently_executing)):
                    if self._currently_executing[i] == operation:
                        del self._currently_executing[i]
                        return
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


class Result:
    """An object grouping the results obtained from a worker for an
    operation.

    """

    def __init__(self, job, job_success):
        self.job = job
        self.job_success = job_success


class EvaluationService(TriggeredService):
    """Evaluation service.

    """

    # TODO: these constants should be in a more general place.
    MAX_COMPILATION_TRIES = 3
    MAX_EVALUATION_TRIES = 3
    MAX_USER_TEST_COMPILATION_TRIES = 3
    MAX_USER_TEST_EVALUATION_TRIES = 3

    INVALIDATE_COMPILATION = 0
    INVALIDATE_EVALUATION = 1

    # How often we check for stale workers.
    WORKER_TIMEOUT_CHECK_TIME = timedelta(seconds=300)

    # How often we check if a worker is connected.
    WORKER_CONNECTION_CHECK_TIME = timedelta(seconds=10)

    # How many worker results we accumulate before processing them.
    RESULT_CACHE_SIZE = 100
    # The maximum time since the last result before processing.
    MAX_FLUSHING_TIME_SECONDS = 2

    def __init__(self, shard, contest_id=None):
        super().__init__(shard)

        self.contest_id = contest_id

        # Cache holding the results from the worker until they are
        # written to the DB.
        self.result_cache = FlushingDict(
            EvaluationService.RESULT_CACHE_SIZE,
            EvaluationService.MAX_FLUSHING_TIME_SECONDS,
            self.write_results)

        # This lock is used to avoid inserting in the queue (which
        # itself is already thread-safe) an operation which is already
        # being processed. Such operation might be in one of the
        # following state:
        # 1. in the queue;
        # 2. extracted from the queue by the executor, but not yet
        #    dispatched to a worker;
        # 3. being processed by a worker ("in the worker pool");
        # 4. being processed by action_finished, but with the results
        #    not yet written to the database.
        # 5. with results written in the database.
        #
        # The methods enqueuing operations already check that the
        # operation is not in state 5, and enqueue() checks that it is
        # not in the first three states.
        #
        # Therefore, the lock guarantees that the methods adding
        # operations to the queue (_missing_operations,
        # invalidate_submission, enqueue) are not executed
        # concurrently with action_finished to avoid picking
        # operations in state 4.
        self.post_finish_lock = gevent.lock.RLock()

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

    def submission_enqueue_operations(self, submission):
        """Push in queue the operations required by a submission.

        submission (Submission): a submission.

        return (int): the number of actually enqueued operations.

        """
        new_operations = 0
        for dataset in get_datasets_to_judge(submission.task):
            submission_result = submission.get_result(dataset)
            number_of_operations = 0
            for operation, priority, timestamp in submission_get_operations(
                    submission_result, submission, dataset):
                number_of_operations += 1
                if self.enqueue(operation, priority, timestamp):
                    new_operations += 1

            # If we got 0 operations, but the submission result is to
            # evaluate, it means that we just need to finalize the
            # evaluation.
            if number_of_operations == 0 and submission_to_evaluate(
                    submission_result):
                logger.info("Result %d(%d) has already all evaluations, "
                            "finalizing it.", submission.id, dataset.id)
                submission_result.set_evaluation_outcome()
                submission_result.sa_session.commit()
                self.evaluation_ended(submission_result)

        return new_operations

    def user_test_enqueue_operations(self, user_test):
        """Push in queue the operations required by a user test.

        user_test (UserTest): a user test.

        return (int): the number of actually enqueued operations.

        """
        new_operations = 0
        for dataset in get_datasets_to_judge(user_test.task):
            for operation, priority, timestamp in user_test_get_operations(
                    user_test, dataset):
                if self.enqueue(operation, priority, timestamp):
                    new_operations += 1

        return new_operations

    @with_post_finish_lock
    def _missing_operations(self):
        """Look in the database for submissions that have not been compiled or
        evaluated for no good reasons. Put the missing operation in
        the queue.

        """
        counter = 0
        with SessionGen() as session:

            for operation, timestamp, priority in \
                    get_submissions_operations(session, self.contest_id):
                if self.enqueue(operation, timestamp, priority):
                    counter += 1

            for operation, timestamp, priority in \
                    get_user_tests_operations(session, self.contest_id):
                if self.enqueue(operation, timestamp, priority):
                    counter += 1

        return counter

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
        for operation in lost_operations:
            logger.info("Operation %s put again in the queue because of "
                        "worker timeout.", operation)
            priority, timestamp = operation.side_data
            self.enqueue(operation, priority, timestamp)
        return True

    def check_workers_connection(self):
        """We ask WorkerPool for the unconnected workers, and we put
        again their operations in the queue.

        """
        lost_operations = self.get_executor().pool.check_connections()
        for operation in lost_operations:
            logger.info("Operation %s put again in the queue because of "
                        "disconnected worker.", operation)
            priority, timestamp = operation.side_data
            self.enqueue(operation, priority, timestamp)
        return True

    @with_post_finish_lock
    def enqueue(self, operation, priority, timestamp):
        """Push an operation in the queue.

        Push an operation in the operation queue if the submission is
        not already in the queue or assigned to a worker.

        operation (ESOperation): the operation to put in the queue.
        priority (int): the priority of the operation.
        timestamp (datetime): the time of the submission.

        return (bool): True if pushed, False if not.

        """
        if operation in self.get_executor() or operation in self.result_cache:
            return False

        # enqueue() returns the number of successful pushes.
        return super().enqueue(operation, priority, timestamp) > 0

    @with_post_finish_lock
    def action_finished(self, data, shard, error=None):
        """Callback from a worker, to signal that is finished some
        action (compilation or evaluation).

        data (dict): the JobGroup, exported to dict.
        shard (int): the shard finishing the action.

        """
        # We notify the pool that the worker is available again for
        # further work (no matter how the current request turned out,
        # even if the worker encountered an error). If the pool
        # informs us that the data produced by the worker has to be
        # ignored (by returning True) we interrupt the execution of
        # this method and do nothing because in that case we know the
        # operation has returned to the queue and perhaps already been
        # reassigned to another worker.
        to_ignore = self.get_executor().pool.release_worker(shard)
        if to_ignore is True:
            logger.info("Ignored result from worker %s as requested.", shard)
            return

        job_group = None
        job_group_success = True
        if error is not None:
            logger.error(
                "Received error from Worker (see above), job group lost.")
            job_group_success = False

        else:
            try:
                job_group = JobGroup.import_from_dict(data)
            except Exception:
                logger.error("Couldn't build JobGroup for data %s.", data,
                             exc_info=True)
                job_group_success = False

        if job_group_success:
            for job in job_group.jobs:
                operation = job.operation
                if job.success:
                    logger.info("`%s' succeeded.", operation)
                else:
                    logger.error("`%s' failed, see worker logs and (possibly) "
                                 "sandboxes at '%s'.",
                                 operation, " ".join(job.sandboxes))
                if isinstance(to_ignore, list) and operation in to_ignore:
                    logger.info("`%s' result ignored as requested", operation)
                else:
                    self.result_cache.add(operation, Result(job, job.success))

    @with_post_finish_lock
    def write_results(self, items):
        """Receive worker results from the cache and writes them to the DB.

        Grouping results together by object (i.e., submission result
        or user test result) and type (compilation or evaluation)
        allows this method to talk less to the DB, for example by
        retrieving datasets and submission results only once instead
        of once for every result.

        items ([(operation, Result)]): the results received by ES but
            not yet written to the db.

        """
        logger.info("Starting commit process...")

        # Reorganize the results by submission/usertest result and
        # operation type (i.e., group together the testcase
        # evaluations for the same submission and dataset).
        by_object_and_type = defaultdict(list)
        for operation, result in items:
            t = (operation.type_, operation.object_id, operation.dataset_id)
            by_object_and_type[t].append((operation, result))

        with SessionGen() as session:
            for key, operation_results in by_object_and_type.items():
                type_, object_id, dataset_id = key

                dataset = Dataset.get_from_id(dataset_id, session)
                if dataset is None:
                    logger.error("Could not find dataset %d in the database.",
                                 dataset_id)
                    continue

                # Get submission or user test results.
                if type_ in [ESOperation.COMPILATION, ESOperation.EVALUATION]:
                    object_ = Submission.get_from_id(object_id, session)
                    if object_ is None:
                        logger.error("Could not find submission %d "
                                     "in the database.", object_id)
                        continue
                    object_result = object_.get_result_or_create(dataset)
                else:
                    object_ = UserTest.get_from_id(object_id, session)
                    if object_ is None:
                        logger.error("Could not find user test %d "
                                     "in the database.", object_id)
                        continue
                    object_result = object_.get_result_or_create(dataset)

                self.write_results_one_object_and_type(
                    session, object_result, operation_results)

            logger.info("Committing evaluations...")
            session.commit()

            num_testcases_per_dataset = dict()
            for type_, object_id, dataset_id in by_object_and_type.keys():
                if type_ == ESOperation.EVALUATION:
                    if dataset_id not in num_testcases_per_dataset:
                        num_testcases_per_dataset[dataset_id] = session\
                            .query(func.count(Testcase.id))\
                            .filter(Testcase.dataset_id == dataset_id).scalar()
                    num_evaluations = session\
                        .query(func.count(Evaluation.id)) \
                        .filter(Evaluation.dataset_id == dataset_id) \
                        .filter(Evaluation.submission_id == object_id).scalar()
                    if num_evaluations == num_testcases_per_dataset[dataset_id]:
                        submission_result = SubmissionResult.get_from_id(
                            (object_id, dataset_id), session)
                        submission_result.set_evaluation_outcome()

            logger.info("Committing evaluation outcomes...")
            session.commit()

            logger.info("Ending operations for %s objects...",
                        len(by_object_and_type))
            for type_, object_id, dataset_id in by_object_and_type.keys():
                if type_ == ESOperation.COMPILATION:
                    submission_result = SubmissionResult.get_from_id(
                        (object_id, dataset_id), session)
                    self.compilation_ended(submission_result)
                elif type_ == ESOperation.EVALUATION:
                    submission_result = SubmissionResult.get_from_id(
                        (object_id, dataset_id), session)
                    if submission_result.evaluated():
                        self.evaluation_ended(submission_result)
                elif type_ == ESOperation.USER_TEST_COMPILATION:
                    user_test_result = UserTestResult.get_from_id(
                        (object_id, dataset_id), session)
                    self.user_test_compilation_ended(user_test_result)
                elif type_ == ESOperation.USER_TEST_EVALUATION:
                    user_test_result = UserTestResult.get_from_id(
                        (object_id, dataset_id), session)
                    self.user_test_evaluation_ended(user_test_result)

        logger.info("Done")

    def write_results_one_object_and_type(
            self, session, object_result, operation_results):
        """Write to the DB the results for one object and type.

        session (Session): the DB session to use.
        object_result (SubmissionResult|UserTestResult): the DB object
            for the result referred to all the ESOperations.
        operation_results ([(ESOperation, WorkerResult)]): all the
            operations and corresponding worker results we have
            received for the given object_result

        """
        for operation, result in operation_results:
            logger.info("Writing result to db for %s", operation)
            try:
                with session.begin_nested():
                    self.write_results_one_row(
                        session, object_result, operation, result)
            except IntegrityError:
                logger.warning(
                    "Integrity error while inserting worker result.",
                    exc_info=True)
            except Exception:
                # Defend against any exception. A poisonous results that fails
                # here is attempted again without limits, thus can enter in
                # all batches to write. Without the catch-all, it will prevent
                # the whole batch to be written over and over. See issue #888.
                logger.error(
                    "Unexpected exception while inserting worker result.",
                    exc_info=True)

    def write_results_one_row(self, session, object_result, operation, result):
        """Write to the DB a single result.

        session (Session): the DB session to use.
        object_result (SubmissionResult|UserTestResult): the DB object
            for the operation (and for the result).
        operation (ESOperation): the operation for which we have the result.
        result (WorkerResult): the result from the worker.

        """
        if operation.type_ == ESOperation.COMPILATION:
            if result.job_success:
                result.job.to_submission(object_result)
            else:
                object_result.compilation_tries += 1

        elif operation.type_ == ESOperation.EVALUATION:
            if result.job_success:
                result.job.to_submission(object_result)
            else:
                if result.job.plus is not None and \
                   result.job.plus.get("tombstone") is True:
                    executable_digests = [
                        e.digest for e in
                        object_result.executables.values()]
                    if Digest.TOMBSTONE in executable_digests:
                        logger.info("Submission %d's compilation on dataset "
                                    "%d has been invalidated since the "
                                    "executable was the tombstone",
                                    object_result.submission_id,
                                    object_result.dataset_id)
                        with session.begin_nested():
                            object_result.invalidate_compilation()
                        self.submission_enqueue_operations(
                            object_result.submission)
                else:
                    object_result.evaluation_tries += 1

        elif operation.type_ == ESOperation.USER_TEST_COMPILATION:
            if result.job_success:
                result.job.to_user_test(object_result)
            else:
                object_result.compilation_tries += 1

        elif operation.type_ == ESOperation.USER_TEST_EVALUATION:
            if result.job_success:
                result.job.to_user_test(object_result)
            else:
                object_result.evaluation_tries += 1

        else:
            logger.error("Invalid operation type %r.", operation.type_)

    def compilation_ended(self, submission_result):
        """Actions to be performed when we have a submission that has
        ended compilation. In particular: we queue evaluation if
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
                logger.error("Maximum number of failures reached for the "
                             "compilation of submission %d(%d).",
                             submission_result.submission_id,
                             submission_result.dataset_id)

        # Otherwise, error.
        else:
            logger.error("Compilation outcome %r not recognized.",
                         submission_result.compilation_outcome)

        # Enqueue next steps to be done
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
                logger.error("Maximum number of failures reached for the "
                             "evaluation of submission %d(%d).",
                             submission_result.submission_id,
                             submission_result.dataset_id)

        # Enqueue next steps to be done (e.g., if evaluation failed).
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
                           user_test_result.user_test_id,
                           user_test_result.dataset_id)
            if user_test_result.compilation_tries >= \
                    EvaluationService.MAX_USER_TEST_COMPILATION_TRIES:
                logger.error("Maximum number of failures reached for the "
                             "compilation of user test %d(%d).",
                             user_test_result.user_test_id,
                             user_test_result.dataset_id)

        # Otherwise, error.
        else:
            logger.error("Compilation outcome %r not recognized.",
                         user_test_result.compilation_outcome)

        # Enqueue next steps to be done
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
                           user_test_result.user_test_id,
                           user_test_result.dataset_id)
            if user_test_result.evaluation_tries >= \
                    EvaluationService.MAX_USER_TEST_EVALUATION_TRIES:
                logger.error("Maximum number of failures reached for the "
                             "evaluation of user test %d(%d).",
                             user_test_result.user_test_id,
                             user_test_result.dataset_id)

        # Enqueue next steps to be done (e.g., if evaluation failed).
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
                              contest_id=None,
                              submission_id=None,
                              dataset_id=None,
                              participation_id=None,
                              task_id=None,
                              level="compilation"):
        """Request to invalidate some computed data.

        Invalidate the compilation and/or evaluation data of the
        SubmissionResults that:
        - belong to submission_id or, if None, to any submission of
          participation_id and/or task_id or, if both None, to any
          submission of the contest asked for, or, if all three are
          None, the contest this service is running for (or all contests).
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
        participation_id (int|None): id of the participation to
            invalidate, or None.
        task_id (int|None): id of the task to invalidate, or None.
        level (string): 'compilation' or 'evaluation'

        """
        logger.info("Invalidation request received.")

        # Validate arguments
        # TODO Check that all these objects belong to this contest.
        if level not in ("compilation", "evaluation"):
            raise ValueError(
                "Unexpected invalidation level `%s'." % level)

        if contest_id is None:
            contest_id = self.contest_id

        with SessionGen() as session:
            # When invalidating a dataset we need to know the task_id,
            # otherwise get_submissions will return all the submissions of
            # the contest.
            if dataset_id is not None and task_id is None \
                    and submission_id is None:
                task_id = Dataset.get_from_id(dataset_id, session).task_id
            # First we load all involved submissions.
            submissions = get_submissions(
                session,
                # Give contest_id only if all others are None.
                contest_id
                if {participation_id, task_id, submission_id} == {None}
                else None,
                participation_id, task_id, submission_id).all()

            # Then we get all relevant operations, and we remove them
            # both from the queue and from the pool (i.e., we ignore
            # the workers involved in those operations).
            operations = get_relevant_operations(
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
                session,
                # Give contest_id only if all others are None.
                contest_id
                if {participation_id,
                    task_id,
                    submission_id,
                    dataset_id} == {None}
                else None,
                participation_id,
                # Provide the task_id only if the entire task has to be
                # reevaluated and not only a specific dataset.
                task_id if dataset_id is None else None,
                submission_id, dataset_id).all()
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
        logger.info("Invalidate successfully completed.")

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

        for operation in lost_operations:
            logger.info("Operation %s put again in the queue because "
                        "the worker was disabled.", operation)
            priority, timestamp = operation.side_data
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
        entries = super().queue_status()[0]
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
            key=lambda x: (x["priority"], x["timestamp"]))
