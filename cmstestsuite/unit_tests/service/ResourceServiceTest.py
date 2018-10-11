#!/usr/bin/env python3

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

import os
import sys
import unittest
from unittest.mock import patch

from cms import ServiceCoord
from cms.service import ResourceService
from cms.service.ResourceService import ProcessMatcher


class TestProcessMatcher(unittest.TestCase):

    def setUp(self):
        self.pm = ProcessMatcher()

        path = os.path.join(ResourceService.BIN_PATH, "cms")
        self.w0_cmdlines = [
            "/usr/bin/python3 %sWorker 0" % path,
            "/usr/bin/python3 %sWorker" % path,
            "python3 %sWorker 0 -c 1" % path,
            "python3 %sWorker -c 1" % path,
            "python3 %sWorker -c 1 0" % path,
            "/usr/bin/env python3 %sWorker 0" % path,
            "/usr/bin/env python3 %sWorker" % path,
            "/usr/bin/env python3 %sWorker 0 -c 1" % path,
            "/usr/bin/env python3 %sWorker -c 1" % path,
            "/usr/bin/env python3 %sWorker -c 1 0" % path,
            sys.executable + " %sWorker" % path,
            sys.executable + " %sWorker 0" % path,
            sys.executable + " %sWorker 0 -c 1" % path,
            sys.executable + " %sWorker -c 1" % path,
            sys.executable + " %sWorker -c 1 0" % path,
        ]
        self.bad_cmdlines = [
            "ps",
            "less %sWorker 0" % path,
            "less /usr/bin/python3 %sWorker 0" % path,
            "/usr/bin/python3 %sWorker 1" % path,
            "/usr/bin/python3 %sAdminWebServer 0" % path,
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
                self.assertEqual(self.pm.find(self.w0), "good")

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
