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

Converts the '*_sandbox' columns to '*_sandbox_paths' columns.

"""

def convert(obj: dict, key: str):
    old_val = obj.pop(key, None)

    if old_val is None:
        new_val = None
    elif old_val == '':
        new_val = []
    else:
        new_val = old_val.split(':')

    obj[key + '_paths'] = new_val

class Updater:

    def __init__(self, data):
        assert data["_version"] == 45
        self.objs = data

    def run(self):
        for k, v in self.objs.items():
            if k.startswith("_"):
                continue
            if v["_class"] == "SubmissionResult":
                convert(v, 'compilation_sandbox')
            elif v["_class"] == "Evaluation":
                convert(v, 'evaluation_sandbox')
            elif v["_class"] == "UserTestResult":
                convert(v, 'compilation_sandbox')
                convert(v, 'evaluation_sandbox')

        return self.objs

