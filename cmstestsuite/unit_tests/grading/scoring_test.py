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

"""Tests for scoring functions.

"""

import unittest
from datetime import timedelta

# Needs to be first to allow for monkey patching the DB connection string.
from cmstestsuite.unit_tests.databasemixin import DatabaseMixin

from cms.grading.scoring import task_score
from cmscommon.constants import \
    SCORE_MODE_MAX, SCORE_MODE_MAX_SUBTASK, SCORE_MODE_MAX_TOKENED_LAST
from cmscommon.datetime import make_datetime


class TaskScoreMixin(DatabaseMixin):
    """A mixin to test the task_score() function with various score modes."""

    def setUp(self):
        super().setUp()
        self.participation = self.add_participation()
        self.task = self.add_task(contest=self.participation.contest,
                                  score_precision=2)
        dataset = self.add_dataset(task=self.task)
        self.task.active_dataset = dataset
        self.timestamp = make_datetime()

    def at(self, timestamp):
        return self.timestamp + timedelta(seconds=timestamp)

    def call(self, public=False, only_tokened=False, rounded=False):
        return task_score(self.participation, self.task,
                          public=public, only_tokened=only_tokened,
                          rounded=rounded)

    def add_result(self, timestamp, score, tokened=False, score_details=None,
                   public_score=None, public_score_details=None):
        public_score = public_score if public_score is not None else 0.0
        public_score_details = public_score_details \
            if public_score_details is not None else []
        score_details = score_details if score_details is not None else []
        submission = self.add_submission(
            participation=self.participation,
            task=self.task,
            timestamp=timestamp)
        # task_score() only needs score and score_details, but all the fields
        # must be set to declare the submission result as scored.
        self.add_submission_result(submission, self.task.active_dataset,
                                   score=score,
                                   public_score=public_score,
                                   score_details=score_details,
                                   public_score_details=public_score_details,
                                   ranking_score_details=[])
        if tokened:
            self.add_token(timestamp=timestamp, submission=submission)


class TestTaskScoreMaxTokenedLast(TaskScoreMixin, unittest.TestCase):
    """Tests for task_score() using the max_tokened_last score mode."""

    def setUp(self):
        super().setUp()
        self.task.score_mode = SCORE_MODE_MAX_TOKENED_LAST

    def test_no_submissions(self):
        self.assertEqual(self.call(), (0.0, False))

    def test_all_submissions_scored_tokened(self):
        self.add_result(self.at(1), 44.4, tokened=True)
        self.add_result(self.at(2), 66.6, tokened=True)
        self.session.flush()
        self.assertEqual(self.call(), (66.6, False))

    def test_all_submissions_scored_tokened_best_first(self):
        self.add_result(self.at(1), 66.6, tokened=True)
        self.add_result(self.at(2), 44.4, tokened=True)
        self.session.flush()
        self.assertEqual(self.call(), (66.6, False))

    def test_best_untokened_return_next_best(self):
        self.add_result(self.at(1), 44.4, tokened=True)
        self.add_result(self.at(2), 66.6, tokened=False)
        self.add_result(self.at(3), 11.1, tokened=False)
        self.session.flush()
        self.assertEqual(self.call(), (44.4, False))

    def test_best_untokened_return_last(self):
        self.add_result(self.at(1), 44.4, tokened=True)
        self.add_result(self.at(2), 66.6, tokened=False)
        self.add_result(self.at(3), 55.5, tokened=False)
        self.session.flush()
        self.assertEqual(self.call(), (55.5, False))

    def test_no_tokened(self):
        self.add_result(self.at(1), 66.6, tokened=False)
        self.add_result(self.at(2), 44.4, tokened=False)
        self.session.flush()
        self.assertEqual(self.call(), (44.4, False))

    def test_best_last_unordered(self):
        self.add_result(self.at(2), 66.6, tokened=False)
        self.add_result(self.at(1), 44.4, tokened=False)
        self.session.flush()
        self.assertEqual(self.call(), (66.6, False))

    def test_partial(self):
        self.add_result(self.at(1), None, tokened=True)
        self.add_result(self.at(2), 66.6, tokened=False)
        self.add_result(self.at(3), 55.5, tokened=False)
        self.session.flush()
        self.assertEqual(self.call(), (55.5, True))

    def test_partial_last_unscored(self):
        self.add_result(self.at(1), 66.6, tokened=True)
        self.add_result(self.at(2), None, tokened=False)
        self.session.flush()
        self.assertEqual(self.call(), (66.6, True))

    def test_not_partial_when_irrelevant_is_unscored(self):
        self.add_result(self.at(1), None, tokened=False)
        self.add_result(self.at(2), 66.6, tokened=False)
        self.session.flush()
        self.assertEqual(self.call(), (66.6, True))

    def test_all_unscored(self):
        self.add_result(self.at(1), None, tokened=True)
        self.add_result(self.at(2), None, tokened=False)
        self.add_result(self.at(3), None, tokened=False)
        self.session.flush()
        self.assertEqual(self.call(), (0.0, True))

    def test_public(self):
        self.add_result(self.at(1), 44.4, tokened=True, public_score=4.4)
        self.add_result(self.at(2), 66.6, tokened=False, public_score=66.6)
        self.add_result(self.at(3), 11.1, tokened=False, public_score=11.1)
        self.session.flush()
        self.assertEqual(self.call(public=True), (11.1, False))

    def test_only_tokened(self):
        self.add_result(self.at(1), 11.1, tokened=True)
        self.add_result(self.at(2), 66.6, tokened=False)
        self.add_result(self.at(3), 44.4, tokened=False)
        self.session.flush()
        self.assertEqual(self.call(only_tokened=True), (11.1, False))


class TestTaskScoreMaxSubtask(TaskScoreMixin, unittest.TestCase):
    """Tests for task_score() using the max_subtask score mode."""

    def setUp(self):
        super().setUp()
        self.task.score_mode = SCORE_MODE_MAX_SUBTASK

    @staticmethod
    def subtask(idx, max_score, score_fraction):
        """Return an item of score details for a subtask."""
        return {
            "idx": idx,
            "max_score": max_score,
            "score_fraction": score_fraction
        }

    def test_no_submissions(self):
        self.assertEqual(self.call(), (0.0, False))

    def test_task_not_group(self):
        self.add_result(self.at(1), 66.6, tokened=False)
        self.add_result(self.at(2), 44.4, tokened=False)
        self.session.flush()
        self.assertEqual(self.call(), (66.6, False))

    def test_all_submissions_scored(self):
        self.add_result(self.at(1), 30 * 0.2 + 40 * 0.5 + 30 * 0.1,
                        score_details=[
                            self.subtask(3, 30, 0.2),
                            self.subtask(2, 40, 0.5),
                            self.subtask(1, 30, 0.1),
                        ])
        self.add_result(self.at(2), 30 * 0.1 + 40 * 0.5 + 30 * 0.2,
                        score_details=[
                            self.subtask(2, 40, 0.5),
                            self.subtask(1, 30, 0.2),
                            self.subtask(3, 30, 0.1),
                        ])
        self.session.flush()
        self.assertEqual(self.call(), (30 * 0.2 + 40 * 0.5 + 30 * 0.2, False))

    def test_compilation_error_total_is_zero(self):
        # Compilation errors have details=[].
        self.add_result(self.at(1), 0.0, score_details=[])
        self.add_result(self.at(2), 30 * 0.0 + 40 * 0.0 + 30 * 0.0,
                        score_details=[
                            self.subtask(3, 30, 0.0),
                            self.subtask(2, 40, 0.0),
                            self.subtask(1, 30, 0.0),
                        ])
        self.session.flush()
        self.assertEqual(self.call(), (30 * 0.0 + 40 * 0.0 + 30 * 0.0, False))

    def test_compilation_error_total_is_positive(self):
        # Compilation errors have details=[].
        self.add_result(self.at(1), 0.0, score_details=[])
        self.add_result(self.at(2), 30 * 0.1 + 40 * 0.0 + 30 * 0.0,
                        score_details=[
                            self.subtask(3, 30, 0.1),
                            self.subtask(2, 40, 0.0),
                            self.subtask(1, 30, 0.0),
                        ])
        self.session.flush()
        self.assertEqual(self.call(), (30 * 0.1 + 40 * 0.0 + 30 * 0.0, False))

    def test_partial(self):
        self.add_result(self.at(1), 30 * 0.2 + 40 * 0.5 + 30 * 0.1,
                        score_details=[
                            self.subtask(3, 30, 0.2),
                            self.subtask(2, 40, 0.5),
                            self.subtask(1, 30, 0.1),
                        ])
        self.add_result(self.at(2), 30 * 0.1 + 40 * 0.5 + 30 * 0.2,
                        score_details=[
                            self.subtask(3, 30, 0.1),
                            self.subtask(2, 40, 0.5),
                            self.subtask(1, 30, 0.2),
                        ])
        self.add_result(self.at(3), None)
        self.session.flush()
        self.assertEqual(self.call(), (30 * 0.2 + 40 * 0.5 + 30 * 0.2, True))

    def test_rounding(self):
        # No rounding should happen at the subtask or task level.
        self.add_result(self.at(1), 80 + 0.000_2,
                        score_details=[
                            self.subtask(1, 80, 1.0),
                            self.subtask(2, 20, 0.000_01),
                        ])
        self.add_result(self.at(2), 0.000_4,
                        score_details=[
                            self.subtask(1, 80, 0.0),
                            self.subtask(2, 20, 0.000_02),
                        ])
        self.session.flush()
        self.assertEqual(self.call(), (80 + 0.000_4, False))

    def test_public(self):
        self.add_result(self.at(1),
                        30 * 1.0 + 40 * 1.0 + 30 * 1.0,
                        score_details=[
                            self.subtask(3, 30, 1.0),
                            self.subtask(2, 40, 1.0),
                            self.subtask(1, 30, 1.0),
                        ],
                        public_score=30 * 0.2 + 40 * 0.5 + 30 * 0.1,
                        public_score_details=[
                            self.subtask(3, 30, 0.2),
                            self.subtask(2, 40, 0.5),
                            self.subtask(1, 30, 0.1),
                        ])
        self.add_result(self.at(2),
                        30 * 1.0 + 40 * 1.0 + 30 * 1.0,
                        score_details=[
                            self.subtask(2, 40, 1.0),
                            self.subtask(1, 30, 1.0),
                            self.subtask(3, 30, 1.0),
                        ],
                        public_score=30 * 0.1 + 40 * 0.5 + 30 * 0.2,
                        public_score_details=[
                            self.subtask(2, 40, 0.5),
                            self.subtask(1, 30, 0.2),
                            self.subtask(3, 30, 0.1),
                        ])
        self.session.flush()
        self.assertEqual(self.call(public=True),
                         (30 * 0.2 + 40 * 0.5 + 30 * 0.2, False))

    def test_only_tokened(self):
        self.add_result(self.at(1), 30 * 0.2 + 40 * 0.5 + 30 * 0.1,
                        score_details=[
                            self.subtask(3, 30, 0.2),
                            self.subtask(2, 40, 0.5),
                            self.subtask(1, 30, 0.1),
                        ], tokened=True)
        self.add_result(self.at(2), 30 * 0.1 + 40 * 0.5 + 30 * 0.2,
                        score_details=[
                            self.subtask(2, 40, 0.5),
                            self.subtask(1, 30, 0.2),
                            self.subtask(3, 30, 0.1),
                        ], tokened=True)
        self.add_result(self.at(3), 30 * 1.0 + 40 * 1.0 + 30 * 1.0,
                        score_details=[
                            self.subtask(2, 40, 1.0),
                            self.subtask(1, 30, 1.0),
                            self.subtask(3, 30, 1.0),
                        ], tokened=False)
        self.session.flush()
        self.assertEqual(self.call(only_tokened=True),
                         (30 * 0.2 + 40 * 0.5 + 30 * 0.2, False))


class TestTaskScoreMax(TaskScoreMixin, unittest.TestCase):
    """Tests for task_score() using the max score mode."""

    def setUp(self):
        super().setUp()
        self.task.score_mode = SCORE_MODE_MAX

    def test_no_submissions(self):
        self.assertEqual(self.call(), (0.0, False))

    def test_all_submissions_scored(self):
        self.add_result(self.at(1), 44.4, tokened=False)
        self.add_result(self.at(2), 66.6, tokened=False)
        self.session.flush()
        self.assertEqual(self.call(), (66.6, False))

    def test_all_submissions_scored_best_first(self):
        self.add_result(self.at(1), 66.6, tokened=False)
        self.add_result(self.at(2), 44.4, tokened=False)
        self.session.flush()
        self.assertEqual(self.call(), (66.6, False))

    def test_best_untokened(self):
        self.add_result(self.at(1), 44.4, tokened=True)
        self.add_result(self.at(2), 66.6, tokened=False)
        self.add_result(self.at(3), 11.1, tokened=False)
        self.session.flush()
        self.assertEqual(self.call(), (66.6, False))

    def test_partial(self):
        self.add_result(self.at(1), None, tokened=False)
        self.add_result(self.at(2), 66.6, tokened=False)
        self.add_result(self.at(3), 55.5, tokened=False)
        self.session.flush()
        self.assertEqual(self.call(), (66.6, True))

    def test_all_unscored(self):
        self.add_result(self.at(1), None, tokened=False)
        self.add_result(self.at(2), None, tokened=False)
        self.session.flush()
        self.assertEqual(self.call(), (0.0, True))

    def test_public(self):
        self.add_result(self.at(1), 44.4, tokened=False, public_score=44.4)
        self.add_result(self.at(2), 66.6, tokened=False, public_score=6.6)
        self.session.flush()
        self.assertEqual(self.call(public=True), (44.4, False))

    def test_only_tokened(self):
        self.add_result(self.at(1), 44.4, tokened=True)
        self.add_result(self.at(2), 66.6, tokened=False)
        self.session.flush()
        self.assertEqual(self.call(only_tokened=True), (44.4, False))

    def test_unrounded(self):
        self.add_result(self.at(1), 44.44444, tokened=False)
        self.add_result(self.at(2), 44.44443, tokened=False)
        self.session.flush()
        self.assertEqual(self.call(), (44.44444, False))

    def test_rounded(self):
        self.add_result(self.at(1), 44.44444, tokened=False)
        self.add_result(self.at(2), 44.44443, tokened=False)
        self.session.flush()
        self.assertEqual(self.call(rounded=True), (44.44, False))


if __name__ == "__main__":
    unittest.main()
