#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2019 Stefano Maggiolo <s.maggiolo@gmail.com>
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

This updater changes the in-database column type for some columns.

"""

import json
import logging


logger = logging.getLogger(__name__)


def fix_text(t):
    if t is None:
        return []
    try:
        t = json.loads(t)
    except ValueError:
        t = [t]
    t[0] = t[0].replace("%d", "%s")
    # Some items were stored as numbers instead of strings.
    return [str(x) for x in t]


class Updater:

    def __init__(self, data):
        assert data["_version"] == 28
        self.objs = data

    def run(self):
        for k, v in self.objs.items():
            if k.startswith("_"):
                continue

            if v["_class"] == "Dataset":
                v["task_type_parameters"] = \
                    json.loads(v["task_type_parameters"])
                v["score_type_parameters"] = \
                    json.loads(v["score_type_parameters"])

            if v["_class"] == "SubmissionResult":
                if v["score_details"] is not None:
                    v["score_details"] = json.loads(v["score_details"])
                if v["public_score_details"] is not None:
                    v["public_score_details"] = \
                        json.loads(v["public_score_details"])
                if v["ranking_score_details"] is not None:
                    v["ranking_score_details"] = \
                        json.loads(v["ranking_score_details"])
                v["compilation_text"] = fix_text(v["compilation_text"])

            if v["_class"] == "Evaluation":
                v["text"] = fix_text(v["text"])

            if v["_class"] == "UserTestResult":
                v["compilation_text"] = fix_text(v["compilation_text"])
                v["evaluation_text"] = fix_text(v["evaluation_text"])

            if v["_class"] == "User":
                v["preferred_languages"] = \
                    json.loads(v["preferred_languages"]) \
                    if "preferred_languages" in v else []

            if v["_class"] == "Task":
                v["primary_statements"] = json.loads(v["primary_statements"])

        return self.objs
