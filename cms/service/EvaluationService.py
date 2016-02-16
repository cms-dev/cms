#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2016 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013-2015 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

from datetime import timedelta
from functools import wraps

import gevent.coros

from sqlalchemy import func, not_

from cms import ServiceCoord, get_service_shards
from cms.io import Executor, TriggeredService, rpc_method
from cms.db import SessionGen, Dataset, Submission, \
    SubmissionResult, Task, UserTest
from cms.service import get_datasets_to_judge, \
    get_submissions, get_submission_results
from cms.grading.Job import Job

from .esoperations import ESOperation, get_relevant_operations, \
    get_submissions_operations, get_user_tests_operations, \
    submission_get_operations, submission_to_evaluate, \
    user_test_get_operations
from .workerpool import WorkerPool


logger = logging.getLogger(__name__)


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

    def __contains__(self, item):
        """Return whether the item is in execution.

        item (QueueItem): an item to search.

        return (bool): True if item is in the queue, or if it is the
            item already extracted but not given to the workers yet,
            or if it is being executed by a worker.

        """
        return super(EvaluationExecutor, self).__contains__(item) or \
            self._currently_executing == item or \
            item in self.pool

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

    # How often we check for stale workers.
    WORKER_TIMEOUT_CHECK_TIME = timedelta(seconds=300)

    # How often we check if a worker is connected.
    WORKER_CONNECTION_CHECK_TIME = timedelta(seconds=10)

    def __init__(self, shard, contest_id):
        super(EvaluationService, self).__init__(shard)

        self.contest_id = contest_id

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
                SubmissionResult.compilation_tries <
                EvaluationService.MAX_COMPILATION_TRIES)
            queries['max_compilations'] = not_compiled.filter(
                SubmissionResult.compilation_tries >=
                EvaluationService.MAX_COMPILATION_TRIES)
            queries['compilation_fail'] = base_query.filter(
                SubmissionResult.filter_compilation_failed())
            queries['evaluating'] = not_evaluated.filter(
                SubmissionResult.evaluation_tries <
                EvaluationService.MAX_EVALUATION_TRIES)
            queries['max_evaluations'] = not_evaluated.filter(
                SubmissionResult.evaluation_tries >=
                EvaluationService.MAX_EVALUATION_TRIES)
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
        return any([operation in self.get_executor()
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
        return any([operation in self.get_executor()
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
    def enqueue(self, operation, priority, timestamp):
        """Push an operation in the queue.

        Push an operation in the operation queue if the submission is
        not already in the queue or assigned to a worker.

        operation (ESOperation): the operation to put in the queue.
        priority (int): the priority of the operation.
        timestamp (datetime): the time of the submission.

        return (bool): True if pushed, False if not.

        """
        if self.operation_busy(operation):
            return False

        # enqueue() returns the number of successful pushes.
        return super(EvaluationService, self).enqueue(
            operation, priority, timestamp) > 0

    @with_post_finish_lock
    def action_finished(self, data, plus, error=None):
        """Callback from a worker, to signal that is finished some
        action (compilation or evaluation).

        data (dict): a dictionary that describes a Job instance.
        plus (tuple): the tuple (type_,
                                 object_id,
                                 dataset_id,
                                 testcase_codename,
                                 side_data=(priority, timestamp),
                                 shard_of_worker)

        """
        # Unpack the plus tuple. It's built in the RPC call to Worker's
        # execute_job method inside WorkerPool.acquire_worker.
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
                job = Job.import_from_dict_with_type(data)
            except:
                logger.error("Couldn't build Job for data %s.", data,
                             exc_info=True)
                job_success = False

            else:
                if not job.success:
                    logger.error("Worker %s signaled action not successful.",
                                 shard)
                    job_success = False

        logger.info("`%s' completed. Success: %s.", operation, job_success)

        # We get the submission from DB and update it.
        with SessionGen() as session:
            dataset = Dataset.get_from_id(dataset_id, session)
            if dataset is None:
                logger.error("Could not find dataset %d in the database.",
                             dataset_id)
                return

            # TODO Try to move this 4-cases if-clause into a method of
            # ESOperation: I'd really like ES itself not to care about
            # which type of operation it's handling.
            if type_ == ESOperation.COMPILATION:
                submission = Submission.get_from_id(object_id, session)
                if submission is None:
                    logger.error("Could not find submission %d "
                                 "in the database.", object_id)
                    return

                submission_result = submission.get_result(dataset)
                if submission_result is None:
                    logger.info("Couldn't find submission %d(%d) "
                                "in the database. Creating it.",
                                object_id, dataset_id)
                    submission_result = \
                        submission.get_result_or_create(dataset)

                if job_success:
                    job.to_submission(submission_result)
                else:
                    submission_result.compilation_tries += 1

                session.commit()

                self.compilation_ended(submission_result)

            elif type_ == ESOperation.EVALUATION:
                submission = Submission.get_from_id(object_id, session)
                if submission is None:
                    logger.error("Could not find submission %d "
                                 "in the database.", object_id)
                    return

                submission_result = submission.get_result(dataset)
                if submission_result is None:
                    logger.error("Couldn't find submission %d(%d) "
                                 "in the database.", object_id, dataset_id)
                    return

                if job_success:
                    job.to_submission(submission_result)
                else:
                    submission_result.evaluation_tries += 1

                # Submission evaluation will be ended only when
                # evaluation for each testcase is available.
                evaluation_complete = (len(submission_result.evaluations) ==
                                       len(dataset.testcases))
                if evaluation_complete:
                    submission_result.set_evaluation_outcome()

                session.commit()

                if evaluation_complete:
                    self.evaluation_ended(submission_result)

            elif type_ == ESOperation.USER_TEST_COMPILATION:
                user_test = UserTest.get_from_id(object_id, session)
                if user_test is None:
                    logger.error("Could not find user test %d "
                                 "in the database.", object_id)
                    return

                user_test_result = user_test.get_result(dataset)
                if user_test_result is None:
                    logger.error("Couldn't find user test %d(%d) "
                                 "in the database. Creating it.",
                                 object_id, dataset_id)
                    user_test_result = \
                        user_test.get_result_or_create(dataset)

                if job_success:
                    job.to_user_test(user_test_result)
                else:
                    user_test_result.compilation_tries += 1

                session.commit()

                self.user_test_compilation_ended(user_test_result)

            elif type_ == ESOperation.USER_TEST_EVALUATION:
                user_test = UserTest.get_from_id(object_id, session)
                if user_test is None:
                    logger.error("Could not find user test %d "
                                 "in the database.", object_id)
                    return

                user_test_result = user_test.get_result(dataset)
                if user_test_result is None:
                    logger.error("Couldn't find user test %d(%d) "
                                 "in the database.", object_id, dataset_id)
                    return

                if job_success:
                    job.to_user_test(user_test_result)
                else:
                    user_test_result.evaluation_tries += 1

                session.commit()

                self.user_test_evaluation_ended(user_test_result)

            else:
                logger.error("Invalid operation type %r.", type_)
                return

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
                           user_test_result.submission_id,
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
                           user_test_result.submission_id,
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
          submission of the contest this service is running for.
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

        with SessionGen() as session:
            # First we load all involved submissions.
            submissions = get_submissions(
                # Give contest_id only if all others are None.
                self.contest_id
                if {participation_id, task_id, submission_id} == {None}
                else None,
                participation_id, task_id, submission_id, session)

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
                # Give contest_id only if all others are None.
                self.contest_id
                if {participation_id,
                    task_id,
                    submission_id,
                    dataset_id} == {None}
                else None,
                participation_id, task_id, submission_id, dataset_id, session)
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
