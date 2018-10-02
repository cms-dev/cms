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

"""Tests for whitediff.py."""

import unittest
from io import BytesIO

from cms.grading.steps import _WHITES, _white_diff


class TestWhiteDiff(unittest.TestCase):

    WHITES_STR = "".join(c.decode('utf-8') for c in _WHITES)

    @staticmethod
    def _diff(s1, s2):
        return _white_diff(
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
