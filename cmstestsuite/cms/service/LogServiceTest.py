#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
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

import unittest

from cms import SEV_CRITICAL, SEV_ERROR, SEV_WARNING, SEV_INFO, SEV_DEBUG
from cms.service.LogService import LogService


class TestLogService(unittest.TestCase):

    MESSAGE = "Random message"
    COORD = "Random coordinates"
    OPERATION = "Random operation"
    TIMESTAMP = 1234567890
    EXC_TEXT = "Random exception"

    def setUp(self):
        self.service = LogService(0)

    def test_last_messages(self):
        for severity in [SEV_CRITICAL,
                         SEV_ERROR,
                         SEV_WARNING]:
            self.helper_test_last_messages(severity)
        for severity in [SEV_INFO,
                         SEV_DEBUG]:
            self.helper_test_last_messages(severity, saved=False)

    def helper_test_last_messages(self, severity, saved=True):
        self.service.Log(TestLogService.MESSAGE + severity,
                         TestLogService.COORD + severity,
                         TestLogService.OPERATION + severity,
                         severity,
                         TestLogService.TIMESTAMP,
                         TestLogService.EXC_TEXT + severity)
        last_message = self.service.last_messages()[-1]
        if saved:
            self.assertEquals(last_message["message"],
                              TestLogService.MESSAGE + severity)
            self.assertEquals(last_message["coord"],
                              TestLogService.COORD + severity)
            self.assertEquals(last_message["operation"],
                              TestLogService.OPERATION + severity)
            self.assertEquals(last_message["severity"],
                              severity)
            self.assertEquals(last_message["timestamp"],
                              TestLogService.TIMESTAMP)
            self.assertEquals(last_message["exc_text"],
                              TestLogService.EXC_TEXT + severity)
            pass
        else:
            self.assertNotEquals(last_message["severity"], severity)


if __name__ == "__main__":
    unittest.main()
