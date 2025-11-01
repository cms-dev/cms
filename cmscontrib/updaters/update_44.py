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

This updater adds file name extensions to relevant executables.

Note:
  - File descriptions are not updated.
  - Out-of-tree languages should be added to LANG_EXT manually.
  - Custom use of USE_JAR = False should be reflected in this updater.

"""

USE_JAR = True

LANG_EXT = {
    "C# / Mono": ".exe",
    "Java / JDK": ".jar" if USE_JAR else ".zip",
    "PHP": ".php",
    "Python 2 / CPython": ".zip",
    "Python 3 / CPython": ".pyz",
}

class Updater:

    def __init__(self, data):
        assert data["_version"] == 43
        self.objs = data

    def run(self):
        for k, v in self.objs.items():
            if k.startswith("_"):
                continue
            if v["_class"] == "Executable":
                s = self.objs[v["submission"]]
                l = s["language"]
                sr = self.objs[v["submission_result"]]

                del sr["executables"][v["filename"]]
                v["filename"] += LANG_EXT.get(l, "")
                sr["executables"][v["filename"]] = k

        return self.objs
