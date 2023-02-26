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
from functools import wraps

import gevent.lock
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from cms import ServiceCoord
from cmscommon.datetime import make_timestamp
from cms.db import SessionGen, Digest, Dataset, Evaluation, Submission, \
    SubmissionResult, Testcase, UserTest, UserTestResult, get_datasets_to_judge
from cms.grading.Job import Job
from cms.io import Service, rpc_method
from .esoperations import ESOperation, \
    submission_get_operations, submission_to_evaluate, \
    user_test_get_operations


logger = logging.getLogger(__name__)

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


class EvaluationService(Service):
    """Evaluation service.

    """

    # TODO: these constants should be in a more general place.
    MAX_COMPILATION_TRIES = 3
    MAX_EVALUATION_TRIES = 3
    MAX_USER_TEST_COMPILATION_TRIES = 3
    MAX_USER_TEST_EVALUATION_TRIES = 3

    INVALIDATE_COMPILATION = 0
    INVALIDATE_EVALUATION = 1

    def __init__(self, shard, contest_id=None):
        super().__init__(shard)

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
        self.post_finish_lock = gevent.lock.RLock()

        self.queue_service = self.connect_to(
            ServiceCoord("QueueService", 0))
        self.scoring_service = self.connect_to(
            ServiceCoord("ScoringService", 0))

    def get_submission_operations(self, submission):
        """Push in queue the operations required by a submission.

        submission (Submission): a submission.

        return ([ESOperation, int, datetime]): operations to enqueue, together
            with priority and timestamp.

        """
        operations = []
        for dataset in get_datasets_to_judge(submission.task):
            submission_result = submission.get_result(dataset)
            number_of_operations = 0
            for operation, priority, timestamp in submission_get_operations(
                    submission_result, submission, dataset):
                number_of_operations += 1
                operations.append([operation, priority, timestamp])

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

        return operations

    def get_user_test_operations(self, user_test):
        """Push in queue the operations required by a user test.

        user_test (UserTest): a user test.

        return ([ESOperation, int, datetime]): operations to enqueue, together
            with priority and timestamp.

        """
        operations = []
        for dataset in get_datasets_to_judge(user_test.task):
            for operation, priority, timestamp in user_test_get_operations(
                    user_test, dataset):
                operations.append([operation, priority, timestamp])

        return operations

    @with_post_finish_lock
    def enqueue_all(self, operations):
        """Enqueue all the operations

        operations ([ESOperation, int, datetime]): operations, priorities,
            timestamps

        """
        for operation, priority, timestamp in operations:
            self.enqueue(operation, priority, timestamp)

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
        return self.queue_service.enqueue(
            operation=operation.to_dict(),
            priority=priority,
            timestamp=make_timestamp(timestamp))

    @with_post_finish_lock
    @rpc_method
    def write_single_result(self, operation, job):
        """Receive worker results from QS and writes them to the DB.

        operation (ESOperation|dict): operation performed, exported as dict
        job (Job|dict): job containing the result, exported as dict

        """

        logger.debug("Starting commit process...")
        if isinstance(operation, dict):
            operation = ESOperation.from_dict(operation)
        if isinstance(job, dict):
            job = Job.import_from_dict_with_type(job)

        with SessionGen() as session:
            type_ = operation.type_
            object_id = operation.object_id
            dataset_id = operation.dataset_id

            dataset = Dataset.get_from_id(dataset_id, session)
            if dataset is None:
                logger.error("Could not find dataset %d in the database.",
                             dataset_id)
                return False

            # Get submission or user test, and their results.
            if type_ in [ESOperation.COMPILATION, ESOperation.EVALUATION]:
                object_ = Submission.get_from_id(object_id, session)
                if object_ is None:
                    logger.error("Could not find submission %d "
                                 "in the database.", object_id)
                    return False
                object_result = object_.get_result_or_create(dataset)
            else:
                object_ = UserTest.get_from_id(object_id, session)
                object_result = object_.get_result_or_create(dataset)

            logger.info("Writing result to db for %s", operation)
            try:
                result_is_valid = self.write_results_one_row(
                    session, object_result, operation, job)
            except IntegrityError:
                logger.warning(
                    "Integrity error while inserting worker result.",
                    exc_info=True)
                # This is not an error condition, as the result is already
                # in the DB.
                return False
            except Exception:
                # Defend against any exception. A poisonous results that fails
                # here is attempted again without limits, thus can enter in
                # all batches to write. Without the catch-all, it will prevent
                # the whole batch to be written over and over. See issue #888.
                logger.error(
                    "Unexpected exception while inserting worker result.",
                    exc_info=True)
                return False

            logger.debug("Committing evaluations...")
            session.commit()

            # If we are not successful, it means we had to invalidate the submission.
            # We return immediately signaling that the queue should be populated with
            # next steps for this submission.
            if not result_is_valid:
                return True

            if type_ == ESOperation.EVALUATION:
                if len(object_result.evaluations) == len(dataset.testcases):
                    object_result.set_evaluation_outcome()

            logger.debug("Committing evaluation outcomes...")
            session.commit()

            logger.info("Ending operations...")
            if type_ == ESOperation.COMPILATION:
                self.compilation_ended(object_result)
            elif type_ == ESOperation.EVALUATION:
                if object_result.evaluated():
                    self.evaluation_ended(object_result)
            elif type_ == ESOperation.USER_TEST_COMPILATION:
                self.user_test_compilation_ended(object_result)
            elif type_ == ESOperation.USER_TEST_EVALUATION:
                self.user_test_evaluation_ended(object_result)
        return True

    def enqueue_next_steps_for_operation(self, operation):
        logger.debug("Adding next steps to queue...")
        if isinstance(operation, dict):
            operation = ESOperation.from_dict(operation)

        with SessionGen() as session:
            type_ = operation.type_
            object_id = operation.object_id
            if type_ in [ESOperation.COMPILATION, ESOperation.EVALUATION]:
                object_ = Submission.get_from_id(object_id, session)
                if object_ is None:
                    logger.error("Could not find submission %d "
                                 "in the database.", object_id)
                    return False
                self.enqueue_all(self.get_submission_operations(object_))
            else:
                object_ = UserTest.get_from_id(object_id, session)
                self.enqueue_all(self.get_user_test_operations(object_))

    @with_post_finish_lock
    @rpc_method
    def write_results(self, items):
        """Receive worker results from the cache and writes them to the DB.

        Grouping results together by object (i.e., submission result
        or user test result) and type (compilation or evaluation)
        allows this method to talk less to the DB, for example by
        retrieving datasets and submission results only once instead
        of once for every result.

        items ([(operation: dict, job: dict)]): the results received by ES but
            not yet written to the db.

        """
        logger.info("Starting commit process...")

        # Reorganize the results by submission/usertest result and
        # operation type (i.e., group together the testcase
        # evaluations for the same submission and dataset).
        by_object_and_type = defaultdict(list)
        new_operations = []
        for operation, job in items:
            operation = ESOperation.from_dict(operation)
            job = Job.import_from_dict_with_type(job)
            t = (operation.type_, operation.object_id, operation.dataset_id)
            by_object_and_type[t].append((operation, job))

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

                new_operations += self.write_results_one_object_and_type(
                    session, object_result, operation_results)

            logger.info("Committing evaluations...")
            session.commit()

            num_testcases_per_dataset = dict()
            for type_, object_id, dataset_id in by_object_and_type.keys():
                if type_ == ESOperation.EVALUATION:
                    if dataset_id not in num_testcases_per_dataset:
                        num_testcases_per_dataset[dataset_id] = session \
                            .query(func.count(Testcase.id)) \
                            .filter(Testcase.dataset_id == dataset_id).scalar()
                    num_evaluations = session \
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
        return True, [
            [op.to_dict(),
             priority,
             make_timestamp(timestamp)]
            for op, priority, timestamp in new_operations]

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
        new_operations = []
        for operation, result in operation_results:
            logger.info("Writing result to db for %s", operation)
            try:
                with session.begin_nested():
                    new_operations += self.write_results_one_row(
                        session, object_result, operation, result)
            except IntegrityError:
                logger.warning(
                    "Integrity error while inserting worker result.",
                    exc_info=True)
        return new_operations

    def write_results_one_row(self, session, object_result, operation, job):
        """Write to the DB a single result.

        session (Session): the DB session to use.
        object_result (SubmissionResult|UserTestResult): the DB object
            for the operation (and for the result).
        operation (ESOperation): the operation for which we have the result.
        job (Job): the result from the worker.

        """
        if operation.type_ == ESOperation.COMPILATION:
            if job.success:
                job.to_submission(object_result)
            else:
                object_result.compilation_tries += 1

        elif operation.type_ == ESOperation.EVALUATION:
            if job.success:
                job.to_submission(object_result)
            else:
                if job.plus is not None and \
                   job.plus.get("tombstone") is True:
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
                        return False
                else:
                    object_result.evaluation_tries += 1

        elif operation.type_ == ESOperation.USER_TEST_COMPILATION:
            if job.success:
                job.to_user_test(object_result)
            else:
                object_result.compilation_tries += 1

        elif operation.type_ == ESOperation.USER_TEST_EVALUATION:
            if job.success:
                job.to_user_test(object_result)
            else:
                object_result.evaluation_tries += 1

        else:
            logger.error("Invalid operation type %r.", operation.type_)

        return True

    def compilation_ended(self, submission_result):
        """Actions to be performed when we have a submission that has
        ended compilation. In particular: we queue evaluation if
        compilation was ok, we inform ScoringService if the
        compilation failed for an error in the submission, or we
        requeue the compilation if there was an error in CMS.

        submission_result (SubmissionResult): the submission result.

        """

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


    def evaluation_ended(self, submission_result):
        """Actions to be performed when we have a submission that has
        been evaluated. In particular: we inform ScoringService on
        success, we requeue on failure.

        submission_result (SubmissionResult): the submission result.

        """

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


    def user_test_compilation_ended(self, user_test_result):
        """Actions to be performed when we have a user test that has
        ended compilation. In particular: we queue evaluation if
        compilation was ok; we requeue compilation if it failed.

        user_test_result (UserTestResult): the user test result.

        """

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


    def user_test_evaluation_ended(self, user_test_result):
        """Actions to be performed when we have a user test that has
        been evaluated. In particular: we do nothing on success, we
        requeue on failure.

        user_test_result (UserTestResult): the user test result.

        """

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

            self.enqueue_all(self.get_submission_operations(submission))

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

            self.enqueue_all(self.get_user_test_operations(user_test))

            session.commit()
