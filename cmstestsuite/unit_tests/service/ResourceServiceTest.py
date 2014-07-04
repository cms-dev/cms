#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2014 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Tests for ResourceService.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import unittest

from cms import ServiceCoord
from cms.service.ResourceService import ResourceService


class TestResourceService(unittest.TestCase):

    def setUp(self):
        pass

    def test_is_service_proc(self):
        """Several tests for identifying the command line of a service.

        """
        service = ServiceCoord("Worker", 0)
        good_command_lines = [
            "/usr/bin/python2 cmsWorker 0",
            "/usr/bin/python2 cmsWorker",
            "python2 cmsWorker 0 -c 1",
            "python2 cmsWorker -c 1",
            "python2 cmsWorker -c 1 0",
            "/usr/bin/env python2 cmsWorker 0",
            "/usr/bin/env python2 cmsWorker",
            "/usr/bin/env python2 cmsWorker 0 -c 1",
            "/usr/bin/env python2 cmsWorker -c 1",
            "/usr/bin/env python2 cmsWorker -c 1 0",
            ]
        bad_command_lines = [
            "ps",
            "less cmsWorker 0",
            "less /usr/bin/python2 cmsWorker 0",
            "/usr/bin/python2 cmsWorker 1",
            "/usr/bin/python2 cmsAdminWebServer 0",
            ]
        for cmdline in good_command_lines:
            self.assertTrue(ResourceService._is_service_proc(
                service, cmdline.split(" ")), cmdline)
        for cmdline in bad_command_lines:
            self.assertFalse(ResourceService._is_service_proc(
                service, cmdline.split(" ")), cmdline)

        # Test we do not pick the wrong shard.
        service = ServiceCoord("Worker", 1)
        cmdline = "/usr/bin/python2 cmsWorker"
        self.assertFalse(ResourceService._is_service_proc(
            service, cmdline.split(" ")), cmdline)

        # Test that an empty command line does not cause problems.
        self.assertFalse(ResourceService._is_service_proc(
            service, []), "Empty command line.")

        # Simulate a service not running on the same machine.
        service = ServiceCoord("FakeWorker", 0)
        cmdline = "/usr/bin/python2 cmsFakeWorker 0"
        self.assertFalse(ResourceService._is_service_proc(
            service, cmdline.split(" ")), cmdline)

if __name__ == "__main__":
    unittest.main()
