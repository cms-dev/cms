#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>

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

This updater makes sure filenames contain no percent sign, except in a
trailing ".%l", if any.

"""

import logging
import re


logger = logging.getLogger(__name__)

# Fields that contain codenames.
CODENAME_FIELDS = {
    "Contest": ["name"],
    "Task": ["name"],
    "Testcase": ["codename"],
    "Admin": ["username"],
    "User": ["username"],
    "Team": ["code"]
}
# Fields that contain filenames.
FILENAME_FIELDS = {
    "Executable": ["filename"],
    "UserTestManager": ["filename"],
    "UserTestExecutable": ["filename"],
    "PrintJob": ["filename"],
    "Attachment": ["filename"],
    "Manager": ["filename"]
}
# Fields that contain filename schemas.
FILENAME_SCHEMA_FIELDS = {
    "File": ["filename"],
    "UserTestFile": ["filename"]
}
# Fields that contain arrays of filename schemas.
FILENAME_SCHEMA_ARRAY_FIELDS = {
    "Task": ["submission_format"]
}
# Fields that contain digests.
DIGEST_FIELDS = {
    "Statement": ["digest"],
    "Attachment": ["digest"],
    "Manager": ["digest"],
    "Testcase": ["input", "output"],
    "UserTest": ["input"],
    "UserTestFile": ["digest"],
    "UserTestManager": ["digest"],
    "UserTestResult": ["output"],
    "UserTestExecutable": ["digest"],
    "File": ["digest"],
    "Executable": ["digest"],
    "PrintJob": ["digest"]
}


class Updater:

    def __init__(self, data):
        assert data["_version"] == 40
        self.objs = data

        self.bad_codename = False
        self.bad_filename = False
        self.bad_filename_schema = False
        self.bad_digest = False

    def check_codename(self, codename):
        if not re.match("^[A-Za-z0-9_-]+$", codename):
            self.bad_codename = True

    def check_filename(self, filename):
        if not re.match('^[A-Za-z0-9_.-]+$', filename) \
                or filename in {',', '..'}:
            self.bad_filename = True

    def check_filename_schema(self, schema):
        if not re.match('^[A-Za-z0-9_.-]+(\.%%l)?$', schema) \
                or schema in {'.', '..'}:
            self.bad_filename_schema = True

    def check_digest(self, digest):
        if not re.match('^([0-9a-f]{40}|x)$', digest):
            self.bad_digest = True

    def run(self):
        for k, v in self.objs.items():
            if k.startswith("_"):
                continue
            if v["_class"] in CODENAME_FIELDS:
                for attr in CODENAME_FIELDS[v["_class"]]:
                    self.check_codename(v[attr])
            if v["_class"] in FILENAME_FIELDS:
                for attr in FILENAME_FIELDS[v["_class"]]:
                    self.check_filename(v[attr])
            if v["_class"] in FILENAME_SCHEMA_FIELDS:
                for attr in FILENAME_SCHEMA_FIELDS[v["_class"]]:
                    self.check_filename_schema(v[attr])
            if v["_class"] in FILENAME_SCHEMA_ARRAY_FIELDS:
                for attr in FILENAME_SCHEMA_ARRAY_FIELDS[v["_class"]]:
                    for schema in v[attr]:
                        self.check_filename_schema(schema)
            if v["_class"] in DIGEST_FIELDS:
                for attr in DIGEST_FIELDS[v["_class"]]:
                    self.check_digest(v[attr])

        if self.bad_codename:
            logger.error("Some codenames were invalid.")

        if self.bad_filename:
            logger.error("Some filenames were invalid.")

        if self.bad_filename_schema:
            logger.error("Some filename schemas were invalid.")

        if self.bad_digest:
            logger.error("Some digests were invalid.")

        if self.bad_codename or self.bad_filename \
                or self.bad_filename_schema or self.bad_digest:
            raise ValueError("Some data was invalid.")

        return self.objs
