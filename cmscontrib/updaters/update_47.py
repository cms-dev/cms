#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2025 Luca Versari <veluca93@gmail.com>
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

Adds opaque_id to user tests.

"""


import random


class Updater:

    def __init__(self, data):
        assert data["_version"] == 46
        self.objs = data

    def run(self):
        used_ids = set()
        for k, v in self.objs.items():
            if k.startswith("_"):
                continue
            if v["_class"] == "UserTest":
                while "opaque_id" not in v or v["opaque_id"] in used_ids:
                    v["opaque_id"] = random.randint(0, 2**63-1)
                used_ids.add(v["opaque_id"])

        return self.objs

