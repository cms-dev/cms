#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2025 Ron Ryvchin <ron.ryv@gmail.com>
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

from cms.grading.steps import _EPS, _real_numbers_compare

_PREC = 12
def f(x: float) -> str:
    return f"{x:.{_PREC}f}"

_ACC = 1e-10
_NOISE = _EPS - _ACC
_DIFF = _EPS + _ACC

class TestWhiteDiff(unittest.TestCase):

    @staticmethod
    def _cmp(s1, s2):
        return _real_numbers_compare(
            BytesIO(s1.encode("utf-8")), BytesIO(s2.encode("utf-8")))

    # --- Tokenization ----------------------------------------------------------------
    
    def test_no_numbers_equal(self):
        self.assertTrue(self._cmp("", ""))
        self.assertTrue(self._cmp("Daniel W", "Ron R"))
        self.assertTrue(self._cmp("你好", "谢谢"))
    
    def test_no_diff_one_token_and_whites(self):
        self.assertTrue(self._cmp("1.0   ", "1.0"))
        self.assertTrue(self._cmp("   1.0", "1.0"))
        self.assertTrue(self._cmp(" The answer is  1.0 thanks", "It should be 1.0 ok?"))
        self.assertFalse(self._cmp(" The answer is  1.0 thanks", "It should be 1.5 ok?"))

    def test_no_diff_multiple_tokens_and_whites(self):
        self.assertTrue(self._cmp("1\n2\n3", "1 2 3"))
        self.assertTrue(self._cmp(" \t 1 \r\n 2 \f 3 \v ", "1 2 3"))

    def test_accepted_formats(self):
        self.assertTrue(self._cmp(".5", "0.5"))
        self.assertTrue(self._cmp("+3.000", "3"))
        self.assertTrue(self._cmp("12.", "12"))
        self.assertTrue(self._cmp("-0.0", "0"))

    def test_multiple_numbers_basic(self):
        self.assertTrue(self._cmp("1 2.0 3", "1.000 2 3."))
        self.assertFalse(self._cmp("1 2 3", "1 3 2"))
        self.assertFalse(self._cmp("1 2.0 3", "1.000 2 3. 4"))

    # --- Absolute accuracy -----------------------------------------------------------
    
    def test_absolute_tolerance_pass(self):
        self.assertTrue(self._cmp(f(_NOISE), "0")) 
        self.assertTrue(self._cmp("0", f(-_NOISE)))
        a = 0.5
        self.assertTrue(self._cmp(f(a), f(a + _NOISE)))
        self.assertTrue(self._cmp(f(a - _NOISE), f(a)))

    def test_absolute_tolerance_fail(self):
        self.assertFalse(self._cmp(f(_DIFF), "0")) 
        self.assertFalse(self._cmp("0", f(-_DIFF)))
        a = 0.5
        self.assertFalse(self._cmp(f(a), f(a + _DIFF)))
        self.assertFalse(self._cmp(f(a - _DIFF), f(a)))

    # --- Relative accuracy -----------------------------------------------------------

    def test_relative_tolerance_pass(self):
        a = 1
        b = a + _NOISE * a
        self.assertTrue(self._cmp(f(a), f(b)))
        a = 1000000
        b = a + _NOISE * a
        self.assertTrue(self._cmp(f(a), f(b)))

    def test_relative_tolerance_fail(self):
        a = 1
        b = a + _DIFF * a
        self.assertFalse(self._cmp(f(a), f(b)))
        a = 1000000
        b = a + _DIFF * a
        self.assertFalse(self._cmp(f(a), f(b)))

    # --- Multiple numbers ------------------------------------------------------------
    
    def test_multiple_numbers_tolerance(self):
        A = [0.25, 1.0, 2500000.0, -0.75, -3.0, 0.0, 12.5, 0.5]
        B = []
        for i, a in enumerate(A):
            B.append(a + (1 - 2 * (i % 2)) * _NOISE * max(1.0, abs(a)))
        
        self.assertTrue(self._cmp(" ".join(map(f, A)), " ".join(map(f, B))))
        C = B.copy()
        C[0] = A[0] + _DIFF * max(1.0, abs(A[0]))
        self.assertFalse(self._cmp(" ".join(map(f, A)), " ".join(map(f, C))))
        D = B.copy()
        D[4] = A[4] - _DIFF * max(1.0, abs(A[4]))
        self.assertFalse(self._cmp(" ".join(map(f, A)), " ".join(map(f, D))))
        E = B.copy()
        E[7] = A[7] - _DIFF * max(1.0, abs(A[7]))
        self.assertFalse(self._cmp(" ".join(map(f, A)), " ".join(map(f, E))))

if __name__ == "__main__":
    unittest.main()
