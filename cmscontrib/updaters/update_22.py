#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2016 Masaki Hara <ackie.h.gmai@gmail.com>
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

This updater adds the default values for the new field 'num_processes' of the
task type Communication.

"""

import json
import logging

logger = logging.getLogger(__name__)


class Updater:

    def __init__(self, data):
        assert data["_version"] == 21
        self.objs = data

    def run(self):
        for k, v in self.objs.items():
            if k.startswith("_"):
                continue
            if v["_class"] == "Dataset" and v["task_type"] == "Communication":
                params = json.loads(v["task_type_parameters"])
                if len(params) < 1:
                    params = [1]
                v["task_type_parameters"] = json.dumps(params)

        return self.objs
