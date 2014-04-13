#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

This adapts the dump to some changes in the model introduced in commit
006de13788e380c284ef4ec96d31b50e547d8c45

"""

from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function


class Updater(object):

    def __init__(self, data):
        assert data["_version"] == 3
        self.objs = data
        self.testcases = dict()

    def run(self):
        for k, v in self.objs.iteritems():
            if k.startswith("_"):
                continue
            if v["_class"] == "Testcase":
                self.testcases[(v["dataset"], v["num"])] = k
                v["codename"] = "%03d" % v["num"]
                del v["num"]

        for k, v in self.objs.iteritems():
            if k.startswith("_"):
                continue
            if v["_class"] == "Evaluation":
                # Hmm... assuming it exists may be not so wise.
                v["testcase"] = self.testcases[(v["dataset"], v["num"])]
                del v["num"]

        return self.objs
