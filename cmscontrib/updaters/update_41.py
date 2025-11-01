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

This updater makes sure that the constraints on codenames, filenames,
filename schemas and digests hold.

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

        self.bad_codenames = []
        self.bad_filenames = []
        self.bad_filename_schemas = []
        self.bad_digests = []

    def check_codename(self, class_, attr, codename):
        if not re.match("^[A-Za-z0-9_-]+$", codename):
            self.bad_codenames.append("%s.%s" % (class_, attr))

    def check_filename(self, class_, attr, filename):
        if not re.match('^[A-Za-z0-9_.-]+$', filename) \
                or filename in {',', '..'}:
            self.bad_filenames.append("%s.%s" % (class_, attr))

    def check_filename_schema(self, class_, attr, schema):
        if not re.match('^[A-Za-z0-9_.-]+(\\.%l)?$', schema) \
                or schema in {'.', '..'}:
            self.bad_filename_schemas.append("%s.%s" % (class_, attr))

    def check_digest(self, class_, attr, digest):
        if digest is not None and not re.match('^([0-9a-f]{40}|x)$', digest):
            self.bad_digests.append("%s.%s" % (class_, attr))

    def run(self):
        for k, v in self.objs.items():
            if k.startswith("_"):
                continue
            if v["_class"] in CODENAME_FIELDS:
                for attr in CODENAME_FIELDS[v["_class"]]:
                    self.check_codename(v["_class"], attr, v[attr])
            if v["_class"] in FILENAME_FIELDS:
                for attr in FILENAME_FIELDS[v["_class"]]:
                    self.check_filename(v["_class"], attr, v[attr])
            if v["_class"] in FILENAME_SCHEMA_FIELDS:
                for attr in FILENAME_SCHEMA_FIELDS[v["_class"]]:
                    self.check_filename_schema(v["_class"], attr, v[attr])
            if v["_class"] in FILENAME_SCHEMA_ARRAY_FIELDS:
                for attr in FILENAME_SCHEMA_ARRAY_FIELDS[v["_class"]]:
                    for schema in v[attr]:
                        self.check_filename_schema(v["_class"], attr, schema)
            if v["_class"] in DIGEST_FIELDS:
                for attr in DIGEST_FIELDS[v["_class"]]:
                    self.check_digest(v["_class"], attr, v[attr])

        bad = False

        if self.bad_codenames:
            logger.error(
                "The following fields contained invalid codenames: %s. "
                "They can only contain letters, digits, underscores and "
                "dashes."
                % ", ".join(self.bad_codenames))
            bad = True

        if self.bad_filenames:
            logger.error(
                "The following fields contained invalid filenames: %s. "
                "They can only contain letters, digits, underscores, dashes "
                "and periods and cannot be '.' or '..'."
                % ", ".join(self.bad_filenames))
            bad = True

        if self.bad_filename_schemas:
            logger.error(
                "The following fields contained invalid filename schemas: %s. "
                "They can only contain letters, digits, underscores, dashes "
                "and periods, end with '.%%l' and cannot be '.' or '..'."
                % ", ".join(self.bad_filename_schemas))
            bad = True

        if self.bad_digests:
            logger.error(
                "The following fields contained invalid digests: %s. "
                "They must be 40-character long lowercase hex values, or 'x'."
                % ", ".join(self.bad_digests))
            bad = True

        if bad:
            raise ValueError("Some data was invalid.")

        return self.objs
