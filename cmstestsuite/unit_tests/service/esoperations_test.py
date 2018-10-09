#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015-2016 Stefano Maggiolo <s.maggiolo@gmail.com>
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

import unittest

# Needs to be first to allow for monkey patching the DB connection string.
from cmstestsuite.unit_tests.databasemixin import DatabaseMixin

from cms.io.priorityqueue import PriorityQueue
from cms.service.esoperations import ESOperation, get_submissions_operations, \
    get_user_tests_operations


class TestESOperations(DatabaseMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()

        # First set up the interesting contest, with a few copies
        # of everything.
        self.contest = self.add_contest()
        self.participation = self.add_participation(contest=self.contest)
        self.tasks = [
            self.add_task(contest=self.contest),
            self.add_task(contest=self.contest)
        ]
        self.datasets = sum([[
            self.add_dataset(task=task, autojudge=False),
            self.add_dataset(task=task, autojudge=True),
            self.add_dataset(task=task, autojudge=False),
        ] for task in self.tasks], [])
        # For maximum possibility of bugs, we use an active dataset
        # with the autojudge bit unset (operations for the active
        # dataset should be scheduled regardless of the autojudge
        # status).
        for task in self.tasks:
            task.active_dataset = task.datasets[0]
        self.testcases = sum([[
            self.add_testcase(dataset),
            self.add_testcase(dataset),
            self.add_testcase(dataset),
        ] for dataset in self.datasets], [])

        self.session.flush()

    def tearDown(self):
        self.session.close()
        super().tearDown()

    # Testing get_submissions_operations.

    def test_get_submissions_operations_no_operations(self):
        """Test for submissions without operations to do."""
        # A submission for a different contest.
        self.add_submission()

        # A submission that failed compilation.
        self.add_submission_with_results(
            self.tasks[0], self.participation, False)

        # A submission completely evaluated.
        submission, results = self.add_submission_with_results(
            self.tasks[0], self.participation, True)
        for result in results:
            for testcase in result.dataset.testcases.values():
                self.add_evaluation(result, testcase)

        # A submission reaching maximum tries for compilation
        submission, results = self.add_submission_with_results(
            self.tasks[0], self.participation)
        for result in results:
            result.compilation_tries = 25

        # A submission reaching maximum tries for evaluation
        submission, results = self.add_submission_with_results(
            self.tasks[0], self.participation, True)
        for result in results:
            result.evaluation_tries = 25

        self.session.flush()
        self.assertEqual(
            set(get_submissions_operations(self.session, self.contest.id)),
            set())

    def test_get_submissions_operations_without_results(self):
        """Test for a submission without submission results."""
        submission = self.add_submission(self.tasks[0], self.participation)
        self.session.flush()

        expected_operations = set(
            self.submission_compilation_operation(submission, dataset)
            for dataset in submission.task.datasets if self.to_judge(dataset))

        self.assertEqual(
            set(get_submissions_operations(self.session, self.contest.id)),
            expected_operations)

    def test_get_submissions_operations_with_results(self):
        """Test for a submission with submission results."""
        submission, results = self.add_submission_with_results(
            self.tasks[0], self.participation)
        self.session.flush()

        expected_operations = set(
            self.submission_compilation_operation(submission, dataset)
            for dataset in submission.task.datasets if self.to_judge(dataset))

        self.assertEqual(
            set(get_submissions_operations(self.session, self.contest.id)),
            expected_operations)

    def test_get_submissions_operations_with_results_second_try(self):
        """Test for a submission with submission results."""
        submission, results = self.add_submission_with_results(
            self.tasks[0], self.participation)
        for result in results:
            result.compilation_tries = 1
        self.session.flush()

        expected_operations = set(
            self.submission_compilation_operation(
                submission, result.dataset, result)
            for result in results if self.to_judge(result.dataset))

        self.assertEqual(
            set(get_submissions_operations(self.session, self.contest.id)),
            expected_operations)

    def test_get_submissions_operations_to_evaluate(self):
        """Test for a compiled submission."""
        submission, results = self.add_submission_with_results(
            self.tasks[0], self.participation, True)
        self.session.flush()

        expected_operations = set(
            self.submission_evaluation_operation(result, codename)
            for result in results if self.to_judge(result.dataset)
            for codename in result.dataset.testcases)

        self.assertEqual(
            set(get_submissions_operations(self.session, self.contest.id)),
            expected_operations)

    def test_get_submissions_operations_to_evaluate_second_try(self):
        """Test for a compiled submission."""
        submission, results = self.add_submission_with_results(
            self.tasks[0], self.participation, True)
        for result in results:
            result.evaluation_tries = 1
        self.session.flush()

        expected_operations = set(
            self.submission_evaluation_operation(result, codename)
            for result in results if self.to_judge(result.dataset)
            for codename in result.dataset.testcases)

        self.assertEqual(
            set(get_submissions_operations(self.session, self.contest.id)),
            expected_operations)

    def test_get_submissions_operations_partially_evaluate(self):
        """Test for a submission with some evaluation present."""
        submission, results = self.add_submission_with_results(
            self.tasks[0], self.participation, True)
        evaluated_codenames = set()
        for result in results:
            # Pick one arbitrary testcase.
            evaluated_codename = next(iter(result.dataset.testcases.keys()))
            self.add_evaluation(
                result, result.dataset.testcases[evaluated_codename])
            evaluated_codenames.add(evaluated_codename)
        self.session.flush()

        expected_operations = set(
            self.submission_evaluation_operation(result, codename)
            for result in results if self.to_judge(result.dataset)
            for codename in result.dataset.testcases
            if codename not in evaluated_codenames)

        self.assertEqual(
            set(get_submissions_operations(self.session, self.contest.id)),
            expected_operations)

    def test_get_submissions_operations_mixed(self):
        """Test with many different submission statuses."""
        expected_operations = set()

        # A submission for a different contest.
        self.add_submission()

        # A submission that failed compilation.
        self.add_submission_with_results(
            self.tasks[0], self.participation, False)

        # A submission without results.
        submission = self.add_submission(self.tasks[0], self.participation)
        self.session.flush()
        expected_operations.update(set(
            self.submission_compilation_operation(submission, dataset)
            for dataset in submission.task.datasets if self.to_judge(dataset)))

        # A submission with results to be compiled.
        submission, results = self.add_submission_with_results(
            self.tasks[0], self.participation)
        self.session.flush()
        expected_operations.update(set(
            self.submission_compilation_operation(submission, dataset)
            for dataset in submission.task.datasets if self.to_judge(dataset)))

        # A submission with results to be evaluated.
        submission, results = self.add_submission_with_results(
            self.tasks[0], self.participation, True)
        self.session.flush()
        expected_operations.update(set(
            self.submission_evaluation_operation(result, codename)
            for result in results if self.to_judge(result.dataset)
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

    # Testing get_user_tests_operations.

    def test_get_user_tests_operations_no_operations(self):
        """Test for user_tests without operations to do."""
        # A user_test for a different contest.
        self.add_user_test()

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

        self.session.flush()
        self.assertEqual(
            set(get_user_tests_operations(self.session, self.contest.id)),
            set())

    def test_get_user_tests_operations_without_results(self):
        """Test for a user_test without user_test results."""
        user_test = self.add_user_test(self.tasks[0], self.participation)
        self.session.flush()

        expected_operations = set(
            self.user_test_compilation_operation(user_test, dataset)
            for dataset in user_test.task.datasets if self.to_judge(dataset))

        self.assertEqual(
            set(get_user_tests_operations(self.session, self.contest.id)),
            expected_operations)

    def test_get_user_tests_operations_with_results(self):
        """Test for a user_test with user_test results."""
        user_test, results = self.add_user_test_with_results()
        self.session.flush()

        expected_operations = set(
            self.user_test_compilation_operation(user_test, dataset)
            for dataset in user_test.task.datasets if self.to_judge(dataset))

        self.assertEqual(
            set(get_user_tests_operations(self.session, self.contest.id)),
            expected_operations)

    def test_get_user_tests_operations_with_results_second_try(self):
        """Test for a user_test with user_test results."""
        user_test, results = self.add_user_test_with_results()
        for result in results:
            result.compilation_tries = 1
        self.session.flush()

        expected_operations = set(
            self.user_test_compilation_operation(
                user_test, result.dataset, result)
            for result in results if self.to_judge(result.dataset))

        self.assertEqual(
            set(get_user_tests_operations(self.session, self.contest.id)),
            expected_operations)

    def test_get_user_tests_operations_to_evaluate(self):
        """Test for a compiled user_test."""
        user_test, results = self.add_user_test_with_results(True)
        self.session.flush()

        expected_operations = set(
            self.user_test_evaluation_operation(result)
            for result in results if self.to_judge(result.dataset))

        self.assertEqual(
            set(get_user_tests_operations(self.session, self.contest.id)),
            expected_operations)

    def test_get_user_tests_operations_to_evaluate_second_try(self):
        """Test for a compiled user_test."""
        user_test, results = self.add_user_test_with_results(True)
        for result in results:
            result.evaluation_tries = 1
        self.session.flush()

        expected_operations = set(
            self.user_test_evaluation_operation(result)
            for result in results if self.to_judge(result.dataset))

        self.assertEqual(
            set(get_user_tests_operations(self.session, self.contest.id)),
            expected_operations)

    def test_get_user_tests_operations_mixed(self):
        """Test with many different user_test statuses."""
        expected_operations = set()

        # A user_test for a different contest.
        self.add_user_test()

        # A user_test that failed compilation.
        self.add_user_test_with_results(False)

        # A user_test without results.
        user_test = self.add_user_test(self.tasks[0], self.participation)
        self.session.flush()
        expected_operations.update(set(
            self.user_test_compilation_operation(user_test, dataset)
            for dataset in user_test.task.datasets if self.to_judge(dataset)))

        # A user_test with results to be compiled.
        user_test, results = self.add_user_test_with_results()
        self.session.flush()
        expected_operations.update(set(
            self.user_test_compilation_operation(user_test, dataset)
            for dataset in user_test.task.datasets if self.to_judge(dataset)))

        # A user_test with results to be evaluated.
        user_test, results = self.add_user_test_with_results(True)
        self.session.flush()
        expected_operations.update(set(
            self.user_test_evaluation_operation(result)
            for result in results if self.to_judge(result.dataset)))

        self.assertEqual(
            set(get_user_tests_operations(self.session, self.contest.id)),
            expected_operations)

    def user_test_compilation_operation(self, user_test, dataset, result=None):
        active_priority = PriorityQueue.PRIORITY_HIGH \
            if result is None or result.compilation_tries == 0 \
            else PriorityQueue.PRIORITY_MEDIUM
        return (ESOperation(ESOperation.USER_TEST_COMPILATION,
                            user_test.id, dataset.id),
                active_priority if dataset.active
                else PriorityQueue.PRIORITY_EXTRA_LOW,
                user_test.timestamp)

    def user_test_evaluation_operation(self, result):
        active_priority = PriorityQueue.PRIORITY_MEDIUM \
            if result.evaluation_tries == 0 else PriorityQueue.PRIORITY_LOW
        return (ESOperation(ESOperation.USER_TEST_EVALUATION,
                            result.user_test.id, result.dataset.id),
                active_priority if result.dataset.active
                else PriorityQueue.PRIORITY_EXTRA_LOW,
                result.user_test.timestamp)

    @staticmethod
    def to_judge(dataset):
        return (
            dataset.autojudge or
            dataset.task.active_dataset_id == dataset.id)


if __name__ == "__main__":
    unittest.main()
