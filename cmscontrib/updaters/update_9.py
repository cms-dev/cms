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

"""A class to update a dump created by CMS.

Used by ContestImporter and DumpUpdater.

This is a fake updater that warns about a change in the way Java
submissions are compiled. This applies only to batch tasks with no
grader (as it was the only task type supporting Java). The difference
is that before the public class submitted by contestant had to be
named "Task", whereas now it must be called with the task short name.

"""

from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

import logging


logger = logging.getLogger(__name__)


class Updater(object):

    def __init__(self, data):
        assert data["_version"] == 8
        self.objs = data

    def run(self):
        for k, v in self.objs.iteritems():
            if k.startswith("_"):
                continue
            if v["_class"] == "Submission" and v["language"] == "java":
                logger.warning(
                    "The way Java submissions are compiled has changed, and\n"
                    "previously valid submissions will now fail to compile.\n"
                    "If you want to obtain again the same results, you have\n"
                    "to (manually) change the name of the public class, from\n"
                    "the literal \"Task\" to the short name of the task,\n"
                    "in each submitted Java file.")
                break

        return self.objs
