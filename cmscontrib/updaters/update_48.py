#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2025 p. randla <prandla@r9.pm>
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

Creates Group objects and moves contest parameters into them.

"""

class Updater:

    def __init__(self, data):
        assert data["_version"] == 47
        self.objs = data
        self.next_id = len(data)

    def get_id(self):
        while str(self.next_id) in self.objs:
            self.next_id += 1
        return str(self.next_id)

    def run(self):
        contest_to_group = {}
        for k, v in list(self.objs.items()):
            if k.startswith("_"):
                continue
            if v["_class"] == "Contest":
                new_obj = {
                    "_class": "Group",
                    "name": "default",
                    "contest": k,
                }
                for prop in ("start", "stop", "analysis_enabled", "analysis_start", "analysis_stop", "per_user_time"):
                    if prop in v:
                        new_obj[prop] = v[prop]
                new_key = self.get_id()
                self.objs[new_key] = new_obj
                v["main_group"] = new_key
                contest_to_group[k] = new_key
        for k, v in self.objs.items():
            if k.startswith("_"):
                continue
            if v["_class"] == "Participation":
                v["group"] = contest_to_group[v["contest"]]

        return self.objs

