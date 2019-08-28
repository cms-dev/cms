#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2019 Andrey Vihrov <andrey.vihrov@gmail.com>

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

This updater adjusts evaluation messages in submission results.

"""

MESSAGES = {
    "Execution killed (could be triggered by violating memory limits)":
        "Execution killed (runtime error)",
    "Execution failed because the return code was nonzero":
        "Execution failed with non-zero exit code "
        "(could be caused by exception)"
}

class Updater:

    def __init__(self, data):
        assert data["_version"] == 42
        self.objs = data

    @staticmethod
    def update_text(text):
        if text[0] in MESSAGES:
            assert len(text) == 1
            text[0] = MESSAGES[text[0]]

    def run(self):
        for k, v in self.objs.items():
            if k.startswith("_"):
                continue
            elif v["_class"] == "Evaluation":
                self.update_text(v["text"])
            elif v["_class"] == "SubmissionResult":
                for details in ["public_score_details", "score_details"]:
                    if details in v and v[details] is not None:
                        for st in v[details]:
                            for t in st["testcases"]:
                                self.update_text(t["text"])

        return self.objs
