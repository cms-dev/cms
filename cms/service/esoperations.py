#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2015 Stefano Maggiolo <s.maggiolo@gmail.com>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging

from cms.io import PriorityQueue, QueueItem
from cms.db import Dataset, Submission, UserTest
from cms.grading.Job import CompilationJob, EvaluationJob


logger = logging.getLogger(__name__)


MAX_COMPILATION_TRIES = 3
MAX_EVALUATION_TRIES = 3
MAX_USER_TEST_COMPILATION_TRIES = 3
MAX_USER_TEST_EVALUATION_TRIES = 3


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
        for testcase_codename in dataset.testcases.iterkeys():
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

    def build_job(self, session):
        """Produce the Job for this operation.

        Return the Job object that has to be sent to Workers to have
        them perform the operation this object describes.

        session (Session): the database session to use to fetch objects
            if necessary.

        return (Job): the job encoding of the operation, as understood
            by Workers and TaskTypes.

        """
        result = None
        dataset = Dataset.get_from_id(self.dataset_id, session)
        if self.type_ == ESOperation.COMPILATION:
            submission = Submission.get_from_id(self.object_id, session)
            result = CompilationJob.from_submission(submission, dataset)
        elif self.type_ == ESOperation.EVALUATION:
            submission = Submission.get_from_id(self.object_id, session)
            result = EvaluationJob.from_submission(
                submission, dataset, self.testcase_codename)
        elif self.type_ == ESOperation.USER_TEST_COMPILATION:
            user_test = UserTest.get_from_id(self.object_id, session)
            result = CompilationJob.from_user_test(user_test, dataset)
        elif self.type_ == ESOperation.USER_TEST_EVALUATION:
            user_test = UserTest.get_from_id(self.object_id, session)
            result = EvaluationJob.from_user_test(user_test, dataset)
        return result
