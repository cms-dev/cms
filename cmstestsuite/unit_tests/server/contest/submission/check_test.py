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

import unittest
from datetime import timedelta
from unittest.mock import call, patch

# Needs to be first to allow for monkey patching the DB connection string.
from cmstestsuite.unit_tests.databasemixin import DatabaseMixin

from cms.db import UserTest, Submission
from cms.server.contest.submission import get_submission_count, \
    check_max_number, get_latest_submission, check_min_interval, is_last_minutes
from cmscommon.datetime import make_datetime


class TestGetSubmissionCount(DatabaseMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.contest = self.add_contest()
        self.task1 = self.add_task(contest=self.contest)
        self.task2 = self.add_task(contest=self.contest)
        self.participation = self.add_participation(contest=self.contest)

    def call(self, participation=None, **kwargs):
        if participation is None:
            participation = self.participation
        return get_submission_count(self.session, participation, **kwargs)

    def test_bad_arguments(self):
        # Needs at least one of contest or task.
        with self.assertRaises(ValueError):
            self.call()
        # If both, the task's contest cannot be None.
        other_task = self.add_task()
        with self.assertRaises(ValueError):
            self.call(contest=self.contest, task=other_task)
        # And cannot be another contest.
        other_contest = self.add_contest()
        other_task.contest = other_contest
        with self.assertRaises(ValueError):
            self.call(contest=self.contest, task=other_task)

    def test_count_task(self):
        # No submissions.
        self.assertEqual(self.call(task=self.task1), 0)

        # One submission.
        s = self.add_submission(task=self.task1,
                                participation=self.participation)
        self.assertEqual(self.call(task=self.task1), 1)

        # More than one submission.
        self.add_submission(task=self.task1, participation=self.participation)
        self.assertEqual(self.call(task=self.task1), 2)

        # Doesn't mix submissions for different tasks.
        self.assertEqual(self.call(task=self.task2), 0)

        # Doesn't mix submissions for different users.
        other_participation = self.add_participation(contest=self.contest)
        self.assertEqual(self.call(participation=other_participation,
                                   task=self.task1), 0)

        # Doesn't mix submissions with user tests.
        self.assertEqual(self.call(task=self.task1, cls=UserTest), 0)

        # Isn't influenced by submission results.
        d1 = self.add_dataset(task=self.task1)
        d2 = self.add_dataset(task=self.task1)
        self.add_submission_result(submission=s, dataset=d1)
        self.add_submission_result(submission=s, dataset=d2)
        self.assertEqual(self.call(task=self.task1), 2)

    def test_count_contest(self):
        # No submissions.
        self.assertEqual(self.call(contest=self.contest), 0)

        # One submission.
        self.add_submission(task=self.task1, participation=self.participation)
        self.assertEqual(self.call(contest=self.contest), 1)

        # Another one, on a different task.
        self.add_submission(task=self.task2, participation=self.participation)
        self.assertEqual(self.call(contest=self.contest), 2)

        # Back to the first task.
        self.add_submission(task=self.task1, participation=self.participation)
        self.assertEqual(self.call(contest=self.contest), 3)

        # Doesn't mix submissions for different contests.
        other_contest = self.add_contest()
        self.assertEqual(self.call(contest=other_contest), 0)

        # Doesn't mix submissions for different users.
        other_participation = self.add_participation(contest=self.contest)
        self.assertEqual(self.call(participation=other_participation,
                                   contest=self.contest), 0)

        # Doesn't mix submissions with user tests.
        self.assertEqual(self.call(contest=self.contest, cls=UserTest), 0)

    def test_user_tests(self):
        # No user tests.
        self.assertEqual(self.call(contest=self.contest, cls=UserTest), 0)
        self.assertEqual(self.call(task=self.task1, cls=UserTest), 0)
        self.assertEqual(self.call(task=self.task2, cls=UserTest), 0)

        # One user test.
        self.add_user_test(task=self.task1, participation=self.participation)
        self.assertEqual(self.call(contest=self.contest, cls=UserTest), 1)
        self.assertEqual(self.call(task=self.task1, cls=UserTest), 1)
        self.assertEqual(self.call(task=self.task2, cls=UserTest), 0)

        # Another user test, on a different task.
        self.add_user_test(task=self.task2, participation=self.participation)
        self.assertEqual(self.call(contest=self.contest, cls=UserTest), 2)
        self.assertEqual(self.call(task=self.task1, cls=UserTest), 1)
        self.assertEqual(self.call(task=self.task2, cls=UserTest), 1)

        # Doesn't mix user tests with submissions.
        self.assertEqual(self.call(contest=self.contest), 0)
        self.assertEqual(self.call(task=self.task1), 0)
        self.assertEqual(self.call(task=self.task2), 0)


class TestCheckMaxNumber(DatabaseMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()

        patcher = patch(
            "cms.server.contest.submission.check.get_submission_count")
        self.get_submission_count = patcher.start()
        self.addCleanup(patcher.stop)
        self.calls = list()

        self.contest = self.add_contest()
        self.task = self.add_task(contest=self.contest)
        self.participation = self.add_participation(unrestricted=False,
                                                    contest=self.contest)

    def call(self, max_number, **kwargs):
        res = check_max_number(
            self.session, max_number, self.participation, **kwargs)
        kwargs.setdefault("contest", None)
        kwargs.setdefault("task", None)
        kwargs.setdefault("cls", Submission)
        self.calls.append(call(self.session, self.participation, **kwargs))
        return res

    def test_no_limit(self):
        self.get_submission_count.return_value = 5
        # Test different arguments to ensure they don't cause issues.
        self.assertTrue(self.call(None))
        self.assertTrue(self.call(None, contest=self.contest))
        self.assertTrue(self.call(None, task=self.task))
        self.assertTrue(self.call(None, contest=self.contest, task=self.task))
        # Having calls signals an inefficiency.
        self.get_submission_count.assert_not_called()

    def test_limit(self):
        self.get_submission_count.return_value = 5
        # Test different arguments to ensure they are passed to the call.
        self.assertFalse(self.call(0, contest=self.contest))
        self.assertFalse(self.call(3, task=self.task))
        self.assertFalse(self.call(5, contest=self.contest, task=self.task))
        self.assertTrue(self.call(6, contest=self.contest, cls=UserTest))
        self.assertTrue(self.call(9, task=self.task, cls=UserTest))
        # Arguments should have been passed unchanged.
        self.get_submission_count.assert_has_calls(self.calls)

    def test_limit_unrestricted(self):
        # Unrestricted users have no limit enforced.
        self.participation.unrestricted = True
        self.get_submission_count.return_value = 5
        # Test different arguments to ensure they don't cause issues.
        self.assertTrue(self.call(0, contest=self.contest))
        self.assertTrue(self.call(3, task=self.task))
        self.assertTrue(self.call(5, contest=self.contest, task=self.task))
        self.assertTrue(self.call(6, contest=self.contest, cls=UserTest))
        self.assertTrue(self.call(9, task=self.task, cls=UserTest))
        # Having calls signals an inefficiency.
        self.get_submission_count.assert_not_called()


class TestGetLatestSubmission(DatabaseMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.contest = self.add_contest()
        self.task1 = self.add_task(contest=self.contest)
        self.task2 = self.add_task(contest=self.contest)
        self.participation = self.add_participation(contest=self.contest)
        self.timestamp = make_datetime()

    def at(self, seconds):
        return self.timestamp + timedelta(seconds=seconds)

    def call(self, participation=None, **kwargs):
        if participation is None:
            participation = self.participation
        return get_latest_submission(self.session, participation, **kwargs)

    def test_bad_arguments(self):
        # Needs at least one of contest or task.
        with self.assertRaises(ValueError):
            self.call()
        # If both, the task's contest cannot be None.
        other_task = self.add_task()
        with self.assertRaises(ValueError):
            self.call(contest=self.contest, task=other_task)
        # And cannot be another contest.
        other_contest = self.add_contest()
        other_task.contest = other_contest
        with self.assertRaises(ValueError):
            self.call(contest=self.contest, task=other_task)

    def test_retrieve_task(self):
        # No submissions.
        self.assertIsNone(self.call(task=self.task1))

        # One submission.
        s1 = self.add_submission(timestamp=self.at(0), task=self.task1,
                                 participation=self.participation)
        self.assertIs(self.call(task=self.task1), s1)

        # More than one submission.
        s2 = self.add_submission(timestamp=self.at(2), task=self.task1,
                                 participation=self.participation)
        self.assertIs(self.call(task=self.task1), s2)

        # They are sorted by timestamp, not by insertion order (i.e., by id).
        self.add_submission(timestamp=self.at(1), task=self.task1,
                            participation=self.participation)
        self.assertIs(self.call(task=self.task1), s2)

        # Doesn't mix submissions for different tasks.
        self.assertIsNone(self.call(task=self.task2))

        # Doesn't mix submissions for different users.
        other_participation = self.add_participation(contest=self.contest)
        self.assertIsNone(self.call(participation=other_participation,
                                    task=self.task1))

        # Doesn't mix submissions with user tests.
        self.assertIsNone(self.call(task=self.task1, cls=UserTest))

    def test_retrieve_contest(self):
        # No submissions.
        self.assertIsNone(self.call(contest=self.contest))

        # One submission.
        s1 = self.add_submission(timestamp=self.at(2), task=self.task1,
                                 participation=self.participation)
        self.assertIs(self.call(contest=self.contest), s1)

        # Another one, on a different task.
        s2 = self.add_submission(timestamp=self.at(3), task=self.task2,
                                 participation=self.participation)
        self.assertIs(self.call(contest=self.contest), s2)

        # Back to the first task, but at an earlier time.
        self.add_submission(timestamp=self.at(1), task=self.task1,
                            participation=self.participation)
        self.assertIs(self.call(contest=self.contest), s2)

        # Doesn't mix submissions for different contests.
        other_contest = self.add_contest()
        self.assertIsNone(self.call(contest=other_contest))

        # Doesn't mix submissions for different users.
        other_participation = self.add_participation(contest=self.contest)
        self.assertIsNone(self.call(participation=other_participation,
                                    contest=self.contest))

        # Doesn't mix submissions with user tests.
        self.assertIsNone(self.call(contest=self.contest, cls=UserTest))

    def test_user_tests(self):
        # No user tests.
        self.assertIsNone(self.call(contest=self.contest, cls=UserTest))
        self.assertIsNone(self.call(task=self.task1, cls=UserTest))
        self.assertIsNone(self.call(task=self.task2, cls=UserTest))

        # One user test.
        s1 = self.add_user_test(timestamp=self.at(1), task=self.task1,
                                participation=self.participation)
        self.assertIs(self.call(contest=self.contest, cls=UserTest), s1)
        self.assertIs(self.call(task=self.task1, cls=UserTest), s1)
        self.assertIsNone(self.call(task=self.task2, cls=UserTest))

        # Another user test, on a different task.
        s2 = self.add_user_test(timestamp=self.at(2), task=self.task2,
                                participation=self.participation)
        self.assertIs(self.call(contest=self.contest, cls=UserTest), s2)
        self.assertIs(self.call(task=self.task1, cls=UserTest), s1)
        self.assertIs(self.call(task=self.task2, cls=UserTest), s2)

        # Doesn't mix user tests with submissions.
        self.assertIsNone(self.call(contest=self.contest))
        self.assertIsNone(self.call(task=self.task1))
        self.assertIsNone(self.call(task=self.task2))


class TestCheckMinInterval(DatabaseMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()

        patcher = \
            patch("cms.server.contest.submission.check.get_latest_submission")
        self.get_latest_submission = patcher.start()
        self.addCleanup(patcher.stop)
        self.calls = list()

        self.contest = self.add_contest()
        self.task = self.add_task(contest=self.contest)
        self.participation = self.add_participation(unrestricted=False,
                                                    contest=self.contest)

        self.timestamp = make_datetime()

    def at(self, seconds):
        return self.timestamp + timedelta(seconds=seconds)

    def call(self, min_interval, timestamp, **kwargs):
        res = check_min_interval(
            self.session,
            None if min_interval is None else timedelta(seconds=min_interval),
            self.at(timestamp), self.participation, **kwargs)
        kwargs.setdefault("contest", None)
        kwargs.setdefault("task", None)
        kwargs.setdefault("cls", Submission)
        self.calls.append(call(self.session, self.participation, **kwargs))
        return res

    def test_no_limit(self):
        s = self.add_submission(timestamp=self.at(5), task=self.task,
                                participation=self.participation)
        self.get_latest_submission.return_value = s
        # Test different arguments to ensure they don't cause issues.
        self.assertTrue(self.call(None, 0))
        self.assertTrue(self.call(None, 1, contest=self.contest))
        self.assertTrue(self.call(None, 2, task=self.task))
        self.assertTrue(self.call(
            None, 3, contest=self.contest, task=self.task))
        # Having calls signals an inefficiency.
        self.get_latest_submission.assert_not_called()

    def test_limit(self):
        s = self.add_submission(timestamp=self.at(5), task=self.task,
                                participation=self.participation)
        self.get_latest_submission.return_value = s
        # Test different arguments to ensure they are passed to the call.
        self.assertFalse(self.call(1, 4, contest=self.contest))
        self.assertFalse(self.call(3, 6, task=self.task, cls=UserTest))
        self.assertTrue(self.call(4, 11, contest=self.contest, task=self.task))
        # Arguments should have been passed unchanged.
        self.get_latest_submission.assert_has_calls(self.calls)

    def test_limit_no_submissions(self):
        self.get_latest_submission.return_value = None
        # Test different arguments to ensure they are passed to the call.
        self.assertTrue(self.call(1, 4, contest=self.contest, cls=UserTest))
        self.assertTrue(self.call(3, 6, task=self.task))
        self.assertTrue(self.call(4, 11, contest=self.contest, task=self.task))
        # Arguments should have been passed unchanged.
        self.get_latest_submission.assert_has_calls(self.calls)

    def test_limit_unrestricted(self):
        # Unrestricted users have no limit enforced.
        self.participation.unrestricted = True
        s = self.add_submission(timestamp=self.at(5), task=self.task,
                                participation=self.participation)
        self.get_latest_submission.return_value = s
        # Test different arguments to ensure they don't cause issues.
        self.assertTrue(self.call(1, 4, contest=self.contest))
        self.assertTrue(self.call(3, 6, task=self.task))
        self.assertTrue(self.call(
            4, 11, contest=self.contest, task=self.task, cls=UserTest))
        # Having calls signals an inefficiency.
        self.get_latest_submission.assert_not_called()


class TestIsLastMinutes(DatabaseMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.contest = self.add_contest()
        self.task = self.add_task(contest=self.contest)
        self.participation = self.add_participation(unrestricted=False,
                                                    contest=self.contest)

        self.timestamp = make_datetime()

    def test_unconfigured_min_submission_interval_grace_period(self):
        self.setup_contest_with_no_user_time()

        self.assertFalse(
            is_last_minutes(self.timestamp, self.participation))

    def test_no_per_user_time_and_last_minutes(self):
        self.setup_contest_with_no_user_time()
        self.contest.min_submission_interval_grace_period = timedelta(minutes=15)

        self.assertTrue(
            is_last_minutes(self.timestamp - timedelta(minutes=15), self.participation))

    def test_no_per_user_time_and_not_last_minutes(self):
        self.setup_contest_with_no_user_time()
        self.contest.min_submission_interval_grace_period = timedelta(minutes=10)

        self.assertFalse(
            is_last_minutes(self.timestamp - timedelta(minutes=15), self.participation))

    def test_per_user_time_and_last_minutes(self):
        self.participation.contest.per_user_time = timedelta(hours=5)
        self.participation.contest.start = self.timestamp - timedelta(hours=10)
        self.participation.contest.stop = self.timestamp
        self.participation.starting_time = self.timestamp - timedelta(hours=5)
        self.contest.min_submission_interval_grace_period = timedelta(minutes=15)

        self.assertTrue(
            is_last_minutes(self.timestamp - timedelta(minutes=15), self.participation))

    def test_per_user_time_and_not_last_minutes(self):
        self.participation.contest.per_user_time = timedelta(hours=5)
        self.participation.contest.start = self.timestamp - timedelta(hours=10)
        self.participation.contest.stop = self.timestamp
        self.participation.starting_time = self.timestamp - timedelta(hours=5)
        self.contest.min_submission_interval_grace_period = timedelta(minutes=10)

        self.assertFalse(
            is_last_minutes(self.timestamp - timedelta(minutes=15), self.participation))

    def test_consider_extra_time(self):
        self.setup_contest_with_no_user_time()

        self.participation.extra_time = timedelta(seconds=1)
        self.contest.min_submission_interval_grace_period = timedelta(minutes=15)

        self.assertFalse(
            is_last_minutes(self.timestamp - timedelta(minutes=15), self.participation))

    def test_consider_delay(self):
        self.setup_contest_with_no_user_time()

        self.participation.delay_time = timedelta(seconds=1)
        self.contest.min_submission_interval_grace_period = timedelta(minutes=15)

        self.assertFalse(
            is_last_minutes(self.timestamp - timedelta(minutes=15), self.participation))

    def test_unrestricted_participation(self):
        self.setup_contest_with_no_user_time()
        self.participation.unrestricted = True

        self.assertFalse(is_last_minutes(self.timestamp, self.participation))

    def setup_contest_with_no_user_time(self):
        self.participation.contest.per_user_time = None
        self.participation.contest.start = self.timestamp - timedelta(hours=5)
        self.participation.contest.stop = self.timestamp


if __name__ == "__main__":
    unittest.main()
