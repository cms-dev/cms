#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

"""Tests for the compilation step."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa
from six import assertRegex

import unittest

from cms.grading.Sandbox import Sandbox
from cms.grading.steps import compilation_step
from cmstestsuite.unit_tests.grading.steps.fakeisolatesandbox \
    import FakeIsolateSandbox
from cmstestsuite.unit_tests.grading.steps.stats_test import get_stats


INVALID_UTF8 = b"\xc3\x28"


class TestCompilationStep(unittest.TestCase):

    def setUp(self):
        super(TestCompilationStep, self).setUp()
        self.sandbox = FakeIsolateSandbox(True, None)

    def test_single_command_success(self):
        self.sandbox.fake_execute_data(
            True, b"o", "你好".encode("utf-8"), 0.1, 0.5, 1000, "OK")

        success, compilation_success, text, stats = compilation_step(
            self.sandbox, [["test", "command"]])

        self.assertTrue(success)
        self.assertTrue(compilation_success)
        # Stdout and stderr are encoded in UTF-8.
        self.assertEqual(
            stats, get_stats(0.1, 0.5, 1000 * 1024, Sandbox.EXIT_OK,
                             stdout="o", stderr="你好"))

    def test_single_commands_compilation_failed_nonzero_return(self):
        # This case is a "success" for the sandbox (it's the user's fault),
        # but compilation is unsuccessful (no executable).
        self.sandbox.fake_execute_data(
            True, b"o", b"e", 0.1, 0.5, 1000, "RE")

        success, compilation_success, text, stats = compilation_step(
            self.sandbox, [["test", "command"]])

        self.assertTrue(success)
        self.assertFalse(compilation_success)
        self.assertEqual(stats,
                         get_stats(0.1, 0.5, 1000 * 1024,
                                   Sandbox.EXIT_NONZERO_RETURN,
                                   stdout="o", stderr="e"))

    def test_single_commands_compilation_failed_timeout(self):
        # This case is a "success" for the sandbox (it's the user's fault),
        # but compilation is unsuccessful (no executable).
        self.sandbox.fake_execute_data(
            True, b"o", b"e", 0.1, 0.5, 1000, "TO")

        success, compilation_success, text, stats = compilation_step(
            self.sandbox, [["test", "command"]])

        self.assertTrue(success)
        self.assertFalse(compilation_success)
        self.assertEqual(stats,
                         get_stats(0.1, 0.5, 1000 * 1024,
                                   Sandbox.EXIT_TIMEOUT,
                                   stdout="o", stderr="e"))

    def test_single_commands_compilation_failed_signal(self):
        # This case is a "success" for the sandbox (it's the user's fault),
        # but compilation is unsuccessful (no executable).
        self.sandbox.fake_execute_data(
            True, b"o", b"e", 0.1, 0.5, 1000, "SG", signal=11)

        success, compilation_success, text, stats = compilation_step(
            self.sandbox, [["test", "command"]])

        self.assertTrue(success)
        self.assertFalse(compilation_success)
        self.assertEqual(stats,
                         get_stats(0.1, 0.5, 1000 * 1024,
                                   Sandbox.EXIT_SIGNAL, signal=11,
                                   stdout="o", stderr="e"))

    def test_single_commands_sandbox_failed(self):
        self.sandbox.fake_execute_data(
            False, b"o", b"e", 0.1, 0.5, 1000, "XX")

        success, compilation_success, text, stats = compilation_step(
            self.sandbox, [["test", "command"]])

        self.assertFalse(success)
        self.assertIsNone(compilation_success)
        self.assertIsNone(text)
        self.assertIsNone(stats)

    def test_multiple_commands_success(self):
        self.sandbox.fake_execute_data(
            True, b"o1", b"e1", 0.1, 0.5, 1000, "OK")
        self.sandbox.fake_execute_data(
            True, b"o2", b"e2", 1.0, 5.0, 10000, "OK")

        success, compilation_success, text, stats = compilation_step(
            self.sandbox, [["test", "command", "1"], ["command2"]])

        # 2 commands executed, with exec_num 0 and 1
        self.assertEquals(self.sandbox.exec_num, 1)

        self.assertTrue(success)
        self.assertTrue(compilation_success)
        # Stats are the combination of the two.
        self.assertEqual(stats, get_stats(1.1,  # sum
                                          5.5,  # sum
                                          10000 * 1024,  # max
                                          Sandbox.EXIT_OK,
                                          stdout="o1\n===\no2",
                                          stderr="e1\n===\ne2"))

    def test_multiple_commands_compilation_failure_terminates_early(self):
        self.sandbox.fake_execute_data(
            True, b"o1", b"e1", 0.1, 0.5, 1000, "RE")
        self.sandbox.fake_execute_data(
            True, b"o2", b"e2", 1.0, 5.0, 10000, "OK")

        success, compilation_success, text, stats = compilation_step(
            self.sandbox, [["test", "command", "1"], ["command2"]])

        # 1 command executed (compilation terminates early), with exec_num 0.
        self.assertEquals(self.sandbox.exec_num, 0)

        self.assertTrue(success)
        self.assertFalse(compilation_success)
        # Stats are only for the first command.
        self.assertEqual(stats, get_stats(
            0.1, 0.5, 1000 * 1024, Sandbox.EXIT_NONZERO_RETURN,
            stdout="o1", stderr="e1"))

    def test_multiple_commands_sandbox_failure_terminates_early(self):
        self.sandbox.fake_execute_data(
            False, b"o1", b"e1", 0.1, 0.5, 1000, "XX")
        self.sandbox.fake_execute_data(
            True, b"o2", b"e2", 1.0, 5.0, 10000, "OK")

        success, compilation_success, text, stats = compilation_step(
            self.sandbox, [["test", "command", "1"], ["command2"]])

        # 1 command executed (compilation terminates early), with exec_num 0.
        self.assertEquals(self.sandbox.exec_num, 0)

        self.assertFalse(success)
        self.assertIsNone(compilation_success)
        self.assertIsNone(text)
        self.assertIsNone(stats)

    def test_invalid_utf8_in_output(self):
        self.sandbox.fake_execute_data(
            True,
            b"o" + INVALID_UTF8 + b"1",
            b"e" + INVALID_UTF8 + b"2",
            0.1, 0.5, 1000, "OK")

        success, compilation_success, text, stats = compilation_step(
            self.sandbox, [["test", "command"]])

        self.assertTrue(success)
        self.assertTrue(compilation_success)
        # UTF-8 invalid parts are replaced with funny question marks (\uFFFD).
        assertRegex(self, stats["stdout"], "^o.*1$")
        assertRegex(self, stats["stderr"], "^e.*2$")


if __name__ == "__main__":
    unittest.main()
