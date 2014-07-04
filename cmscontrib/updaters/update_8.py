#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

This adapts the dump to some changes in the model introduced in the
commit that created this same file.

"""

from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

from datetime import timedelta


class Updater(object):

    def __init__(self, data):
        assert data["_version"] == 7
        self.objs = data

    def run(self):
        for k, v in self.objs.iteritems():
            if k.startswith("_"):
                continue
            if v["_class"] == "Contest" or v["_class"] == "Task":
                if v["token_initial"] is None:
                    v["token_mode"] = "disabled"
                elif v["token_gen_number"] > 0 and v["token_gen_time"] == 0:
                    v["token_mode"] = "infinite"
                else:
                    v["token_mode"] = "finite"

                v["token_max_number"] = v.pop("token_total")
                v["token_gen_initial"] = v.pop("token_initial")
                v["token_gen_interval"] = v.pop("token_gen_time")
                v["token_gen_max"] = v.pop("token_max")

                if v["token_gen_initial"] is None:
                    v["token_gen_initial"] = 0
                if v["token_gen_interval"] == 0:
                    v["token_gen_interval"] = 60

        return self.objs
