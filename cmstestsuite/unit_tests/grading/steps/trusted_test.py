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

"""Tests for the trusted step."""

import unittest
from unittest.mock import ANY, MagicMock, call, patch

from cms.grading.Sandbox import Sandbox
from cms.grading.steps import extract_outcome_and_text, trusted_step, \
    checker_step, trusted
from cmstestsuite.unit_tests.grading.steps.fakeisolatesandbox \
    import FakeIsolateSandbox
from cmstestsuite.unit_tests.grading.steps.stats_test import get_stats


INVALID_UTF8 = b"\xc3\x28"


ONE_COMMAND = [["test", "command"]]
TWO_COMMANDS = [["test", "command", "1"], ["command", "2"]]


class TestExtractOutcomeAndText(unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.sandbox = FakeIsolateSandbox(None)
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

    def test_failure_missing_file(self):
        self.sandbox.fake_file("o", b"0.45\n")
        with self.assertRaises(FileNotFoundError):
            extract_outcome_and_text(self.sandbox)


class TestTrustedStep(unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.sandbox = FakeIsolateSandbox(None)

        patcher = patch("cms.grading.steps.trusted.logger.error",
                        wraps=trusted.logger.error)
        self.addCleanup(patcher.stop)
        self.mock_logger_error = patcher.start()

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


class TestCheckerStep(unittest.TestCase):

    def setUp(self):
        super().setUp()
        # By default, any file request succeeds.
        self.file_cacher = MagicMock()
        self.sandbox = FakeIsolateSandbox(self.file_cacher)

        patcher = patch("cms.grading.steps.trusted.trusted_step")
        self.addCleanup(patcher.stop)
        self.mock_trusted_step = patcher.start()

        patcher = patch("cms.grading.steps.trusted.logger.error",
                        wraps=trusted.logger.error)
        self.addCleanup(patcher.stop)
        self.mock_logger_error = patcher.start()

    def assertLoggedError(self, logged=True):
        if logged:
            self.mock_logger_error.assert_called()
        else:
            self.mock_logger_error.assert_not_called()

    def set_checker_output(self, outcome, text):
        self.sandbox.stdout_file = "stdout_file"
        self.sandbox.stderr_file = "stderr_file"
        if outcome is not None:
            self.sandbox.fake_file(self.sandbox.stdout_file, outcome)
        if text is not None:
            self.sandbox.fake_file(self.sandbox.stderr_file, text)

    def test_success(self):
        self.mock_trusted_step.return_value = (True, True, {})
        self.set_checker_output(b"0.123\n", b"Text.\n")

        ret = checker_step(self.sandbox, "c_dig", "i_dig", "co_dig", "o")

        self.assertEqual(ret, (True, 0.123, ["Text."]))
        self.file_cacher.get_file_to_fobj.assert_has_calls([
            call("c_dig", ANY),
            call("i_dig", ANY),
            call("co_dig", ANY),
        ], any_order=True)
        self.mock_trusted_step.assert_called_once_with(
            self.sandbox, [["./checker", trusted.CHECKER_INPUT_FILENAME,
                            trusted.CHECKER_CORRECT_OUTPUT_FILENAME, "o"]])
        self.assertLoggedError(False)

    def test_sandbox_failure(self):
        self.mock_trusted_step.return_value = (False, None, None)
        # Output files are ignored.
        self.set_checker_output(b"0.123\n", b"Text.\n")

        ret = checker_step(self.sandbox, "c_dig", "i_dig", "co_dig", "o")

        self.assertEqual(ret, (False, None, None))
        self.assertLoggedError()

    def test_checker_failure(self):
        self.mock_trusted_step.return_value = (True, False, {})
        # Output files are ignored.
        self.set_checker_output(b"0.123\n", b"Text.\n")

        ret = checker_step(self.sandbox, "c_dig", "i_dig", "co_dig", "o")

        self.assertEqual(ret, (False, None, None))
        self.assertLoggedError()

    def test_missing_checker(self):
        ret = checker_step(self.sandbox, None, "i_dig", "co_dig", "o")

        self.mock_trusted_step.assert_not_called()
        self.assertEqual(ret, (False, None, None))
        self.assertLoggedError()

    def test_checker_already_in_sandbox(self):
        self.sandbox.fake_file(trusted.CHECKER_FILENAME, b"something")
        ret = checker_step(self.sandbox, "c_dig", "i_dig", "co_dig", "o")

        self.assertEqual(ret, (False, None, None))
        self.assertLoggedError()

    def test_input_already_in_sandbox(self):
        self.sandbox.fake_file(trusted.CHECKER_INPUT_FILENAME, b"something")
        ret = checker_step(self.sandbox, "c_dig", "i_dig", "co_dig", "o")

        self.assertEqual(ret, (False, None, None))
        self.assertLoggedError()

    def test_correct_output_already_in_sandbox(self):
        self.sandbox.fake_file(trusted.CHECKER_CORRECT_OUTPUT_FILENAME,
                               b"something")
        ret = checker_step(self.sandbox, "c_dig", "i_dig", "co_dig", "o")

        self.assertEqual(ret, (False, None, None))
        self.assertLoggedError()

    def test_invalid_checker_outcome(self):
        self.mock_trusted_step.return_value = (True, True, {})
        self.set_checker_output(b"A0.123\n", b"Text.\n")

        ret = checker_step(self.sandbox, "c_dig", "i_dig", "co_dig", "o")

        self.assertEqual(ret, (False, None, None))
        self.assertLoggedError()

    def test_invalid_checker_text(self):
        self.mock_trusted_step.return_value = (True, True, {})
        self.set_checker_output(b"0.123\n", INVALID_UTF8)

        ret = checker_step(self.sandbox, "c_dig", "i_dig", "co_dig", "o")

        self.assertEqual(ret, (False, None, None))
        self.assertLoggedError()

    def test_missing_checker_outcome(self):
        self.mock_trusted_step.return_value = (True, True, {})
        self.set_checker_output(None, b"Text.\n")

        ret = checker_step(self.sandbox, "c_dig", "i_dig", "co_dig", "o")

        self.assertEqual(ret, (False, None, None))
        self.assertLoggedError()

    def test_missing_checker_text(self):
        self.mock_trusted_step.return_value = (True, True, {})
        self.set_checker_output(b"0.123\n", None)

        ret = checker_step(self.sandbox, "c_dig", "i_dig", "co_dig", "o")

        self.assertEqual(ret, (False, None, None))
        self.assertLoggedError()


if __name__ == "__main__":
    unittest.main()
