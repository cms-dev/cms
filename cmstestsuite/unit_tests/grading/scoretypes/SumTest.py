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

"""Tests for the Sum score type."""

import unittest

from cms.grading.scoretypes.Sum import Sum
from cmstestsuite.unit_tests.grading.scoretypes.scoretypetestutils \
    import ScoreTypeTestMixin


class TestSum(ScoreTypeTestMixin, unittest.TestCase):
    """Test the Sum score type."""

    def setUp(self):
        super().setUp()
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

    def test_max_scores(self):
        testcase_score = 10.5
        self.assertEqual(Sum(testcase_score,
                             self._public_testcases).max_scores(),
                         (testcase_score * 4, testcase_score, []))

    def test_compute_score(self):
        testcase_score = 10.5
        st = Sum(testcase_score, self._public_testcases)
        sr = self.get_submission_result(self._public_testcases)

        # All correct.
        self.assertComputeScore(
            st.compute_score(sr),
            testcase_score * 4, testcase_score, [], [
                {"idx": '0'},
                {"idx": '1'},
                {"idx": '2'},
                {"idx": '3'}
            ])

        # Some non-public subtask is incorrect.
        self.set_outcome(sr, "3", 0.0)
        self.assertComputeScore(
            st.compute_score(sr),
            testcase_score * 3, testcase_score, [], [
                {"idx": '0'},
                {"idx": '1'},
                {"idx": '2'},
                {"idx": '3'}
            ])

        # Also the public subtask is incorrect.
        self.set_outcome(sr, "1", 0.0)
        self.assertComputeScore(
            st.compute_score(sr),
            testcase_score * 2, 0.0, [], [
                {"idx": '0'},
                {"idx": '1'},
                {"idx": '2'},
                {"idx": '3'}
            ])

        # Now the public subtask has some partial scores.
        self.set_outcome(sr, "1", 0.2)
        self.assertComputeScore(
            st.compute_score(sr),
            testcase_score * 2.2, testcase_score * 0.2, [], [
                {"idx": '0'},
                {"idx": '1'},
                {"idx": '2'},
                {"idx": '3'}
            ])


if __name__ == "__main__":
    unittest.main()
