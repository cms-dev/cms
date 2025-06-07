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

"""Utilities for testing score types."""

from unittest.mock import Mock


class ScoreTypeTestMixin:
    """A test mixin to make it easier to test score types."""

    def assertComputeScore(self, scores, total, public, rws_scores, subtasks):
        self.assertAlmostEqual(scores[0], total)
        self.assertEqual([{"idx": s["idx"]} for s in scores[1]],
                         subtasks)
        self.assertAlmostEqual(scores[2], public)
        self.assertEqual(scores[4], [str(score) for score in rws_scores])

    @staticmethod
    def get_submission_result(testcases):
        sr = Mock()
        sr.evaluated.return_value = True
        # Reversed to make sure the score type does not depend on the order.
        sr.evaluations = [
            ScoreTypeTestMixin.get_evaluation(codename, 1.0)
            for codename in reversed(sorted(testcases.keys()))]
        return sr

    @staticmethod
    def get_evaluation(codename, outcome):
        evaluation = Mock()
        evaluation.codename = codename
        evaluation.outcome = outcome
        evaluation.execution_memory = 100
        evaluation.execution_time = 0.5
        evaluation.text = "Nothing to report"
        return evaluation

    @staticmethod
    def set_outcome(sr, codename, outcome):
        for evaluation in sr.evaluations:
            if evaluation.codename == codename:
                evaluation.outcome = outcome
                return
        raise ValueError("set_outcome called for non-existing codename %s."
                         % codename)
