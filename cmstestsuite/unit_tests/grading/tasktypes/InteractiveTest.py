#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2026 Luca Versari <veluca93@gmail.com>
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

"""Tests for the Interactive task type."""

import unittest
from unittest.mock import MagicMock

from cms.db import File, Manager
from cms.grading.Job import CompilationJob
from cms.grading.tasktypes.Interactive import Interactive
from cmstestsuite.unit_tests.grading.tasktypes.tasktypetestutils import (
    COMPILATION_COMMAND_1,
    COMPILATION_COMMAND_2,
    LANG_1,
    LANG_2,
    STATS_OK,
    TEXT,
    TaskTypeTestMixin,
    fake_compilation_commands,
)


FILE_FOO_L1 = File(digest="digest of foo.l1", filename="foo.%l")
GRADER_L1 = Manager(digest="digest of grader.l1", filename="grader.l1")


class TestInteractiveTaskType(TaskTypeTestMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.setUpMocks("Interactive")
        self.languages.update({LANG_1, LANG_2})
        self.file_cacher = MagicMock()

    def test_get_compilation_commands_with_grader(self):
        tt = Interactive([200, "grader", True, 128.0, 1.0, 5.0])
        cc = tt.get_compilation_commands(["foo.%l"])
        self.assertEqual(
            cc,
            {
                "L1": fake_compilation_commands(
                    COMPILATION_COMMAND_1, ["grader.l1", "foo.l1"], "foo"
                ),
                "L2": fake_compilation_commands(
                    COMPILATION_COMMAND_2, ["grader.l2", "foo.l2"], "foo.ext"
                ),
            },
        )

    def test_get_compilation_commands_alone(self):
        tt = Interactive([200, "alone", True, 128.0, 1.0, 5.0])
        cc = tt.get_compilation_commands(["foo.%l"])
        self.assertEqual(
            cc,
            {
                "L1": fake_compilation_commands(
                    COMPILATION_COMMAND_1, ["foo.l1"], "foo"
                ),
                "L2": fake_compilation_commands(
                    COMPILATION_COMMAND_2, ["foo.l2"], "foo.ext"
                ),
            },
        )

    def test_get_user_managers_with_grader(self):
        tt = Interactive([200, "grader", True, 128.0, 1.0, 5.0])
        self.assertEqual(tt.get_user_managers(), ["grader.%l"])

    def test_get_user_managers_alone(self):
        tt = Interactive([200, "alone", True, 128.0, 1.0, 5.0])
        self.assertEqual(tt.get_user_managers(), [])

    def test_get_auto_managers(self):
        tt = Interactive([200, "grader", True, 128.0, 1.0, 5.0])
        self.assertEqual(tt.get_auto_managers(), [])

    def test_compile_with_grader(self):
        tt = Interactive([200, "grader", True, 128.0, 1.0, 5.0])
        job = CompilationJob(
            language="L1",
            files={"foo.%l": FILE_FOO_L1},
            managers={"grader.l1": GRADER_L1},
        )
        sandbox = self.expect_sandbox()
        sandbox.get_file_to_storage.return_value = "exe_digest"
        self.compilation_step.return_value = (True, True, TEXT, STATS_OK)

        tt.compile(job, self.file_cacher)

        self.assertTrue(job.success)
        self.assertTrue(job.compilation_success)
        sandbox.create_file_from_storage.assert_any_call(
            "grader.l1", "digest of grader.l1", self.file_cacher
        )
        sandbox.create_file_from_storage.assert_any_call(
            "foo.l1", "digest of foo.l1", self.file_cacher
        )

    def test_compile_missing_grader(self):
        tt = Interactive([200, "grader", True, 128.0, 1.0, 5.0])
        job = CompilationJob(
            language="L1",
            files={"foo.%l": FILE_FOO_L1},
            managers={},
        )
        tt.compile(job, self.file_cacher)
        self.assertFalse(job.success)


if __name__ == "__main__":
    unittest.main()
