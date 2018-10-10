#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""Tests for tokening functions.

"""

import unittest
from datetime import timedelta
from unittest.mock import patch

# Needs to be first to allow for monkey patching the DB connection string.
from cmstestsuite.unit_tests.databasemixin import DatabaseMixin

from cms import TOKEN_MODE_INFINITE, TOKEN_MODE_DISABLED, TOKEN_MODE_FINITE
from cms.server.contest.tokening import accept_token, UnacceptableToken, \
    TokenAlreadyPlayed, tokens_available
from cmscommon.datetime import make_datetime


class TestTokensAvailable(DatabaseMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()

        self.timestamp = make_datetime()

        self.contest = self.add_contest(start=self.at(0))
        self.participation = self.add_participation(contest=self.contest)
        self.task = self.add_task(contest=self.contest)
        self.other_task = self.add_task(contest=self.contest)

    def at(self, timestamp):
        return self.timestamp + timedelta(seconds=timestamp)

    def call(self, timestamp):
        return tokens_available(
            self.participation, self.task, self.at(timestamp))

    def add_token_to_contest(self, timestamp):
        submission = self.add_submission(participation=self.participation,
                                         task=self.other_task)
        self.add_token(timestamp=self.at(timestamp), submission=submission)

    def add_token_to_task(self, timestamp):
        submission = self.add_submission(participation=self.participation,
                                         task=self.task)
        self.add_token(timestamp=self.at(timestamp), submission=submission)

    def set_contest_token_infinite(self):
        self.contest.token_mode = TOKEN_MODE_INFINITE

    def set_contest_token_disabled(self):
        self.contest.token_mode = TOKEN_MODE_DISABLED

    def set_contest_token_finite(self, initial, number, interval, max_=None):
        self.contest.token_mode = TOKEN_MODE_FINITE
        self.contest.token_gen_initial = initial
        self.contest.token_gen_number = number
        self.contest.token_gen_interval = timedelta(seconds=interval)
        self.contest.token_gen_max = max_

    def set_contest_token_constraints(self, max_number=None, min_interval=0):
        self.contest.token_max_number = max_number
        self.contest.token_min_interval = timedelta(seconds=min_interval)

    def set_task_token_infinite(self):
        self.task.token_mode = TOKEN_MODE_INFINITE

    def set_task_token_disabled(self):
        self.task.token_mode = TOKEN_MODE_DISABLED

    def set_task_token_finite(self, initial, number, interval, max_=None):
        self.task.token_mode = TOKEN_MODE_FINITE
        self.task.token_gen_initial = initial
        self.task.token_gen_number = number
        self.task.token_gen_interval = timedelta(seconds=interval)
        self.task.token_gen_max = max_

    def set_task_token_constraints(self, max_number=None, min_interval=0):
        self.task.token_max_number = max_number
        self.task.token_min_interval = timedelta(seconds=min_interval)

    def test_infinite(self):
        self.set_contest_token_infinite()
        self.set_task_token_infinite()
        self.assertEqual(self.call(10), (-1, None, None))

    def test_disabled(self):
        self.set_contest_token_infinite()
        self.set_task_token_disabled()
        self.assertEqual(self.call(10), (0, None, None))

        self.set_contest_token_disabled()
        self.set_task_token_infinite()
        self.assertEqual(self.call(10), (0, None, None))

    def test_finite_on_contest(self):
        self.set_contest_token_finite(initial=3, number=2, interval=4, max_=6)
        self.set_task_token_infinite()

        # None generated yet.
        self.assertEqual(self.call(3), (3, self.at(4), None))
        # One period of generation passed.
        self.assertEqual(self.call(6), (5, self.at(8), None))
        # Cap hit.
        self.assertEqual(self.call(10), (6, None, None))
        # Once some used, regeneration resumes.
        self.add_token_to_contest(9)
        self.assertEqual(self.call(10), (5, self.at(12), None))

    def test_finite_on_task(self):
        self.set_contest_token_infinite()
        self.set_task_token_finite(initial=3, number=2, interval=4, max_=6)

        # None generated yet.
        self.assertEqual(self.call(3), (3, self.at(4), None))
        # One period of generation passed.
        self.assertEqual(self.call(6), (5, self.at(8), None))
        # Cap hit.
        self.assertEqual(self.call(10), (6, None, None))
        # Once some used, regeneration resumes.
        self.add_token_to_task(9)
        self.assertEqual(self.call(10), (5, self.at(12), None))

        # Tokens on other tasks have no effect.
        self.add_token_to_contest(9)
        self.assertEqual(self.call(10), (5, self.at(12), None))

    def test_finite_on_both(self):
        self.set_contest_token_finite(initial=1, number=2, interval=5)
        self.set_task_token_finite(initial=2, number=1, interval=4, max_=5)

        # 7 ║                             ┏━━━━━━━━━┛
        # 6 ║                             ┃
        # 5 ║                   ┏━━━┯━━━━━┹───────────
        # 4 ║               ┌───╂───┘
        # 3 ║ ↓task ┌─┲━━━━━┷━━━┛
        # 2 ║───────┘ ┃
        # 1 ║━━━━━━━━━┛ ←contest
        # 0 ╠═╦═╦═╦═╦═╦═╦═╦═╦═╦═╦═╦═╦═╦═╦═╦═╦═╦═╦═╦═╦═
        #   0   2   4   6   8  10  12  14  16  18  20

        # Capped at the contest level.
        self.assertEqual(self.call(3), (1, self.at(5), None))
        # Capped at both, with the contest unlocking later.
        self.assertEqual(self.call(7), (3, self.at(10), None))
        # Capped at the task level.
        self.assertEqual(self.call(11), (4, self.at(12), None))
        # Capped at both, but no more will be generated.
        self.assertEqual(self.call(13), (5, None, None))
        # Capped at the task, but no more will be generated.
        self.assertEqual(self.call(16), (5, None, None))

        # Generation stops when the maximum is hit, but resumes as soon
        # as some tokens are used.
        self.assertEqual(self.call(101), (5, None, None))
        self.add_token_to_task(102)
        self.assertEqual(self.call(103), (4, self.at(104), None))
        self.assertEqual(self.call(105), (5, None, None))

    def test_constraints(self):
        self.set_contest_token_finite(initial=3, number=1, interval=2, max_=6)
        self.set_task_token_finite(initial=1, number=2, interval=2)

        # 7 ║                       ┌───────┘
        # 6 ║                       ┢━━━━━━━━━━━━━━━
        # 5 ║ ↓contest      ┏━━━━━━━┛
        # 4 ║       ┏━━━━━━━┩
        # 3 ║━━━━━━━╃───────┘
        # 2 ║       │
        # 1 ║───────┘ ←task
        # 0 ╠═══╦═══╦═══╦═══╦═══╦═══╦═══╦═══╦═══╦═══╦═
        #   0   1   2   3   4   5   6   7   8   9  10

        self.set_contest_token_constraints(3, 2)
        self.set_task_token_constraints(None, 4)

        self.add_token_to_contest(2)
        # We have 4 - 1 = 3 contest tokens and 3 task tokens but we can
        # play only 2 more on the contest, hence the number is capped.
        self.assertEqual(self.call(3), (2, None, self.at(4)))

        self.add_token_to_task(1)
        # We need to wait 4 seconds to play a token.
        self.assertEqual(self.call(3), (1, None, self.at(5)))

        self.add_token_to_contest(6)
        # We played all the tokens we could on the contest.
        self.assertEqual(self.call(7), (0, None, None))

    def test_constraints_have_no_effect_if_infinite(self):
        self.set_contest_token_infinite()
        self.set_task_token_infinite()

        self.add_token_to_task(5)

        # Just contest.
        self.set_contest_token_constraints(1, 10)
        self.assertEqual(self.call(10), (-1, None, None))

        # Just task.
        self.set_contest_token_constraints()
        self.set_task_token_constraints(1, 10)
        self.assertEqual(self.call(10), (-1, None, None))

        # Both.
        self.set_contest_token_constraints(1, 10)
        self.assertEqual(self.call(10), (-1, None, None))

    def test_usaco_like(self):
        self.contest.per_user_time = timedelta(seconds=100)
        self.participation.starting_time = self.at(1000)

        self.set_contest_token_finite(initial=2, number=1, interval=10, max_=10)
        self.set_task_token_finite(initial=10, number=0, interval=1)

        # Generation didn't start before the user's starting_time.
        self.assertEqual(self.call(1000), (2, self.at(1010), None))
        # Then it proceeds normally.
        self.assertEqual(self.call(1011), (3, self.at(1020), None))
        # Until the cap is hit.
        self.assertEqual(self.call(1081), (10, None, None))
        # Played tokens are taken into account at their correct time.
        self.add_token_to_task(1050)
        self.assertEqual(self.call(1051), (6, self.at(1060), None))
        self.assertEqual(self.call(1081), (9, None, None))


class TestAcceptToken(DatabaseMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()

        self.contest = self.add_contest()
        self.participation = self.add_participation(contest=self.contest)
        self.task = self.add_task(contest=self.contest)
        self.submission = self.add_submission(participation=self.participation,
                                              task=self.task)

        patcher = patch("cms.server.contest.tokening.tokens_available")
        self.tokens_available = patcher.start()
        self.addCleanup(patcher.stop)

        self.timestamp = make_datetime()

    def call(self):
        return accept_token(self.session, self.submission, self.timestamp)

    def test_success_infinite_tokens(self):
        self.tokens_available.return_value = (-1, None, None)
        token = self.call()
        self.assertIsNotNone(token)
        self.assertIs(token.submission, self.submission)
        self.assertIs(token.timestamp, self.timestamp)

    def test_success_finite_tokens(self):
        self.tokens_available.return_value = (1, None, None)
        token = self.call()
        self.assertIsNotNone(token)
        self.assertIs(token.submission, self.submission)
        self.assertIs(token.timestamp, self.timestamp)

    def test_failure_none_available(self):
        self.tokens_available.return_value = (0, None, None)
        with self.assertRaises(UnacceptableToken):
            self.call()

    def test_failure_cooldown_in_effect(self):
        self.tokens_available.return_value = \
            (1, None, self.timestamp + timedelta(seconds=1))
        with self.assertRaises(UnacceptableToken):
            self.call()

    def test_double_use(self):
        # Infinite tokens.
        self.tokens_available.return_value = (-1, None, None)
        self.add_token(submission=self.submission,
                       timestamp=self.timestamp - timedelta(seconds=1))
        with self.assertRaises(TokenAlreadyPlayed):
            self.call()


if __name__ == "__main__":
    unittest.main()
