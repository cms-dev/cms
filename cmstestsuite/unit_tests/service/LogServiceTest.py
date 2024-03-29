#!/usr/bin/env python3

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

"""Tests for the logger service.

"""

import logging
import unittest

from cms.service.LogService import LogService


class TestLogService(unittest.TestCase):

    MSG = "Random message"
    SERVICE_NAME = "RandomService"
    SERVICE_SHARD = 0
    OPERATION = "Random operation"
    CREATED = 1_234_567_890.123
    EXC_TEXT = "Random exception"

    def setUp(self):
        self.service = LogService(0)

    def test_last_messages(self):
        for severity in ["CRITICAL",
                         "ERROR",
                         "WARNING"]:
            self.helper_test_last_messages(severity)
        for severity in ["INFO",
                         "DEBUG"]:
            self.helper_test_last_messages(severity, saved=False)

    def helper_test_last_messages(self, severity, saved=True):
        self.service.Log(
            msg=TestLogService.MSG + severity,
            levelname=severity,
            levelno=getattr(logging, severity),
            created=TestLogService.CREATED,
            service_name=TestLogService.SERVICE_NAME + severity,
            service_shard=TestLogService.SERVICE_SHARD,
            operation=TestLogService.OPERATION + severity,
            exc_text=TestLogService.EXC_TEXT + severity)
        last_message = self.service.last_messages()[-1]
        if saved:
            self.assertEqual(last_message["message"],
                              TestLogService.MSG + severity)
            self.assertEqual(last_message["coord"],
                              TestLogService.SERVICE_NAME + severity +
                              "," + ("%d" % TestLogService.SERVICE_SHARD))
            self.assertEqual(last_message["operation"],
                              TestLogService.OPERATION + severity)
            self.assertEqual(last_message["severity"],
                              severity)
            self.assertEqual(last_message["timestamp"],
                              TestLogService.CREATED)
            self.assertEqual(last_message["exc_text"],
                              TestLogService.EXC_TEXT + severity)
        else:
            self.assertNotEqual(last_message["severity"], severity)


if __name__ == "__main__":
    unittest.main()
