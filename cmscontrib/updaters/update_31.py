#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

This updater makes submission_format become a list-of-strings column.

"""

import logging


logger = logging.getLogger(__name__)


class Updater:

    def __init__(self, data):
        assert data["_version"] == 30
        self.objs = data

    def run(self):
        to_delete = set()

        for k, v in self.objs.items():
            if k.startswith("_"):
                continue

            if v["_class"] == "SubmissionFormatElement":
                to_delete.add(k)

            if v["_class"] == "Task":
                v["submission_format"] = list(
                    self.objs[k]["filename"]
                    for k in v.get("submission_format", list()))

        for k in to_delete:
            del self.objs[k]

        return self.objs
