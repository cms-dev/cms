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

"""Tests for the scoringoperations module (containing ScoringOperation
and the function to compute them).

"""

import unittest

# Needs to be first to allow for monkey patching the DB connection string.
from cmstestsuite.unit_tests.databasemixin import DatabaseMixin

from cms.service.scoringoperations import ScoringOperation, get_operations


class TestScoringOperations(DatabaseMixin, unittest.TestCase):

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
        # Similarly to esoperationstest, the active dataset is not
        # autojudged.
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

    # Testing get_operations.

    def test_get_operations_no_operations(self):
        """Test for submissions without operations to do."""
        # Submission to compile, without a result.
        submission = self.add_submission(self.tasks[0], self.participation)

        # Again to compile, but with a result.
        submission, results = self.add_submission_with_results(
            self.tasks[0], self.participation)

        # With many failure during compilation.
        submission, results = self.add_submission_with_results(
            self.tasks[0], self.participation)
        for result in results:
            result.compilation_tries = 25

        # Submission to evaluate.
        submission, results = self.add_submission_with_results(
            self.tasks[0], self.participation, True)

        # With many failures during evaluation.
        submission, results = self.add_submission_with_results(
            self.tasks[0], self.participation, True)
        for result in results:
            result.evaluation_tries = 25

        # Submission partially evaluated.
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
        self.assertEqual(set(get_operations(self.session)), set())

    def test_get_operations_compilation_failed(self):
        """Test for a submission which failed to compile."""
        submission, results = self.add_submission_with_results(
            self.tasks[0], self.participation, False)
        self.session.flush()

        expected_operations = set(
            self._scoring_operation(submission, dataset)
            for dataset in submission.task.datasets if self.to_judge(dataset))

        self.assertEqual(
            set(get_operations(self.session)),
            expected_operations)

    def test_get_operations_evaluated(self):
        """Test for a submission which failed to compile."""
        # A submission completely evaluated.
        submission, results = self.add_submission_with_results(
            self.tasks[0], self.participation, True)
        for result in results:
            for testcase in result.dataset.testcases.values():
                self.add_evaluation(result, testcase)
                result.set_evaluation_outcome()
        self.session.flush()

        expected_operations = set(
            self._scoring_operation(submission, dataset)
            for dataset in submission.task.datasets if self.to_judge(dataset))

        self.assertEqual(
            set(get_operations(self.session)),
            expected_operations)

    def _scoring_operation(self, submission, dataset):
        return (ScoringOperation(submission.id, dataset.id),
                submission.timestamp)

    @staticmethod
    def to_judge(dataset):
        return (
            dataset.autojudge or
            dataset.task.active_dataset_id == dataset.id)


if __name__ == "__main__":
    unittest.main()
