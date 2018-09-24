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
from cmscommon.constants import SCORE_MODE_MAX, SCORE_MODE_MAX_TOKENED_LAST
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

    def add_result(self, timestamp, score, tokened=False):
        submission = self.add_submission(
            participation=self.participation,
            task=self.task,
            timestamp=timestamp)
        # task_score() only needs score, but all the fields must be set to
        # declare the submission result as scored.
        self.add_submission_result(submission, self.task.active_dataset,
                                   score=score,
                                   public_score=score,
                                   score_details={},
                                   public_score_details={},
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
