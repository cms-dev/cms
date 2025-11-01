#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2014 Luca Versari <veluca93@gmail.com>
# Copyright © 2016 Stefano Maggiolo <s.maggiolo@gmail.com>
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

Used by DumpImporter and DumpUpdater.

This converts the dump to the new schema introduced to support user
and contest separation.
"""


def split_dict(src, *keys):
    ret = dict()
    for k in list(src.keys()):
        v = src[k]
        if k in keys:
            ret[k] = v
            del src[k]
    return ret


class Updater:
    def __init__(self, data):
        assert data["_version"] == 14
        self.objs = data
        self.next_id = len(data)

    def get_id(self):
        while str(self.next_id) in self.objs:
            self.next_id += 1
        return str(self.next_id)

    def run(self):
        for k in list(self.objs.keys()):
            if k.startswith("_"):
                continue
            v = self.objs[k]
            if v["_class"] == "User":
                self.split_user(k, v)
            elif v["_class"] in ["Message", "PrintJob", "Question",
                                 "Submission", "UserTest"]:
                v["participation"] = v["user"]
                del v["user"]
        return self.objs

    def split_user(self, user_id, user_data):
        # Since all the other objects will now refer to the
        # participation, we use the same id for the participation, and
        # create a new one for the user.
        new_user_id = self.get_id()
        new_participation_id = user_id
        participation_data = split_dict(
            user_data,
            "contest", "delay_time",
            "extra_time", "ip",
            "messages", "usertests",
            "questions", "starting_time",
            "submissions", "hidden")
        self.objs[new_participation_id] = participation_data

        assert user_data["_class"] == "User"
        participation_data["_class"] = "Participation"

        participation_data["password"] = None
        user_data["participations"] = [new_participation_id]

        participation_data["user"] = new_user_id
        self.objs[new_user_id] = user_data

        # FIXME: information about primary_statements /
        # preferrend_languages are silently dropped

        # FIXME: deduplicate repeated names in contests, users and
        # tasks
