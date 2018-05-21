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

"""Tests for the GroupThreshold score type."""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import unittest

from cms.grading.scoretypes.GroupThreshold import GroupThreshold

from cmstestsuite.unit_tests.grading.scoretypes.scoretypetestutils \
    import ScoreTypeTestMixin


class TestGroupThreshold(ScoreTypeTestMixin, unittest.TestCase):
    """Test the GroupThreshold score type."""

    def setUp(self):
        super(TestGroupThreshold, self).setUp()
        self._public_testcases = {
            "1_0": True,
            "1_1": True,
            "2_0": True,
            "2_1": False,
            "3_0": False,
            "3_1": False,
        }

    def test_paramaters_correct(self):
        """Test that correct parameters do not throw."""
        for parameters in [
                [],
                [[40, 10, 500], [60.0, 15, 1000]],
                [[40, "1_*", 500.5], [60.0, "2_*", 1000]]]:
            GroupThreshold(parameters, self._public_testcases)

    def test_paramaters_invalid_wrong_item_len(self):
        with self.assertRaises(ValueError):
            GroupThreshold([[]], self._public_testcases)
        with self.assertRaises(ValueError):
            GroupThreshold([[1]], self._public_testcases)

    @unittest.skip("Not yet detected.")
    def test_paramaters_invalid_wrong_item_len_not_caught(self):
        with self.assertRaises(ValueError):
            GroupThreshold([[1, 2]], self._public_testcases)

    def test_parameter_invalid_wrong_max_score_type(self):
        with self.assertRaises(ValueError):
            GroupThreshold([["a", 10, 1000]], self._public_testcases)

    def test_parameter_invalid_wrong_testcases_type(self):
        with self.assertRaises(ValueError):
            GroupThreshold([[100, 1j, 1000]], self._public_testcases)

    def test_parameter_invalid_inconsistent_testcases_type(self):
        with self.assertRaises(ValueError):
            GroupThreshold([[40, 10, 500], [40, "1_*", 1000]],
                           self._public_testcases)

    def test_parameter_invalid_testcases_regex_no_match_type(self):
        with self.assertRaises(ValueError):
            GroupThreshold([[100, "9_*", 1000]], self._public_testcases)

    @unittest.skip("Not yet detected.")
    def test_parameter_invalid_wrong_threshold_type_not_caught(self):
        with self.assertRaises(ValueError):
            GroupThreshold([[100, 1, 1000j]], self._public_testcases)

    def test_max_scores_regexp(self):
        """Test max score is correct when groups are regexp-defined."""
        parameters = [[10.5, "1_*", 10], [30.5, "2_*", 20], [59, "3_*", 30]]
        header = ["Subtask 1 (10.5)", "Subtask 2 (30.5)", "Subtask 3 (59)"]

        # Only group 1_* is public.
        self.assertEqual(
            GroupThreshold(parameters, self._public_testcases).max_scores(),
            (100, 10.5, header))

    def test_max_scores_number(self):
        """Test max score is correct when groups are number-defined."""
        parameters = [[10.5, 2, 10], [30.5, 2, 20], [59, 2, 30]]
        header = ["Subtask 1 (10.5)", "Subtask 2 (30.5)", "Subtask 3 (59)"]

        # Only group 1_* is public.
        self.assertEqual(
            GroupThreshold(parameters, self._public_testcases).max_scores(),
            (100, 10.5, header))

    def test_compute_score(self):
        parameters = [[10.5, "1_*", 10], [30.5, "2_*", 20], [59, "3_*", 30]]
        st = GroupThreshold(parameters, self._public_testcases)
        sr = self.get_submission_result(self._public_testcases)

        # All correct (below threshold).
        for i in range(len(sr.evaluations)):
            sr.evaluations[i].outcome = 5.5
        self.assertComputeScore(st.compute_score(sr),
                                100, 10.5, [10.5, 30.5, 59])

        # Some non-public subtask is incorrect.
        sr.evaluations[-1].outcome = 100.5
        self.assertComputeScore(st.compute_score(sr),
                                10.5 + 30.5, 10.5, [10.5, 30.5, 0])

        # Also the public subtask is incorrect.
        sr.evaluations[0].outcome = 12.5
        sr.evaluations[1].outcome = 12.5
        self.assertComputeScore(st.compute_score(sr),
                                30.5, 0.0, [0, 30.5, 0])


if __name__ == "__main__":
    unittest.main()
