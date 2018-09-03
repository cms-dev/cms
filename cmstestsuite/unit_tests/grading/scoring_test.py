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

"""Tests for scoring functions.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa

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
        super(TaskScoreMixin, self).setUp()
        self.participation = self.add_participation()
        self.task = self.add_task(contest=self.participation.contest)
        dataset = self.add_dataset(task=self.task)
        self.task.active_dataset = dataset
        self.timestamp = make_datetime()

    def at(self, timestamp):
        return self.timestamp + timedelta(seconds=timestamp)

    def call(self):
        return task_score(self.participation, self.task)

    def add_result(self, timestamp, score, tokened=False, score_details=None):
        score_details = score_details if score_details is not None else []
        submission = self.add_submission(
            participation=self.participation,
            task=self.task,
            timestamp=timestamp)
        # task_score() only needs score and score_details, but all the fields
        # must be set to declare the submission result as scored.
        self.add_submission_result(submission, self.task.active_dataset,
                                   score=score,
                                   public_score=score,
                                   score_details=score_details,
                                   public_score_details=score_details,
                                   ranking_score_details=[])
        if tokened:
            self.add_token(timestamp=timestamp, submission=submission)


class TestTaskScoreMaxTokenedLast(TaskScoreMixin, unittest.TestCase):
    """Tests for task_score() using the max_tokened_last score mode."""

    def setUp(self):
        super(TestTaskScoreMaxTokenedLast, self).setUp()
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


class TestTaskScoreMaxSubtask(TaskScoreMixin, unittest.TestCase):
    """Tests for task_score() using the max_subtask score mode."""

    def setUp(self):
        super(TestTaskScoreMaxSubtask, self).setUp()
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
        self.add_result(self.at(1), 80 + 0.0002,
                        score_details=[
                            self.subtask(1, 80, 1.0),
                            self.subtask(2, 20, 0.00001),
                        ])
        self.add_result(self.at(2), 0.0004,
                        score_details=[
                            self.subtask(1, 80, 0.0),
                            self.subtask(2, 20, 0.00002),
                        ])
        self.session.flush()
        self.assertEqual(self.call(), (80 + 0.0004, False))


class TestTaskScoreMax(TaskScoreMixin, unittest.TestCase):
    """Tests for task_score() using the max score mode."""

    def setUp(self):
        super(TestTaskScoreMax, self).setUp()
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


if __name__ == "__main__":
    unittest.main()
