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

"""Tests for the step utils."""

import unittest

from cms.grading.Sandbox import Sandbox
from cms.grading.steps.utils import generic_step
from cmstestsuite.unit_tests.grading.steps.fakeisolatesandbox \
    import FakeIsolateSandbox
from cmstestsuite.unit_tests.grading.steps.stats_test import get_stats


INVALID_UTF8 = b"\xc3\x28"


ONE_COMMAND = [["test", "command"]]
TWO_COMMANDS = [["test", "command", "1"], ["command", "2"]]


class TestGenericStep(unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.sandbox = FakeIsolateSandbox(None)

    def test_single_command_success(self):
        self.sandbox.fake_execute_data(
            True, b"o", "你好".encode("utf-8"), 0.1, 0.5, 1000, "OK")

        stats = generic_step(self.sandbox, ONE_COMMAND, "name",
                             collect_output=True)

        # Stdout and stderr are encoded in UTF-8.
        self.assertEqual(
            stats, get_stats(0.1, 0.5, 1000 * 1024, Sandbox.EXIT_OK,
                             stdout="o", stderr="你好"))
        # Generic step always redirects stdout and stderr.
        self.assertEqual(self.sandbox.stdout_file, "name_stdout_0.txt")
        self.assertEqual(self.sandbox.stderr_file, "name_stderr_0.txt")

    def test_single_command_success_no_collect_output(self):
        self.sandbox.fake_execute_data(
            True, b"o", "你好".encode("utf-8"), 0.1, 0.5, 1000, "OK")

        stats = generic_step(self.sandbox, ONE_COMMAND, "name",
                             collect_output=False)

        # No output collected on stats.
        self.assertEqual(
            stats, get_stats(0.1, 0.5, 1000 * 1024, Sandbox.EXIT_OK))
        # Generic step always redirects stdout and stderr.
        self.assertEqual(self.sandbox.stdout_file, "name_stdout_0.txt")
        self.assertEqual(self.sandbox.stderr_file, "name_stderr_0.txt")

    def test_single_command_nonzero_return(self):
        self.sandbox.fake_execute_data(True, b"o", b"e", 0.1, 0.5, 1000, "RE")

        stats = generic_step(self.sandbox, ONE_COMMAND, "name")

        self.assertEqual(stats, get_stats(0.1, 0.5, 1000 * 1024,
                                          Sandbox.EXIT_NONZERO_RETURN))

    def test_single_command_failed_timeout(self):
        self.sandbox.fake_execute_data(True, b"o", b"e", 0.1, 0.5, 1000, "TO")

        stats = generic_step(self.sandbox, ONE_COMMAND, "name")

        self.assertEqual(stats, get_stats(0.1, 0.5, 1000 * 1024,
                                          Sandbox.EXIT_TIMEOUT))

    def test_single_command_failed_timeout_wall(self):
        self.sandbox.fake_execute_data(
            True, b"o", b"e", 0.1, 0.5, 1000, "TO",
            message="Time limit exceeded (wall clock)")

        stats = generic_step(self.sandbox, ONE_COMMAND, "name")

        self.assertEqual(stats, get_stats(0.1, 0.5, 1000 * 1024,
                                          Sandbox.EXIT_TIMEOUT_WALL))

    def test_single_command_failed_signal(self):
        self.sandbox.fake_execute_data(
            True, b"o", b"e", 0.1, 0.5, 1000, "SG", signal=11)

        stats = generic_step(self.sandbox, ONE_COMMAND, "name")

        self.assertEqual(stats, get_stats(0.1, 0.5, 1000 * 1024,
                                          Sandbox.EXIT_SIGNAL, signal=11))

    def test_single_command_sandbox_failed(self):
        self.sandbox.fake_execute_data(
            False, b"o", b"e", 0.1, 0.5, 1000, "XX")

        stats = generic_step(self.sandbox, ONE_COMMAND, "name")

        self.assertIsNone(stats)

    def test_multiple_commands_success(self):
        self.sandbox.fake_execute_data(
            True, b"o1", b"e1", 0.1, 0.5, 1000, "OK")
        self.sandbox.fake_execute_data(
            True, b"o2", b"e2", 1.0, 5.0, 10_000, "OK")

        stats = generic_step(self.sandbox, TWO_COMMANDS, "name",
                             collect_output=True)

        # 2 commands executed, with exec_num 0 and 1
        self.assertEquals(self.sandbox.exec_num, 1)
        # Stats are the combination of the two.
        self.assertEqual(stats, get_stats(1.1,  # sum
                                          5.5,  # sum
                                          10_000 * 1024,  # max
                                          Sandbox.EXIT_OK,
                                          stdout="o1\n===\no2",
                                          stderr="e1\n===\ne2"))

    def test_multiple_commands_failure_terminates_early(self):
        self.sandbox.fake_execute_data(
            True, b"o1", b"e1", 0.1, 0.5, 1000, "RE")
        self.sandbox.fake_execute_data(
            True, b"o2", b"e2", 1.0, 5.0, 10_000, "OK")

        stats = generic_step(self.sandbox, TWO_COMMANDS, "name",
                             collect_output=True)

        # 1 command executed (generic terminates early), with exec_num 0.
        self.assertEquals(self.sandbox.exec_num, 0)
        # Stats are only for the first command.
        self.assertEqual(stats, get_stats(
            0.1, 0.5, 1000 * 1024, Sandbox.EXIT_NONZERO_RETURN,
            stdout="o1", stderr="e1"))

    def test_multiple_commands_sandbox_failure_terminates_early(self):
        self.sandbox.fake_execute_data(
            False, b"o1", b"e1", 0.1, 0.5, 1000, "XX")
        self.sandbox.fake_execute_data(
            True, b"o2", b"e2", 1.0, 5.0, 10_000, "OK")

        stats = generic_step(self.sandbox, TWO_COMMANDS, "name")

        # 1 command executed (generic terminates early), with exec_num 0.
        self.assertEquals(self.sandbox.exec_num, 0)
        self.assertIsNone(stats)

    def test_invalid_utf8_in_output(self):
        self.sandbox.fake_execute_data(
            True,
            b"o" + INVALID_UTF8 + b"1",
            b"e" + INVALID_UTF8 + b"2",
            0.1, 0.5, 1000, "OK")

        stats = generic_step(self.sandbox, ONE_COMMAND, "name",
                             collect_output=True)

        # UTF-8 invalid parts are replaced with funny question marks (\uFFFD).
        self.assertRegex(stats["stdout"], "^o.*1$")
        self.assertRegex(stats["stderr"], "^e.*2$")


if __name__ == "__main__":
    unittest.main()
