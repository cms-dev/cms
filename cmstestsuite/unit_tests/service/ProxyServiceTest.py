#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015 Stefano Maggiolo <s.maggiolo@gmail.com>
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
gevent.monkey.patch_all()  # noqa

import unittest
from unittest.mock import patch, PropertyMock

import gevent

# Needs to be first to allow for monkey patching the DB connection string.
from cmstestsuite.unit_tests.databasemixin import DatabaseMixin

from cms.service.ProxyService import ProxyService
from cmscommon.constants import SCORE_MODE_MAX


class TestProxyService(DatabaseMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()

        patcher = patch("cms.db.Dataset.score_type_object",
                        new_callable=PropertyMock)
        self.score_type = patcher.start().return_value
        self.addCleanup(patcher.stop)
        self.score_type.max_score = 100
        self.score_type.ranking_headers = ["100"]

        patcher = patch("requests.put")
        self.requests_put = patcher.start()
        self.addCleanup(patcher.stop)
        self.requests_put.return_value.status_code = 200

        self.contest = self.add_contest()
        self.contest.score_precision = 2

        self.task = self.add_task(contest=self.contest)
        self.task.score_precision = 2
        self.task.score_mode = SCORE_MODE_MAX
        self.dataset = self.add_dataset(task=self.task)
        self.task.active_dataset = self.dataset

        self.team = self.add_team()
        self.user = self.add_user()
        self.participation = self.add_participation(user=self.user,
                                                    contest=self.contest,
                                                    team=self.team)

        self.new_sr_unscored()
        self.new_sr_scored()
        result = self.new_sr_scored()
        self.add_token(submission=result.submission)

        self.session.commit()

    def new_sr_unscored(self):
        submission = self.add_submission(task=self.task,
                                         participation=self.participation)
        result = self.add_submission_result(submission=submission,
                                            dataset=self.dataset)
        result.compilation_outcome = "ok"
        result.evaluation_outcome = "ok"
        return result

    def new_sr_scored(self):
        result = self.new_sr_unscored()
        result.score = 100
        result.score_details = dict()
        result.public_score = 50
        result.public_score_details = dict()
        result.ranking_score_details = ["100"]
        return result

    def test_startup(self):
        """Test that data is sent in the right order at startup."""
        ProxyService(0, self.contest.id)

        gevent.sleep(0.1)

        urls = [args[0] for args, _ in self.requests_put.call_args_list]

        self.assertTrue(urls[0].endswith("contests/"))
        self.assertTrue(any(urls[i].endswith("users/") for i in [1, 2, 3]))
        self.assertTrue(any(urls[i].endswith("teams/") for i in [1, 2, 3]))
        self.assertTrue(any(urls[i].endswith("tasks/") for i in [1, 2, 3]))
        self.assertTrue(urls[4].endswith("submissions/"))
        self.assertTrue(urls[5].endswith("subchanges/"))


if __name__ == "__main__":
    unittest.main()
