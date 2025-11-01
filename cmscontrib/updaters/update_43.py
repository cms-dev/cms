#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2020 Andrey Vihrov <andrey.vihrov@gmail.com>

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

The Java 1.4 / gcj programming language is removed.

"""

import logging


logger = logging.getLogger(__name__)

JAVA_GCJ = "Java 1.4 / gcj"
JAVA_JDK = "Java / JDK"

class Updater:

    def __init__(self, data):
        assert data["_version"] == 42
        self.objs = data

    def run(self):
        objs_to_remove = []

        for k, v in self.objs.items():
            if k.startswith("_"):
                continue
            if v["_class"] == "Contest":
                l = v["languages"]
                if JAVA_GCJ in l:
                    l.remove(JAVA_GCJ)
                    if JAVA_JDK not in l:
                        l.append(JAVA_JDK)
            elif v["_class"] in ["Submission", "UserTest"]:
                if v["language"] == JAVA_GCJ:
                    logger.warning("%s %s uses %s, updating to %s."
                                   % (v["_class"], k, v["language"], JAVA_JDK))
                    v["language"] = JAVA_JDK
                    for r in v["results"]:
                        objs_to_remove.extend(
                            self.objs[r]["executables"].values())
                        self.objs[r]["executables"].clear()

        for obj in objs_to_remove:
            del self.objs[obj]

        return self.objs
