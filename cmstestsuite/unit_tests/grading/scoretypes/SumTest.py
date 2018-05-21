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

"""Tests for the Sum score type."""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import unittest

from cms.grading.scoretypes.Sum import Sum

from cmstestsuite.unit_tests.grading.scoretypes.scoretypetestutils \
    import ScoreTypeTestMixin


class TestSum(ScoreTypeTestMixin, unittest.TestCase):
    """Test the Sum score type."""

    def setUp(self):
        super(TestSum, self).setUp()
        self._public_testcases = {
            "0": False,
            "1": True,
            "2": False,
            "3": False,
        }

    def test_paramaters_correct(self):
        """Test that correct parameters do not throw."""
        Sum(100, self._public_testcases)
        Sum(1.5, self._public_testcases)

    def test_paramaters_invalid(self):
        with self.assertRaises(ValueError):
            Sum([], self._public_testcases)
        with self.assertRaises(ValueError):
            Sum("1", self._public_testcases)

    @unittest.skip
    def test_parameters_invalid_not_caught(self):
        with self.assertRaises(ValueError):
            Sum(1j, self._public_testcases)

    def test_max_scores(self):
        self.assertEqual(Sum(10.5, self._public_testcases).max_scores(),
                         (42, 10.5, []))

    def test_compute_score(self):
        st = Sum(10.5, self._public_testcases)
        sr = self.get_submission_result(self._public_testcases)

        # All correct.
        self.assertComputeScore(st.compute_score(sr), 42, 10.5, [])

        # Some non-public subtask is incorrect.
        sr.evaluations[-1].outcome = 0
        self.assertComputeScore(st.compute_score(sr), 42 - 10.5, 10.5, [])

        # Also the public subtask is incorrect.
        sr.evaluations[1].outcome = 0.0
        self.assertComputeScore(st.compute_score(sr), 21, 0.0, [])


if __name__ == "__main__":
    unittest.main()
