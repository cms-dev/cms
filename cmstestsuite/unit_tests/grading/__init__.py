#!/usr/bin/env python2
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

"""Tests for common grading functions.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *
from future.builtins import *

import unittest
from io import BytesIO

from cms.grading import Sandbox, WHITES, \
    format_status_text, merge_evaluation_results, white_diff


class TestFormatStatusText(unittest.TestCase):

    @staticmethod
    def _tr(s):
        return s.replace("A", "E")

    def test_success_no_placeholders(self):
        self.assertEqual(format_status_text([]), "N/A")
        self.assertEqual(format_status_text([""]), "")
        self.assertEqual(format_status_text(["ASD"]), "ASD")
        self.assertEqual(format_status_text(["你好"]), "你好")

    def test_success_with_placeholders(self):
        self.assertEqual(format_status_text(["%s", "ASD"]), "ASD")
        self.assertEqual(format_status_text(["ASD%s\n%s", "QWE", "123"]),
                         "ASDQWE\n123")

    def test_success_with_translator(self):
        self.assertEqual(format_status_text([""], self._tr), "")
        self.assertEqual(format_status_text(["ASD"], self._tr), "ESD")
        # Translation is applied before formatting.
        self.assertEqual(format_status_text(["A%s", "ASD"], self._tr), "EASD")
        self.assertEqual(
            format_status_text(["AAA %s\n%s", "AAA", "AE"], self._tr),
            "EEE AAA\nAE")

    def test_insuccess(self):
        # Not enough elements for the placeholders.
        self.assertEqual(format_status_text(["%s"]), "N/A")
        self.assertEqual(format_status_text(["%s"], self._tr), "N/E")
        # No elements at all.
        self.assertEqual(format_status_text([]), "N/A")
        self.assertEqual(format_status_text([], self._tr), "N/E")


class TestMergeEvaluationResults(unittest.TestCase):

    @staticmethod
    def _res(execution_time, execution_wall_clock_time, execution_memory,
             exit_status, signal=None, filename=None):
        r = {
            "execution_time": execution_time,
            "execution_wall_clock_time": execution_wall_clock_time,
            "execution_memory": execution_memory,
            "exit_status": exit_status,
        }
        if signal is not None:
            r["signal"] = signal
        if filename is not None:
            r["filename"] = filename
        return r

    def assertRes(self, r0, r1):
        """Assert that r0 and r1 are the same result."""
        self.assertAlmostEqual(r0["execution_time"], r1["execution_time"])
        self.assertAlmostEqual(r0["execution_wall_clock_time"],
                               r1["execution_wall_clock_time"])
        self.assertAlmostEqual(r0["execution_memory"], r1["execution_memory"])
        self.assertEqual(r0["exit_status"], r1["exit_status"])
        for key in ["syscall", "signal", "filename"]:
            self.assertEqual(key in r0, key in r1)
            self.assertEqual(r0.get(key), r1.get(key))

    def test_success_status_ok(self):
        self.assertRes(
            merge_evaluation_results(
                self._res(1.0, 2.0, 300, Sandbox.EXIT_OK),
                self._res(0.1, 0.2, 0.3, Sandbox.EXIT_OK)),
            self._res(1.1, 2.0, 300.3, Sandbox.EXIT_OK))

    def test_success_first_status_ok(self):
        self.assertRes(
            merge_evaluation_results(
                self._res(0, 0, 0, Sandbox.EXIT_OK),
                self._res(0, 0, 0, Sandbox.EXIT_TIMEOUT)),
            self._res(0, 0, 0, Sandbox.EXIT_TIMEOUT))
        self.assertRes(
            merge_evaluation_results(
                self._res(0, 0, 0, Sandbox.EXIT_OK),
                self._res(0, 0, 0, Sandbox.EXIT_FILE_ACCESS, filename="asd")),
            self._res(0, 0, 0, Sandbox.EXIT_FILE_ACCESS, filename="asd"))
        self.assertRes(
            merge_evaluation_results(
                self._res(0, 0, 0, Sandbox.EXIT_OK),
                self._res(0, 0, 0, Sandbox.EXIT_SIGNAL, signal="11")),
            self._res(0, 0, 0, Sandbox.EXIT_SIGNAL, signal="11"))

    def test_success_first_status_not_ok(self):
        self.assertRes(
            merge_evaluation_results(
                self._res(0, 0, 0, Sandbox.EXIT_TIMEOUT),
                self._res(0, 0, 0, Sandbox.EXIT_SIGNAL, signal="11")),
            self._res(0, 0, 0, Sandbox.EXIT_TIMEOUT))
        self.assertRes(
            merge_evaluation_results(
                self._res(0, 0, 0, Sandbox.EXIT_FILE_ACCESS, filename="asd"),
                self._res(0, 0, 0, Sandbox.EXIT_SIGNAL, signal="11")),
            self._res(0, 0, 0, Sandbox.EXIT_FILE_ACCESS, filename="asd"))
        self.assertRes(
            merge_evaluation_results(
                self._res(0, 0, 0, Sandbox.EXIT_SIGNAL, signal="9"),
                self._res(0, 0, 0, Sandbox.EXIT_SIGNAL, signal="11")),
            self._res(0, 0, 0, Sandbox.EXIT_SIGNAL, signal="9"))
        self.assertRes(
            merge_evaluation_results(
                self._res(0, 0, 0, Sandbox.EXIT_SIGNAL, signal="9"),
                self._res(0, 0, 0, Sandbox.EXIT_OK)),
            self._res(0, 0, 0, Sandbox.EXIT_SIGNAL, signal="9"))

    def test_success_results_are_not_modified(self):
        r0 = self._res(1.0, 2.0, 300, Sandbox.EXIT_OK)
        r1 = self._res(0.1, 0.2, 0.3, Sandbox.EXIT_SIGNAL, signal="11")
        m = merge_evaluation_results(r0, r1)
        self.assertRes(
            m, self._res(1.1, 2.0, 300.3, Sandbox.EXIT_SIGNAL, signal="11"))
        self.assertRes(
            r0, self._res(1.0, 2.0, 300, Sandbox.EXIT_OK))
        self.assertRes(
            r1, self._res(0.1, 0.2, 0.3, Sandbox.EXIT_SIGNAL, signal="11"))


class TestWhiteDiff(unittest.TestCase):

    WHITES_STR = "".join(c.decode('utf-8') for c in WHITES)

    @staticmethod
    def _diff(s1, s2):
        return white_diff(
            BytesIO(s1.encode("utf-8")), BytesIO(s2.encode("utf-8")))

    def test_no_diff_one_token(self):
        self.assertTrue(self._diff("", ""))
        self.assertTrue(self._diff("1", "1"))
        self.assertTrue(self._diff("a", "a"))
        self.assertTrue(self._diff("你好", "你好"))

    def test_no_diff_one_token_and_whites(self):
        self.assertTrue(self._diff("1   ", "1"))
        self.assertTrue(self._diff("   1", "1"))
        self.assertTrue(self._diff("1" + TestWhiteDiff.WHITES_STR, "1"))

    def test_no_diff_one_token_and_trailing_blank_lines(self):
        self.assertTrue(self._diff("1\n", "1"))
        self.assertTrue(self._diff("1\n\n\n\n", "1"))
        self.assertTrue(self._diff("1\n\n\n\n", "1\n"))
        self.assertTrue(self._diff("1\n\r\r \n  \n\n", "1   \n\r  "))

    def test_no_diff_multiple_tokens(self):
        self.assertTrue(self._diff("1 asd\n\n\n", "   1\tasd  \n"))
        self.assertTrue(self._diff("1 2\n\n\n", "1 2\n"))
        self.assertTrue(self._diff("1\t\r2", "1 2"))
        self.assertTrue(self._diff("1 2", "1 2" + TestWhiteDiff.WHITES_STR))

    def test_diff_wrong_tokens(self):
        self.assertFalse(self._diff("1 2", "12"))
        self.assertFalse(self._diff("1 23", "12 3"))
        self.assertFalse(self._diff("1", "01"))
        self.assertFalse(self._diff("1.0", "1"))

    def test_diff_wrong_line(self):
        self.assertFalse(self._diff("\n1", "1"))
        self.assertFalse(self._diff("1 2", "1\n2"))
        self.assertFalse(self._diff("1\n\n2", "1\n2"))


if __name__ == "__main__":
    unittest.main()
