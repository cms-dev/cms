#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2014-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Tests for ResourceService."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa

import sys
import unittest

from mock import patch

from cms import ServiceCoord
from cms.service.ResourceService import ProcessMatcher


class TestProcessMatcher(unittest.TestCase):

    def setUp(self):
        self.pm = ProcessMatcher()
        self.w0_cmdlines = [
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
            sys.executable + " cmsWorker",
            sys.executable + " cmsWorker 0",
            sys.executable + " cmsWorker 0 -c 1",
            sys.executable + " cmsWorker -c 1",
            sys.executable + " cmsWorker -c 1 0",
        ]
        self.bad_cmdlines = [
            "ps",
            "less cmsWorker 0",
            "less /usr/bin/python2 cmsWorker 0",
            "/usr/bin/python2 cmsWorker 1",
            "/usr/bin/python2 cmsAdminWebServer 0",
        ]
        self.w0 = ServiceCoord("Worker", 0)

    @staticmethod
    def _get_all_processes_ret(cmdlines_and_maybe_procs):
        ret = []
        for c in cmdlines_and_maybe_procs:
            if isinstance(c, tuple):
                ret.append((c[0].split(), c[1]))
            else:
                ret.append((c.split(), "base"))
        return ret

    def test_find_works(self):
        for c in self.w0_cmdlines:
            with patch.object(ProcessMatcher, '_get_all_processes') as f:
                f.return_value = (TestProcessMatcher._get_all_processes_ret(
                    self.bad_cmdlines + [(c, "good")] + self.bad_cmdlines))
                self.assertEquals(self.pm.find(self.w0), "good")

    def test_find_fails(self):
        service = ServiceCoord("EvaluationService", 0)
        for c in self.w0_cmdlines:
            with patch.object(ProcessMatcher, '_get_all_processes') as f:
                f.return_value = (TestProcessMatcher._get_all_processes_ret(
                    self.bad_cmdlines + [(c, "good")] + self.bad_cmdlines))
                self.assertIsNone(self.pm.find(service))

    def test_get_all_processes_is_called_once(self):
        with patch.object(ProcessMatcher, '_get_all_processes') as f:
            f.return_value = (TestProcessMatcher._get_all_processes_ret(
                self.w0_cmdlines + self.bad_cmdlines))
            self.assertEqual(self.pm.find(self.w0), "base")
            self.assertEqual(self.pm.find(self.w0), "base")
            self.assertEqual(f.call_count, 1)


if __name__ == "__main__":
    unittest.main()
