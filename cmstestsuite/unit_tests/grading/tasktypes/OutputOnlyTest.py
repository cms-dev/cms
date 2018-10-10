#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Tests for the OutputOnly task type."""

import unittest
from unittest.mock import MagicMock

from cms.db import File
from cms.grading.Job import EvaluationJob
from cms.grading.tasktypes.OutputOnly import OutputOnly
from cms.service.esoperations import ESOperation
from cmstestsuite.unit_tests.grading.tasktypes.tasktypetestutils import \
    OUTCOME, TEXT, TaskTypeTestMixin


FILE_001 = File(digest="digest of 001", filename="output_001.txt")
FILE_023 = File(digest="digest of 023", filename="output_023.txt")


class TestEvaluate(TaskTypeTestMixin, unittest.TestCase):
    """Tests for evaluate().

    prepare() creates a task type and a job with the given arguments, and in
    addition sets up successful return values for eval_output.

    """

    def setUp(self):
        super().setUp()
        self.setUpMocks("OutputOnly")
        self.file_cacher = MagicMock()

    @staticmethod
    def job(files):
        operation = ESOperation(ESOperation.EVALUATION, 1, 1, "023")
        return EvaluationJob(input="digest of input",
                             output="digest of correct output",
                             files=files,
                             operation=operation,
                             multithreaded_sandbox=True)

    def prepare(self, parameters, files):
        tt = OutputOnly(parameters)
        job = self.job(files)
        self.eval_output.return_value = (True, OUTCOME, TEXT)
        return tt, job

    def assertResultsInJob(self, job, success, outcome, text, stats):
        self.assertEqual(job.success, success)
        self.assertEqual(job.outcome, outcome)
        self.assertEqual(job.text, text)
        self.assertEqual(job.plus, stats)

    def test_diff_success(self):
        tt, job = self.prepare(["diff"], {
            "output_001.txt": FILE_001,
            "output_023.txt": FILE_023
        })

        tt.evaluate(job, self.file_cacher)

        self.eval_output.assert_called_once_with(
            self.file_cacher, job, None, user_output_digest="digest of 023")
        self.assertResultsInJob(job, True, str(OUTCOME), TEXT, {})

    def test_diff_missing_file(self):
        tt, job = self.prepare(["diff"], {
            "output_001.txt": FILE_001,
        })

        tt.evaluate(job, self.file_cacher)

        self.eval_output.assert_not_called()
        self.assertResultsInJob(job,
                                True, str(0.0), ["File not submitted"], {})

    def test_diff_failure(self):
        tt, job = self.prepare(["diff"], {
            "output_001.txt": FILE_001,
            "output_023.txt": FILE_023
        })
        self.eval_output.return_value = False, None, None

        tt.evaluate(job, self.file_cacher)

        self.eval_output.assert_called_once_with(
            self.file_cacher, job, None, user_output_digest="digest of 023")
        self.assertResultsInJob(job, False, None, None, None)

    def test_comparator_success(self):
        tt, job = self.prepare(["comparator"], {
            "output_001.txt": FILE_001,
            "output_023.txt": FILE_023
        })

        tt.evaluate(job, self.file_cacher)

        self.eval_output.assert_called_once_with(
            self.file_cacher, job, "checker",
            user_output_digest="digest of 023")
        self.assertResultsInJob(job, True, str(OUTCOME), TEXT, {})


if __name__ == "__main__":
    unittest.main()
