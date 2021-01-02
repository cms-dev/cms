#!/usr/bin/env python3

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

"""The EvaluationService operation class, and related functions to
compute sets of operations to do.

"""

import logging

from sqlalchemy import case, literal

from cms.db import Dataset, Evaluation, Submission, SubmissionResult, \
    Task, Testcase, UserTest, UserTestResult
from cms.io import PriorityQueue, QueueItem


logger = logging.getLogger(__name__)


MAX_COMPILATION_TRIES = 3
MAX_EVALUATION_TRIES = 3
MAX_USER_TEST_COMPILATION_TRIES = 3
MAX_USER_TEST_EVALUATION_TRIES = 3


FILTER_SUBMISSION_DATASETS_TO_JUDGE = (
    (Dataset.id == Task.active_dataset_id) |
    (Dataset.autojudge.is_(True))
)
FILTER_SUBMISSION_RESULTS_TO_COMPILE = (
    (~SubmissionResult.filter_compiled()) &
    (SubmissionResult.compilation_tries < MAX_COMPILATION_TRIES)
)
FILTER_SUBMISSION_RESULTS_TO_EVALUATE = (
    SubmissionResult.filter_compilation_succeeded() &
    (~SubmissionResult.filter_evaluated()) &
    (SubmissionResult.evaluation_tries < MAX_EVALUATION_TRIES)
)


FILTER_USER_TEST_DATASETS_TO_JUDGE = (
    (Dataset.id == Task.active_dataset_id) |
    (Dataset.autojudge.is_(True))
)
FILTER_USER_TEST_RESULTS_TO_COMPILE = (
    (~UserTestResult.filter_compiled()) &
    (UserTestResult.compilation_tries < MAX_COMPILATION_TRIES)
)
FILTER_USER_TEST_RESULTS_TO_EVALUATE = (
    UserTestResult.filter_compilation_succeeded() &
    (~UserTestResult.filter_evaluated()) &
    (UserTestResult.evaluation_tries < MAX_EVALUATION_TRIES)
)


def submission_to_compile(submission_result):
    """Return whether ES is interested in compiling the submission.

    submission_result (SubmissionResult): a submission result.

    return (bool): True if ES wants to compile the submission.

    """
    return submission_result is None or \
        (not submission_result.compiled() and
         submission_result.compilation_tries < MAX_COMPILATION_TRIES)


def submission_to_evaluate(submission_result):
    """Return whether ES is interested in evaluating the submission.

    submission_result (SubmissionResult): a submission result.

    return (bool): True if ES wants to evaluate the submission.

    """
    return submission_result is not None and \
        submission_result.compilation_succeeded() and \
        not submission_result.evaluated() and \
        submission_result.evaluation_tries < MAX_EVALUATION_TRIES


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
         r.compilation_tries < MAX_USER_TEST_COMPILATION_TRIES)


def user_test_to_evaluate(user_test_result):
    """Return whether ES is interested in evaluating the user test.

    user_test_result (UserTestResult): a user test result.

    return (bool): True if ES wants to evaluate the user test.

    """
    r = user_test_result
    return r is not None and r.compilation_outcome == "ok" and \
        not r.evaluated() and \
        r.evaluation_tries < MAX_USER_TEST_EVALUATION_TRIES


def submission_get_operations(submission_result, submission, dataset):
    """Generate all operations originating from a submission for a given
    dataset.

    submission_result (SubmissionResult|None): a submission result.
    submission (Submission): the submission for submission_result.
    dataset (Dataset): the dataset for submission_result.

    yield (ESOperation, int, datetime): an iterator providing triplets
        consisting of a ESOperation for a certain operation to
        perform, its priority and its timestamp.

    """
    if submission_to_compile(submission_result):
        if not dataset.active:
            priority = PriorityQueue.PRIORITY_EXTRA_LOW
        elif submission_result is None or \
                submission_result.compilation_tries == 0:
            priority = PriorityQueue.PRIORITY_HIGH
        else:
            priority = PriorityQueue.PRIORITY_MEDIUM

        yield ESOperation(ESOperation.COMPILATION,
                          submission.id,
                          dataset.id), \
            priority, \
            submission.timestamp

    elif submission_to_evaluate(submission_result):
        if not dataset.active:
            priority = PriorityQueue.PRIORITY_EXTRA_LOW
        elif submission_result.evaluation_tries == 0:
            priority = PriorityQueue.PRIORITY_MEDIUM
        else:
            priority = PriorityQueue.PRIORITY_LOW

        evaluated_testcase_ids = set(
            evaluation.testcase_id
            for evaluation in submission_result.evaluations)
        for testcase_codename in dataset.testcases.keys():
            testcase_id = dataset.testcases[testcase_codename].id
            if testcase_id not in evaluated_testcase_ids:
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
    user_test_result = user_test.get_result(dataset)
    if user_test_to_compile(user_test_result):
        if not dataset.active:
            priority = PriorityQueue.PRIORITY_EXTRA_LOW
        elif user_test_result is None or \
                user_test_result.compilation_tries == 0:
            priority = PriorityQueue.PRIORITY_HIGH
        else:
            priority = PriorityQueue.PRIORITY_MEDIUM

        yield ESOperation(ESOperation.USER_TEST_COMPILATION,
                          user_test.id,
                          dataset.id), \
            priority, \
            user_test.timestamp

    elif user_test_to_evaluate(user_test_result):
        if not dataset.active:
            priority = PriorityQueue.PRIORITY_EXTRA_LOW
        elif user_test_result.evaluation_tries == 0:
            priority = PriorityQueue.PRIORITY_MEDIUM
        else:
            priority = PriorityQueue.PRIORITY_LOW

        yield ESOperation(ESOperation.USER_TEST_EVALUATION,
                          user_test.id,
                          dataset.id), \
            priority, \
            user_test.timestamp


def get_relevant_operations(level, submissions, dataset_id=None):
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


def get_submissions_operations(session, contest_id=None):
    """Return all the operations to do for submissions in the contest.

    session (Session): the database session to use.
    contest_id (int|None): the contest for which we want the operations.
        If none, get operations for any contest.

    return ([ESOperation, float, int]): a list of operation, timestamp
        and priority.

    """
    operations = []

    if contest_id is None:
        contest_filter = literal(True)
    else:
        contest_filter = Task.contest_id == contest_id

    # Retrieve the compilation operations for all submissions without
    # the corresponding result for a dataset to judge. Since we have
    # no SubmissionResult, we cannot join regularly with dataset;
    # instead we take the cartesian product with all the datasets for
    # the correct task.
    to_compile = session.query(Submission)\
        .join(Submission.task)\
        .join(Task.datasets)\
        .outerjoin(SubmissionResult,
                   (Dataset.id == SubmissionResult.dataset_id) &
                   (Submission.id == SubmissionResult.submission_id))\
        .filter(
            contest_filter &
            (FILTER_SUBMISSION_DATASETS_TO_JUDGE) &
            (SubmissionResult.dataset_id.is_(None)))\
        .with_entities(Submission.id, Dataset.id,
                       case([
                           (Dataset.id != Task.active_dataset_id,
                            literal(PriorityQueue.PRIORITY_EXTRA_LOW))
                           ], else_=literal(PriorityQueue.PRIORITY_HIGH)),
                       Submission.timestamp)\
        .all()

    # Retrieve all the compilation operations for submissions
    # already having a result for a dataset to judge.
    to_compile += session.query(Submission)\
        .join(Submission.task)\
        .join(Submission.results)\
        .join(SubmissionResult.dataset)\
        .filter(
            contest_filter &
            (FILTER_SUBMISSION_DATASETS_TO_JUDGE) &
            (FILTER_SUBMISSION_RESULTS_TO_COMPILE))\
        .with_entities(Submission.id, Dataset.id,
                       case([
                           (Dataset.id != Task.active_dataset_id,
                            literal(PriorityQueue.PRIORITY_EXTRA_LOW)),
                           (SubmissionResult.compilation_tries == 0,
                            literal(PriorityQueue.PRIORITY_HIGH))
                           ], else_=literal(PriorityQueue.PRIORITY_MEDIUM)),
                       Submission.timestamp)\
        .all()

    for data in to_compile:
        submission_id, dataset_id, priority, timestamp = data
        operations.append((
            ESOperation(ESOperation.COMPILATION, submission_id, dataset_id),
            priority, timestamp))

    # Retrieve all the evaluation operations for a dataset to
    # judge. Again we need to pick all tuples (submission, dataset,
    # testcase) such that there is no evaluation for them, and to do
    # so we take the cartesian product with the testcases and later
    # ensure that there is no evaluation associated.
    to_evaluate = session.query(SubmissionResult)\
        .join(SubmissionResult.dataset)\
        .join(SubmissionResult.submission)\
        .join(Submission.task)\
        .join(Dataset.testcases)\
        .outerjoin(Evaluation,
                   (Evaluation.submission_id == Submission.id) &
                   (Evaluation.dataset_id == Dataset.id) &
                   (Evaluation.testcase_id == Testcase.id))\
        .filter(
            contest_filter &
            (FILTER_SUBMISSION_DATASETS_TO_JUDGE) &
            (FILTER_SUBMISSION_RESULTS_TO_EVALUATE) &
            (Evaluation.id.is_(None)))\
        .with_entities(Submission.id, Dataset.id,
                       case([
                           (Dataset.id != Task.active_dataset_id,
                            literal(PriorityQueue.PRIORITY_EXTRA_LOW)),
                           (SubmissionResult.evaluation_tries == 0,
                            literal(PriorityQueue.PRIORITY_MEDIUM))
                           ], else_=literal(PriorityQueue.PRIORITY_LOW)),
                       Submission.timestamp,
                       Testcase.codename)\
        .all()

    for data in to_evaluate:
        submission_id, dataset_id, priority, timestamp, codename = data
        operations.append((
            ESOperation(
                ESOperation.EVALUATION, submission_id, dataset_id, codename),
            priority, timestamp))

    return operations


def get_user_tests_operations(session, contest_id=None):
    """Return all the operations to do for user tests in the contest.

    session (Session): the database session to use.
    contest_id (int|None): the contest for which we want the operations.
        If none, get operations for any contest.

    return ([ESOperation, float, int]): a list of operation, timestamp
        and priority.

    """
    operations = []

    if contest_id is None:
        contest_filter = literal(True)
    else:
        contest_filter = Task.contest_id == contest_id

    # Retrieve the compilation operations for all user tests without
    # the corresponding result for a dataset to judge. Since we have
    # no UserTestResult, we cannot join regularly with dataset;
    # instead we take the cartesian product with all the datasets for
    # the correct task.
    to_compile = session.query(UserTest)\
        .join(UserTest.task)\
        .join(Task.datasets)\
        .outerjoin(UserTestResult,
                   (Dataset.id == UserTestResult.dataset_id) &
                   (UserTest.id == UserTestResult.user_test_id))\
        .filter(
            contest_filter &
            (FILTER_USER_TEST_DATASETS_TO_JUDGE) &
            (UserTestResult.dataset_id.is_(None)))\
        .with_entities(UserTest.id, Dataset.id,
                       case([
                           (Dataset.id != Task.active_dataset_id,
                            literal(PriorityQueue.PRIORITY_EXTRA_LOW))
                           ], else_=literal(PriorityQueue.PRIORITY_HIGH)),
                       UserTest.timestamp)\
        .all()

    # Retrieve all the compilation operations for user_tests
    # already having a result for a dataset to judge.
    to_compile += session.query(UserTest)\
        .join(UserTest.task)\
        .join(UserTest.results)\
        .join(UserTestResult.dataset)\
        .filter(
            contest_filter &
            (FILTER_USER_TEST_DATASETS_TO_JUDGE) &
            (FILTER_USER_TEST_RESULTS_TO_COMPILE))\
        .with_entities(UserTest.id, Dataset.id,
                       case([
                           (Dataset.id != Task.active_dataset_id,
                            literal(PriorityQueue.PRIORITY_EXTRA_LOW)),
                           (UserTestResult.compilation_tries == 0,
                            literal(PriorityQueue.PRIORITY_HIGH))
                           ], else_=literal(PriorityQueue.PRIORITY_MEDIUM)),
                       UserTest.timestamp)\
        .all()

    for data in to_compile:
        user_test_id, dataset_id, priority, timestamp = data
        operations.append((
            ESOperation(ESOperation.USER_TEST_COMPILATION,
                        user_test_id, dataset_id),
            priority, timestamp))

    # Retrieve all the evaluation operations for a dataset to judge,
    # that is, all pairs (user_test, dataset) for which we have a
    # user test result which is compiled but not evaluated.
    to_evaluate = session.query(UserTest)\
        .join(UserTest.task)\
        .join(UserTest.results)\
        .join(UserTestResult.dataset)\
        .filter(
            contest_filter &
            (FILTER_USER_TEST_DATASETS_TO_JUDGE) &
            (FILTER_USER_TEST_RESULTS_TO_EVALUATE))\
        .with_entities(UserTest.id, Dataset.id,
                       case([
                           (Dataset.id != Task.active_dataset_id,
                            literal(PriorityQueue.PRIORITY_EXTRA_LOW)),
                           (UserTestResult.evaluation_tries == 0,
                            literal(PriorityQueue.PRIORITY_MEDIUM))
                           ], else_=literal(PriorityQueue.PRIORITY_LOW)),
                       UserTest.timestamp)\
        .all()

    for data in to_evaluate:
        user_test_id, dataset_id, priority, timestamp = data
        operations.append((
            ESOperation(
                ESOperation.USER_TEST_EVALUATION, user_test_id, dataset_id),
            priority, timestamp))

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

    @staticmethod
    def from_dict(d):
        return ESOperation(d["type"],
                           d["object_id"],
                           d["dataset_id"],
                           d["testcase_codename"])

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

    def __repr__(self):
        return "(\"%s\", %s, %s, %s)" % (
            self.type_,
            self.object_id,
            self.dataset_id,
            self.testcase_codename)

    def for_submission(self):
        """Return if the operation is for a submission or for a user test.

        return (bool): True if this operation is for a submission.

        """
        return self.type_ == ESOperation.COMPILATION or \
            self.type_ == ESOperation.EVALUATION

    def to_dict(self):
        return {
            "type": self.type_,
            "object_id": self.object_id,
            "dataset_id": self.dataset_id,
            "testcase_codename": self.testcase_codename
        }

    def short_key(self):
        """Return a short tuple (type, object_id, dataset_id) that omits
        the testcase codename.

        """
        return (str(self.type_),
                str(self.object_id),
                str(self.dataset_id))
