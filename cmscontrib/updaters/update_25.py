#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2017 Stefano Maggiolo <s.maggiolo@gmail.com>
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

This updater changes the programming language code after the change to
language plugins (for example, from

"""

import logging

logger = logging.getLogger(__name__)


LANGUAGE_MAP = {
    "c": "C11 / gcc",
    "cpp": "C++11 / g++",
    "pas": "Pascal / fpc",
    "py": "Python 2 / CPython",
    "php": "PHP",
    "java": "Java 1.4 / gcj",
    "hs": "Haskell / ghc",
}


class Updater:

    def __init__(self, data):
        assert data["_version"] == 24
        self.objs = data
        self._warned_lang = set()

    def run(self):
        for k, v in self.objs.items():
            if k.startswith("_"):
                continue
            if v["_class"] == "Contest":
                v["languages"] = [self._map_language(l)
                                  for l in v["languages"]]
            if v["_class"] == "Submission" or v["_class"] == "UserTest":
                v["language"] = self._map_language(v["language"])

        return self.objs

    def _map_language(self, l):
        if l in LANGUAGE_MAP:
            return LANGUAGE_MAP[l]
        else:
            if l not in self._warned_lang:
                logger.warning(
                    "Unrecognized language `%s', "
                    "copying without modifying.", l)
                self._warned_lang.add(l)
            return l
