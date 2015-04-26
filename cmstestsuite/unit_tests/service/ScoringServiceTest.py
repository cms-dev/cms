#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2013 Stefano Maggiolo <s.maggiolo@gmail.com>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

# We enable monkey patching to make many libraries gevent-friendly
# (for instance, urllib3, used by requests)
import gevent.monkey
gevent.monkey.patch_all()

import gevent
import random
import unittest
from mock import Mock, call

import cms.service.ScoringService
from cms.service.ScoringService import ScoringService


class TestScoringService(unittest.TestCase):

    def setUp(self):
        self.service = ScoringService(0)

    # Testing new_evaluation.

    def test_new_evaluation(self):
        """One submission is scored.

        """
        score_info = self.new_score_info()
        sr = TestScoringService.new_sr_to_score()
        score_type = Mock()
        score_type.compute_score.return_value = score_info
        TestScoringService.set_up_db([sr], score_type)

        self.service.new_evaluation(123, 456)

        gevent.sleep(0)  # Needed to trigger the score loop.
        # Asserts that compute_score was called.
        assert score_type.compute_score.mock_calls == [call(sr)]
        assert (sr.score,
                sr.score_details,
                sr.public_score,
                sr.public_score_details,
                sr.ranking_score_details) == score_info

    def test_new_evaluation_two(self):
        """More than one submissions in the queue.

        """
        score_type = Mock()
        score_type.compute_score.return_value = (1, "1", 2, "2", ["1", "2"])
        sr_a = TestScoringService.new_sr_to_score()
        sr_b = TestScoringService.new_sr_to_score()
        TestScoringService.set_up_db([sr_a, sr_b], score_type)

        self.service.new_evaluation(123, 456)
        self.service.new_evaluation(124, 456)

        gevent.sleep(0)  # Needed to trigger the score loop.
        # Asserts that compute_score was called.
        assert score_type.compute_score.mock_calls == [call(sr_a), call(sr_b)]

    def test_new_evaluation_already_scored(self):
        """One submission is not re-scored if already scored.

        """
        sr = TestScoringService.new_sr_scored()
        score_type = Mock()
        score_type.compute_score.return_value = (1, "1", 2, "2", ["1", "2"])
        TestScoringService.set_up_db([sr], score_type)

        self.service.new_evaluation(123, 456)

        gevent.sleep(0)  # Needed to trigger the score loop.
        # Asserts that compute_score was called.
        assert score_type.compute_score.mock_calls == []

    @staticmethod
    def new_sr_to_score():
        sr = Mock()
        sr.needs_scoring.return_value = True
        sr.scored.return_value = False
        return sr

    @staticmethod
    def new_sr_scored():
        sr = Mock()
        sr.needs_scoring.return_value = False
        sr.scored.return_value = True
        return sr

    @staticmethod
    def new_score_info():
        return (
            random.randint(1, 1000),
            "%d" % random.randint(1, 1000),
            random.randint(1, 1000),
            "%d" % random.randint(1, 1000),
            ["%d" % random.randint(1, 1000), "%d" % random.randint(1, 1000)]
        )

    @staticmethod
    def set_up_db(srs, score_type):
        submission = Mock()
        submission.get_result = Mock(side_effect=srs)
        cms.service.ScoringService.Submission.get_from_id = \
            Mock(return_value=submission)
        cms.service.ScoringService.Dataset.get_from_id = \
            Mock(return_value=Mock())
        cms.service.ScoringService.get_score_type = \
            Mock(return_value=score_type)


if __name__ == "__main__":
    unittest.main()
