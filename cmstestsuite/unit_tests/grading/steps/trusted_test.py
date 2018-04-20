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

"""Tests for the trusted step."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa
from six import PY2

import unittest

from mock import patch

from cms.grading.Sandbox import Sandbox
from cms.grading.steps import extract_outcome_and_text, trusted_step
from cmstestsuite.unit_tests.grading.steps.fakeisolatesandbox \
    import FakeIsolateSandbox
from cmstestsuite.unit_tests.grading.steps.stats_test import get_stats


INVALID_UTF8 = b"\xc3\x28"


ONE_COMMAND = [["test", "command"]]
TWO_COMMANDS = [["test", "command", "1"], ["command", "2"]]


class TestExtractOutcomeAndText(unittest.TestCase):

    def setUp(self):
        super(TestExtractOutcomeAndText, self).setUp()
        self.sandbox = FakeIsolateSandbox(True, None)
        self.sandbox.stdout_file = "o"
        self.sandbox.stderr_file = "e"

    def test_success(self):
        self.sandbox.fake_file("o", b"0.45\n")
        self.sandbox.fake_file("e", "你好.\n".encode("utf-8"))
        outcome, text = extract_outcome_and_text(self.sandbox)
        self.assertEqual(outcome, 0.45)
        self.assertEqual(text, ["你好."])

    def test_following_lines_ignored(self):
        self.sandbox.fake_file("o", b"0.45\nNothing\n")
        self.sandbox.fake_file("e", b"Text to return.\nto see here")
        outcome, text = extract_outcome_and_text(self.sandbox)
        self.assertEqual(outcome, 0.45)
        self.assertEqual(text, ["Text to return."])

    def test_works_without_newlines(self):
        self.sandbox.fake_file("o", b"0.45")
        self.sandbox.fake_file("e", b"Text to return.")
        outcome, text = extract_outcome_and_text(self.sandbox)
        self.assertEqual(outcome, 0.45)
        self.assertEqual(text, ["Text to return."])

    def test_text_is_stripped(self):
        self.sandbox.fake_file("o", b"   0.45\t \nignored")
        self.sandbox.fake_file("e", b"\t  Text to return.\r\n")
        outcome, text = extract_outcome_and_text(self.sandbox)
        self.assertEqual(outcome, 0.45)
        self.assertEqual(text, ["Text to return."])

    def test_text_is_translated(self):
        self.sandbox.fake_file("o", b"0.45\n")
        self.sandbox.fake_file("e", b"translate:success\n")
        outcome, text = extract_outcome_and_text(self.sandbox)
        self.assertEqual(outcome, 0.45)
        self.assertEqual(text, ["Output is correct"])

    def test_failure_not_a_float(self):
        self.sandbox.fake_file("o", b"not a float\n")
        self.sandbox.fake_file("e", b"Text to return.\n")
        with self.assertRaises(ValueError):
            extract_outcome_and_text(self.sandbox)

    def test_failure_invalid_utf8(self):
        self.sandbox.fake_file("o", b"0.45")
        self.sandbox.fake_file("e", INVALID_UTF8)
        with self.assertRaises(ValueError):
            extract_outcome_and_text(self.sandbox)

    @unittest.skipIf(PY2, "Python 2 does not have FileNotFoundError.")
    def test_failure_missing_file(self):
        self.sandbox.fake_file("o", b"0.45\n")
        with self.assertRaises(FileNotFoundError):
            extract_outcome_and_text(self.sandbox)


class TestTrustedStep(unittest.TestCase):

    def setUp(self):
        super(TestTrustedStep, self).setUp()
        self.sandbox = FakeIsolateSandbox(True, None)

        patcher = patch("cms.grading.steps.trusted.logger.error")
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
        with patch("cms.grading.steps.trusted.generic_step",
                   return_value=expected_stats) as mock_generic_step:
            success, trusted_success, stats = trusted_step(
                self.sandbox, ONE_COMMAND)

        mock_generic_step.assert_called_once_with(
            self.sandbox, ONE_COMMAND, "trusted")
        self.assertLoggedError(False)
        self.assertTrue(success)
        self.assertTrue(trusted_success)
        self.assertEqual(stats, expected_stats)

    def test_single_commands_trusted_failed_nonzero_return(self):
        expected_stats = get_stats(
            0.1, 0.5, 1000 * 1024, Sandbox.EXIT_NONZERO_RETURN,
            stdout="o", stderr="e")
        with patch("cms.grading.steps.trusted.generic_step",
                   return_value=expected_stats):
            success, trusted_success, stats = trusted_step(
                self.sandbox, ONE_COMMAND)

        # Trusted steps should always succeed, if not, should notify the admin.
        self.assertLoggedError()
        self.assertTrue(success)
        self.assertFalse(trusted_success)
        self.assertEqual(stats, expected_stats)

    def test_single_commands_trusted_failed_timeout(self):
        # This case is a "success" for the sandbox (it's the user's fault),
        # but trusted is unsuccessful (no executable).
        expected_stats = get_stats(
            0.1, 0.5, 1000 * 1024, Sandbox.EXIT_TIMEOUT,
            stdout="o", stderr="e")
        with patch("cms.grading.steps.trusted.generic_step",
                   return_value=expected_stats):
            success, trusted_success, stats = trusted_step(
                self.sandbox, ONE_COMMAND)

        # Trusted steps should always succeed, if not, should notify the admin.
        self.assertLoggedError()
        self.assertTrue(success)
        self.assertFalse(trusted_success)
        self.assertEqual(stats, expected_stats)

    def test_single_commands_trusted_failed_timeout_wall(self):
        # This case is a "success" for the sandbox (it's the user's fault),
        # but trusted is unsuccessful (no executable).
        expected_stats = get_stats(
            0.1, 0.5, 1000 * 1024, Sandbox.EXIT_TIMEOUT_WALL,
            stdout="o", stderr="e")
        with patch("cms.grading.steps.trusted.generic_step",
                   return_value=expected_stats):
            success, trusted_success, stats = trusted_step(
                self.sandbox, ONE_COMMAND)

        # Trusted steps should always succeed, if not, should notify the admin.
        self.assertLoggedError()
        self.assertTrue(success)
        self.assertFalse(trusted_success)
        self.assertEqual(stats, expected_stats)

    def test_single_commands_trusted_failed_signal(self):
        # This case is a "success" for the sandbox (it's the user's fault),
        # but trusted is unsuccessful (no executable).
        expected_stats = get_stats(
            0.1, 0.5, 1000 * 1024, Sandbox.EXIT_SIGNAL, signal=11,
            stdout="o", stderr="e")
        with patch("cms.grading.steps.trusted.generic_step",
                   return_value=expected_stats):
            success, trusted_success, stats = trusted_step(
                self.sandbox, ONE_COMMAND)

        # Trusted steps should always succeed, if not, should notify the admin.
        self.assertLoggedError()
        self.assertTrue(success)
        self.assertFalse(trusted_success)
        self.assertEqual(stats, expected_stats)

    def test_single_commands_sandbox_failed(self):
        with patch("cms.grading.steps.trusted.generic_step",
                   return_value=None):
            success, trusted_success, stats = trusted_step(
                self.sandbox, ONE_COMMAND)

        # Sandbox should never fail. If it does, should notify the admin.
        self.assertLoggedError()
        self.assertFalse(success)
        self.assertIsNone(trusted_success)
        self.assertIsNone(stats)

    def test_multiple_commands_success(self):
        expected_stats = get_stats(
            0.1, 0.5, 1000 * 1024, Sandbox.EXIT_OK, stdout="o", stderr="你好")
        with patch("cms.grading.steps.trusted.generic_step",
                   return_value=expected_stats) as mock_generic_step:
            success, trusted_success, stats = trusted_step(
                self.sandbox, TWO_COMMANDS)

        self.assertLoggedError(False)
        mock_generic_step.assert_called_once_with(
            self.sandbox, TWO_COMMANDS, "trusted")
        self.assertTrue(success)
        self.assertTrue(trusted_success)
        self.assertEqual(stats, expected_stats)


if __name__ == "__main__":
    unittest.main()
