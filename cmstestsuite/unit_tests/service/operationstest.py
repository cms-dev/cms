#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Tests for the operations module (containing ESOperation and the
functions to compute them).

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import unittest

from cmstestsuite.unit_tests.testdbgenerator import TestCaseWithDatabase, \
    add_contest, add_dataset, add_evaluation, add_participation, \
    add_submission, add_submission_result, add_task, add_testcase, \
    add_user_test, add_user_test_result

from cms.db import Session
from cms.io.priorityqueue import PriorityQueue
from cms.service.operations import ESOperation, get_submissions_operations, \
    get_user_tests_operations


class TestOperations(TestCaseWithDatabase):

    def setUp(self):
        super(TestOperations, self).setUp()

        self.session = Session()

        # First set up the interesting contest, with a few copies
        # of everything.
        self.contest = add_contest(self.session)
        self.participation = add_participation(
            self.session, contest=self.contest)
        self.tasks = [
            add_task(self.session, self.contest),
            add_task(self.session, self.contest)
        ]
        self.datasets = sum([[
            add_dataset(self.session, task, autojudge=True),
            add_dataset(self.session, task, autojudge=True),
            add_dataset(self.session, task, autojudge=False),
        ] for task in self.tasks], [])
        for task in self.tasks:
            task.active_dataset = task.datasets[0]
        self.testcases = sum([[
            add_testcase(self.session, dataset),
            add_testcase(self.session, dataset),
            add_testcase(self.session, dataset),
        ] for dataset in self.datasets], [])

        self.session.commit()

    def tearDown(self):
        self.session.close()
        super(TestOperations, self).tearDown()

    # Testing get_submissions_operations.

    def test_get_submissions_operations_no_operations(self):
        """Test for submissions without operations to do."""
        # A submission for a different contest.
        add_submission(self.session)

        # A submission that failed compilation.
        self.add_submission_with_results(False)

        # A submission completely evaluated.
        submission, results = self.add_submission_with_results(True)
        for result in results:
            for codename, testcase in result.dataset.testcases.items():
                add_evaluation(self.session, result, testcase)

        # A submission reaching maximum tries for compilation
        submission, results = self.add_submission_with_results()
        for result in results:
            result.compilation_tries = 25

        # A submission reaching maximum tries for evaluation
        submission, results = self.add_submission_with_results(True)
        for result in results:
            result.evaluation_tries = 25

        self.session.commit()
        self.assertEqual(
            set(get_submissions_operations(self.session, self.contest.id)),
            set())

    def test_get_submissions_operations_without_results(self):
        """Test for a submission without submission results."""
        submission = add_submission(
            self.session, self.tasks[0], self.participation)
        self.session.commit()

        expected_operations = set(
            self.submission_compilation_operation(submission, dataset)
            for dataset in submission.task.datasets if dataset.autojudge)

        self.assertEqual(
            set(get_submissions_operations(self.session, self.contest.id)),
            expected_operations)

    def test_get_submissions_operations_with_results(self):
        """Test for a submission with submission results."""
        submission, results = self.add_submission_with_results()
        self.session.commit()

        expected_operations = set(
            self.submission_compilation_operation(submission, dataset)
            for dataset in submission.task.datasets if dataset.autojudge)

        self.assertEqual(
            set(get_submissions_operations(self.session, self.contest.id)),
            expected_operations)

    def test_get_submissions_operations_with_results_second_try(self):
        """Test for a submission with submission results."""
        submission, results = self.add_submission_with_results()
        for result in results:
            result.compilation_tries = 1
        self.session.commit()

        expected_operations = set(
            self.submission_compilation_operation(
                submission, result.dataset, result)
            for result in results if result.dataset.autojudge)

        self.assertEqual(
            set(get_submissions_operations(self.session, self.contest.id)),
            expected_operations)

    def test_get_submissions_operations_to_evaluate(self):
        """Test for a compiled submission."""
        submission, results = self.add_submission_with_results(True)
        self.session.commit()

        expected_operations = set(
            self.submission_evaluation_operation(result, codename)
            for result in results if result.dataset.autojudge
            for codename in result.dataset.testcases)

        self.assertEqual(
            set(get_submissions_operations(self.session, self.contest.id)),
            expected_operations)

    def test_get_submissions_operations_to_evaluate_second_try(self):
        """Test for a compiled submission."""
        submission, results = self.add_submission_with_results(True)
        for result in results:
            result.evaluation_tries = 1
        self.session.commit()

        expected_operations = set(
            self.submission_evaluation_operation(result, codename)
            for result in results if result.dataset.autojudge
            for codename in result.dataset.testcases)

        self.assertEqual(
            set(get_submissions_operations(self.session, self.contest.id)),
            expected_operations)

    def test_get_submissions_operations_partially_evaluate(self):
        """Test for a submission with some evaluation present."""
        submission, results = self.add_submission_with_results(True)
        evaluated_codenames = set()
        for result in results:
            evaluated_codename = result.dataset.testcases.keys()[0]
            add_evaluation(self.session, result,
                           result.dataset.testcases[evaluated_codename])
            evaluated_codenames.add(evaluated_codename)
        self.session.commit()

        expected_operations = set(
            self.submission_evaluation_operation(result, codename)
            for result in results if result.dataset.autojudge
            for codename in result.dataset.testcases
            if codename not in evaluated_codenames)

        self.assertEqual(
            set(get_submissions_operations(self.session, self.contest.id)),
            expected_operations)

    def test_get_submissions_operations_mixed(self):
        """Test with many different submission statuses."""
        expected_operations = set()

        # A submission for a different contest.
        add_submission(self.session)

        # A submission that failed compilation.
        self.add_submission_with_results(False)

        # A submission without results.
        submission = add_submission(
            self.session, self.tasks[0], self.participation)
        self.session.commit()
        expected_operations.update(set(
            self.submission_compilation_operation(submission, dataset)
            for dataset in submission.task.datasets if dataset.autojudge))

        # A submission with results to be compiled.
        submission, results = self.add_submission_with_results()
        self.session.commit()
        expected_operations.update(set(
            self.submission_compilation_operation(submission, dataset)
            for dataset in submission.task.datasets if dataset.autojudge))

        # A submission with results to be evaluated.
        submission, results = self.add_submission_with_results(True)
        self.session.commit()
        expected_operations.update(set(
            self.submission_evaluation_operation(result, codename)
            for result in results if result.dataset.autojudge
            for codename in result.dataset.testcases))

        self.assertEqual(
            set(get_submissions_operations(self.session, self.contest.id)),
            expected_operations)

    def submission_compilation_operation(
            self, submission, dataset, result=None):
        active_priority = PriorityQueue.PRIORITY_HIGH \
            if result is None or result.compilation_tries == 0 \
            else PriorityQueue.PRIORITY_MEDIUM
        return (ESOperation(ESOperation.COMPILATION,
                            submission.id, dataset.id),
                active_priority if dataset.active
                else PriorityQueue.PRIORITY_EXTRA_LOW,
                submission.timestamp)

    def submission_evaluation_operation(self, result, codename):
        active_priority = PriorityQueue.PRIORITY_MEDIUM \
            if result.evaluation_tries == 0 else PriorityQueue.PRIORITY_LOW
        return (ESOperation(ESOperation.EVALUATION,
                            result.submission.id, result.dataset.id, codename),
                active_priority if result.dataset.active
                else PriorityQueue.PRIORITY_EXTRA_LOW,
                result.submission.timestamp)

    def add_submission_with_results(self, compilation_outcome=None):
        """Add a submission for the first tasks, all of its results, and
        optionally the compilation outcome for all results.

        """
        submission = add_submission(
            self.session, self.tasks[0], self.participation)
        results = [add_submission_result(self.session, submission, dataset)
                   for dataset in self.tasks[0].datasets]
        if compilation_outcome is not None:
            for result in results:
                result.set_compilation_outcome(compilation_outcome)
        return submission, results

    # Testing get_user_tests_operations.

    def test_get_user_tests_operations_no_operations(self):
        """Test for user_tests without operations to do."""
        # A user_test for a different contest.
        add_user_test(self.session)

        # A user_test that failed compilation.
        self.add_user_test_with_results(False)

        # A user_test completely evaluated.
        user_test, results = self.add_user_test_with_results(True)
        for result in results:
            result.set_evaluation_outcome()

        # A user_test reaching maximum tries for compilation
        user_test, results = self.add_user_test_with_results()
        for result in results:
            result.compilation_tries = 25

        # A user_test reaching maximum tries for evaluation
        user_test, results = self.add_user_test_with_results(True)
        for result in results:
            result.evaluation_tries = 25

        self.session.commit()
        self.assertEqual(
            set(get_user_tests_operations(self.session, self.contest.id)),
            set())

    def test_get_user_tests_operations_without_results(self):
        """Test for a user_test without user_test results."""
        user_test = add_user_test(
            self.session, self.tasks[0], self.participation)
        self.session.commit()

        expected_operations = set(
            self.user_test_compilation_operation(user_test, dataset)
            for dataset in user_test.task.datasets if dataset.autojudge)

        self.assertEqual(
            set(get_user_tests_operations(self.session, self.contest.id)),
            expected_operations)

    def test_get_user_tests_operations_with_results(self):
        """Test for a user_test with user_test results."""
        user_test, results = self.add_user_test_with_results()
        self.session.commit()

        expected_operations = set(
            self.user_test_compilation_operation(user_test, dataset)
            for dataset in user_test.task.datasets if dataset.autojudge)

        self.assertEqual(
            set(get_user_tests_operations(self.session, self.contest.id)),
            expected_operations)

    def test_get_user_tests_operations_with_results_second_try(self):
        """Test for a user_test with user_test results."""
        user_test, results = self.add_user_test_with_results()
        for result in results:
            result.compilation_tries = 1
        self.session.commit()

        expected_operations = set(
            self.user_test_compilation_operation(
                user_test, result.dataset, result)
            for result in results if result.dataset.autojudge)

        self.assertEqual(
            set(get_user_tests_operations(self.session, self.contest.id)),
            expected_operations)

    def test_get_user_tests_operations_to_evaluate(self):
        """Test for a compiled user_test."""
        user_test, results = self.add_user_test_with_results(True)
        self.session.commit()

        expected_operations = set(
            self.user_test_evaluation_operation(result)
            for result in results if result.dataset.autojudge)

        self.assertEqual(
            set(get_user_tests_operations(self.session, self.contest.id)),
            expected_operations)

    def test_get_user_tests_operations_to_evaluate_second_try(self):
        """Test for a compiled user_test."""
        user_test, results = self.add_user_test_with_results(True)
        for result in results:
            result.evaluation_tries = 1
        self.session.commit()

        expected_operations = set(
            self.user_test_evaluation_operation(result)
            for result in results if result.dataset.autojudge)

        self.assertEqual(
            set(get_user_tests_operations(self.session, self.contest.id)),
            expected_operations)

    def test_get_user_tests_operations_mixed(self):
        """Test with many different user_test statuses."""
        expected_operations = set()

        # A user_test for a different contest.
        add_user_test(self.session)

        # A user_test that failed compilation.
        self.add_user_test_with_results(False)

        # A user_test without results.
        user_test = add_user_test(
            self.session, self.tasks[0], self.participation)
        self.session.commit()
        expected_operations.update(set(
            self.user_test_compilation_operation(user_test, dataset)
            for dataset in user_test.task.datasets if dataset.autojudge))

        # A user_test with results to be compiled.
        user_test, results = self.add_user_test_with_results()
        self.session.commit()
        expected_operations.update(set(
            self.user_test_compilation_operation(user_test, dataset)
            for dataset in user_test.task.datasets if dataset.autojudge))

        # A user_test with results to be evaluated.
        user_test, results = self.add_user_test_with_results(True)
        self.session.commit()
        expected_operations.update(set(
            self.user_test_evaluation_operation(result)
            for result in results if result.dataset.autojudge))

        self.assertEqual(
            set(get_user_tests_operations(self.session, self.contest.id)),
            expected_operations)

    def user_test_compilation_operation(self, user_test, dataset, result=None):
        active_priority = PriorityQueue.PRIORITY_HIGH \
            if result is None or result.compilation_tries == 0 \
            else PriorityQueue.PRIORITY_MEDIUM
        return (ESOperation(ESOperation.COMPILATION,
                            user_test.id, dataset.id),
                active_priority if dataset.active
                else PriorityQueue.PRIORITY_EXTRA_LOW,
                user_test.timestamp)

    def user_test_evaluation_operation(self, result):
        active_priority = PriorityQueue.PRIORITY_MEDIUM \
            if result.evaluation_tries == 0 else PriorityQueue.PRIORITY_LOW
        return (ESOperation(ESOperation.EVALUATION,
                            result.user_test.id, result.dataset.id),
                active_priority if result.dataset.active
                else PriorityQueue.PRIORITY_EXTRA_LOW,
                result.user_test.timestamp)

    def add_user_test_with_results(self, compilation_outcome=None):
        """Add a user_test for the first tasks, all of its results, and
        optionally the compilation outcome for all results.

        """
        user_test = add_user_test(
            self.session, self.tasks[0], self.participation)
        results = [add_user_test_result(self.session, user_test, dataset)
                   for dataset in self.tasks[0].datasets]
        if compilation_outcome is not None:
            for result in results:
                result.set_compilation_outcome(compilation_outcome)
        return user_test, results

if __name__ == "__main__":
    unittest.main()
