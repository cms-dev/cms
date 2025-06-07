#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2013 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2016-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""Tests for the scoring service.

"""

# We enable monkey patching to make many libraries gevent-friendly
# (for instance, urllib3, used by requests)
import gevent.monkey

from cmscommon.datetime import make_datetime

gevent.monkey.patch_all()  # noqa

import unittest
from unittest.mock import patch, PropertyMock

import gevent

# Needs to be first to allow for monkey patching the DB connection string.
from cmstestsuite.unit_tests.databasemixin import DatabaseMixin

from cms.service.ScoringService import ScoringService
from cmstestsuite.unit_tests.testidgenerator import unique_long_id, \
    unique_unicode_id


class TestScoringService(DatabaseMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()

        self.score_info = (unique_long_id(), unique_long_id(),
                           unique_long_id(), unique_long_id(),
                           [unique_unicode_id(), unique_unicode_id()])

        patcher = patch("cms.db.Dataset.score_type_object",
                        new_callable=PropertyMock)
        self.score_type = patcher.start().return_value
        self.addCleanup(patcher.stop)
        self.call_args = list()
        self.score_type.compute_score.side_effect = self.compute_score

        self.contest = self.add_contest()

    def compute_score(self, sr):
        self.call_args.append((sr.submission_id, sr.dataset_id))
        return self.score_info

    def new_sr_to_score(self):
        task = self.add_task(contest=self.contest)
        dataset = self.add_dataset(task=task)
        submission = self.add_submission(task=task)
        result = self.add_submission_result(
            compilation_outcome="ok", evaluation_outcome="ok",
            submission=submission, dataset=dataset)
        return result

    def new_sr_scored(self):
        result = self.new_sr_to_score()
        result.score = 100
        result.score_details = dict()
        result.public_score = 50
        result.public_score_details = dict()
        result.ranking_score_details = ["100"]
        return result

    # Testing new_evaluation.

    def test_new_evaluation(self):
        """One submission is scored.

        """
        sr = self.new_sr_to_score()
        self.session.commit()

        service = ScoringService(0)
        service.new_evaluation(sr.submission_id, sr.dataset_id)

        gevent.sleep(0.1)  # Needed to trigger the score loop.

        # Asserts that compute_score was called.
        self.assertCountEqual(self.call_args,
                              [(sr.submission_id, sr.dataset_id)])
        self.session.expire(sr)
        self.assertEqual((sr.score, sr.score_details,
                          sr.public_score, sr.public_score_details,
                          sr.ranking_score_details),
                         self.score_info)
        self.assertIsNotNone(sr.scored_at)

    def test_new_evaluation_two(self):
        """More than one submissions in the queue.

        """
        sr_a = self.new_sr_to_score()
        sr_b = self.new_sr_to_score()
        self.session.commit()

        service = ScoringService(0)
        service.new_evaluation(sr_a.submission_id, sr_a.dataset_id)
        service.new_evaluation(sr_b.submission_id, sr_b.dataset_id)

        gevent.sleep(0.1)  # Needed to trigger the score loop.

        # Asserts that compute_score was called.
        self.assertCountEqual(self.call_args,
                              [(sr_a.submission_id, sr_a.dataset_id),
                               (sr_b.submission_id, sr_b.dataset_id)])

    def test_new_evaluation_already_scored(self):
        """One submission is not re-scored if already scored.

        """
        sr = self.new_sr_scored()
        current_time = make_datetime()
        sr.scored_at = current_time
        self.session.commit()

        service = ScoringService(0)
        service.new_evaluation(sr.submission_id, sr.dataset_id)

        gevent.sleep(0.1)  # Needed to trigger the score loop.

        # Asserts that compute_score was called.
        self.score_type.compute_score.assert_not_called()
        self.assertEqual(current_time, sr.scored_at)


if __name__ == "__main__":
    unittest.main()
