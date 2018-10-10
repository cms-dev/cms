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

"""Tests for the compilation step."""

import unittest
from unittest.mock import patch

from cms.grading.Sandbox import Sandbox
from cms.grading.steps import COMPILATION_MESSAGES, compilation_step
from cmstestsuite.unit_tests.grading.steps.fakeisolatesandbox \
    import FakeIsolateSandbox
from cmstestsuite.unit_tests.grading.steps.stats_test import get_stats


ONE_COMMAND = [["test", "command"]]
TWO_COMMANDS = [["test", "command", "1"], ["command", "2"]]


class TestCompilationStep(unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.sandbox = FakeIsolateSandbox(None)

        patcher = patch("cms.grading.steps.compilation.logger.error")
        self.mock_logger_error = patcher.start()
        self.addCleanup(patcher.stop)

    def assertLoggedError(self, logged=True):
        if logged:
            self.mock_logger_error.assert_called()
        else:
            self.mock_logger_error.assert_not_called()

    def test_single_command_success(self):
        expected_stats = get_stats(
            0.1, 0.5, 1000 * 1024, Sandbox.EXIT_OK, stdout="o", stderr="你好")
        with patch("cms.grading.steps.compilation.generic_step",
                   return_value=expected_stats) as mock_generic_step:
            success, compilation_success, text, stats = compilation_step(
                self.sandbox, ONE_COMMAND)

        mock_generic_step.assert_called_once_with(
            self.sandbox, ONE_COMMAND, "compilation", collect_output=True)
        self.assertLoggedError(False)
        self.assertTrue(success)
        self.assertTrue(compilation_success)
        self.assertEqual(text, [COMPILATION_MESSAGES.get("success").message])
        self.assertEqual(stats, expected_stats)

    def test_single_command_compilation_failed_nonzero_return(self):
        # This case is a "success" for the sandbox (it's the user's fault),
        # but compilation is unsuccessful (no executable).
        expected_stats = get_stats(
            0.1, 0.5, 1000 * 1024, Sandbox.EXIT_NONZERO_RETURN,
            stdout="o", stderr="e")
        with patch("cms.grading.steps.compilation.generic_step",
                   return_value=expected_stats):
            success, compilation_success, text, stats = compilation_step(
                self.sandbox, ONE_COMMAND)

        # User's fault, no error needs to be logged.
        self.assertLoggedError(False)
        self.assertTrue(success)
        self.assertFalse(compilation_success)
        self.assertEqual(text, [COMPILATION_MESSAGES.get("fail").message])
        self.assertEqual(stats, expected_stats)

    def test_single_command_compilation_failed_timeout(self):
        # This case is a "success" for the sandbox (it's the user's fault),
        # but compilation is unsuccessful (no executable).
        expected_stats = get_stats(
            0.1, 0.5, 1000 * 1024, Sandbox.EXIT_TIMEOUT,
            stdout="o", stderr="e")
        with patch("cms.grading.steps.compilation.generic_step",
                   return_value=expected_stats):
            success, compilation_success, text, stats = compilation_step(
                self.sandbox, ONE_COMMAND)

        # User's fault, no error needs to be logged.
        self.assertLoggedError(False)
        self.assertTrue(success)
        self.assertFalse(compilation_success)
        self.assertEqual(text, [COMPILATION_MESSAGES.get("timeout").message])
        self.assertEqual(stats, expected_stats)

    def test_single_command_compilation_failed_timeout_wall(self):
        # This case is a "success" for the sandbox (it's the user's fault),
        # but compilation is unsuccessful (no executable).
        expected_stats = get_stats(
            0.1, 0.5, 1000 * 1024, Sandbox.EXIT_TIMEOUT_WALL,
            stdout="o", stderr="e")
        with patch("cms.grading.steps.compilation.generic_step",
                   return_value=expected_stats):
            success, compilation_success, text, stats = compilation_step(
                self.sandbox, ONE_COMMAND)

        # User's fault, no error needs to be logged.
        self.assertLoggedError(False)
        self.assertTrue(success)
        self.assertFalse(compilation_success)
        self.assertEqual(text, [COMPILATION_MESSAGES.get("timeout").message])
        self.assertEqual(stats, expected_stats)

    def test_single_command_compilation_failed_signal(self):
        # This case is a "success" for the sandbox (it's the user's fault),
        # but compilation is unsuccessful (no executable).
        expected_stats = get_stats(
            0.1, 0.5, 1000 * 1024, Sandbox.EXIT_SIGNAL, signal=11,
            stdout="o", stderr="e")
        with patch("cms.grading.steps.compilation.generic_step",
                   return_value=expected_stats):
            success, compilation_success, text, stats = compilation_step(
                self.sandbox, ONE_COMMAND)

        # User's fault, no error needs to be logged.
        self.assertLoggedError(False)
        self.assertTrue(success)
        self.assertFalse(compilation_success)
        self.assertEqual(text,
                         [COMPILATION_MESSAGES.get("signal").message, "11"])
        self.assertEqual(stats, expected_stats)

    def test_single_command_sandbox_failed(self):
        with patch("cms.grading.steps.compilation.generic_step",
                   return_value=None):
            success, compilation_success, text, stats = compilation_step(
                self.sandbox, ONE_COMMAND)

        # Sandbox should never fail. If it does, should notify the admin.
        self.assertLoggedError()
        self.assertFalse(success)
        self.assertIsNone(compilation_success)
        self.assertIsNone(text)
        self.assertIsNone(stats)

    def test_multiple_commands_success(self):
        expected_stats = get_stats(
            0.1, 0.5, 1000 * 1024, Sandbox.EXIT_OK, stdout="o", stderr="你好")
        with patch("cms.grading.steps.compilation.generic_step",
                   return_value=expected_stats) as mock_generic_step:
            success, compilation_success, text, stats = compilation_step(
                self.sandbox, TWO_COMMANDS)

        mock_generic_step.assert_called_once_with(
            self.sandbox, TWO_COMMANDS, "compilation", collect_output=True)
        self.assertLoggedError(False)
        self.assertTrue(success)
        self.assertTrue(compilation_success)
        self.assertEqual(text, [COMPILATION_MESSAGES.get("success").message])
        self.assertEqual(stats, expected_stats)


if __name__ == "__main__":
    unittest.main()
