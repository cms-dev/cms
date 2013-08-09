#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Fabian Gundlach <320pointsguy@gmail.com>
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

from __future__ import unicode_literals


def split_dict(src, *keys):
    ret = dict()
    for k in list(src.iterkeys()):
        v = src[k]
        if k in keys:
            ret[k] = v
            del src[k]
    return ret


class Updater(object):

    def __init__(self, data):
        assert data["_version"] == 5
        self.objs = data
        self.next_id = len(data)
        self.groups = dict()

    def get_id(self):
        while unicode(self.next_id) in self.objs:
            self.next_id += 1
        return unicode(self.next_id)

    def run(self):
        for k in list(self.objs.iterkeys()):
            if k.startswith("_"):
                continue
            v = self.objs[k]
            if v["_class"] == "Contest":
                contest_data = v

                group_id = self.get_id()
                group_data = split_dict(
                    contest_data,
                    "start", "stop",
                    "per_user_time")
                self.objs[group_id] = group_data

                self.groups[k] = group_id

                group_data["_class"] = "Group"
                group_data["contest"] = k
                group_data["name"] = "default"

                contest_data["main_group"] = group_id

        for k, v in self.objs.iteritems():
            if k.startswith("_"):
                continue
            if v["_class"] == "User":
                v["group"] = self.groups[v["contest"]]

        return self.objs
