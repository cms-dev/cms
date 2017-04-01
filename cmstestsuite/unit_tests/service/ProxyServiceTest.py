#!/usr/bin/env python2
# -*- coding: utf-8 -*-

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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

# We enable monkey patching to make many libraries gevent-friendly
# (for instance, urllib3, used by requests)
import gevent.monkey
gevent.monkey.patch_all()

import gevent
import unittest
from mock import Mock

import cms.service.ProxyService
from cms.service.ProxyService import ProxyService
from cmstestsuite.unit_tests.testobjectgenerator import \
    get_contest, get_participation, get_submission, get_task


class TestProxyService(unittest.TestCase):

    def setUp(self):
        pass

    def test_startup(self):
        """Test that data is sent in the right order at startup."""
        put_mock = Mock()
        cms.service.ProxyService.requests.put = put_mock

        task = get_task()
        participation = get_participation()
        TestProxyService.set_up_db([task], [participation], [
            get_submission(task, participation),
            get_submission(task, participation),
            get_submission(task, participation, scored=False),
        ])

        self.service = ProxyService(0, 0)
        gevent.sleep(0)
        gevent.sleep(0)

        urls_data = [(call[0][0], call[0][1])
                     for call in put_mock.call_args_list]

        assert urls_data[0][0].endswith("contests/")
        assert any(urls_data[i][0].endswith("users/") for i in [1, 2, 3])
        assert any(urls_data[i][0].endswith("teams/") for i in [1, 2, 3])
        assert any(urls_data[i][0].endswith("tasks/") for i in [1, 2, 3])
        assert urls_data[4][0].endswith("submissions/")
        assert urls_data[5][0].endswith("subchanges/")

    @staticmethod
    def set_up_db(tasks, participations, submissions):
        contest = get_contest()
        cms.service.ProxyService.Contest.get_from_id = \
            Mock(return_value=contest)
        contest.tasks = tasks
        contest.participations = participations
        contest.get_submissions = Mock(return_value=submissions)


if __name__ == "__main__":
    unittest.main()
