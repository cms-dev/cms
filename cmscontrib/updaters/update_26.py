#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2017 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

This updater encodes codenames using a more restricted alphabet.

"""

import ipaddress
import logging
import re
import string
import sys


logger = logging.getLogger(__name__)


CODENAMES = [
    ("Admin", "username"),
    ("Contest", "name"),
    ("Task", "name"),
    ("Testcase", "codename"),
    ("User", "username"),
    ("Team", "code"),
]


FILENAMES = [
    ("PrintJob", "filename"),
    ("File", "filename"),
    ("Executable", "filename"),
    ("Attachment", "filename"),
    ("SubmissionFormatElement", "filename"),
    ("Manager", "filename"),
    ("UserTestFile", "filename"),
    ("UserTestManager", "filename"),
    ("UserTestExecutable", "filename"),
]


FILENAME_DICTS = [
    ("Submission", "files"),
    ("SubmissionResult", "executables"),
    ("Task", "attachments"),
    ("Dataset", "managers"),
    ("UserTest", "files"),
    ("UserTest", "managers"),
    ("UserTestResult", "executables"),
]


DIGESTS = [
    ("PrintJob", "digest"),
    ("File", "digest"),
    ("Executable", "digest"),
    ("Statement", "digest"),
    ("Attachment", "digest"),
    ("Manager", "digest"),
    ("Testcase", "input"),
    ("Testcase", "output"),
    ("UserTest", "input"),
    ("UserTestFile", "digest"),
    ("UserTestManager", "digest"),
    ("UserTestResult", "output"),
    ("UserTestExecutable", "digest"),
]


IP_ADDRESSES = [
    ("Participation", "ip"),
]


# Encodes any unicode string using only "A-Za-z0-9_-". The encoding is
# injective if the input values aren't allowed to contain a double "_".
def encode_codename(s, extra=""):
    encoded_s = ""
    for char in s:
        if char not in string.ascii_letters + string.digits + "_-" + extra:
            encoded_s += "__%x" % ord(char)
        else:
            encoded_s += char
    return encoded_s


class Updater:

    def __init__(self, data):
        assert data["_version"] == 25
        self.objs = data

    def run(self):
        for k, v in self.objs.items():
            if k.startswith("_"):
                continue

            for cls, col in CODENAMES:
                if v["_class"] == cls and v[col] is not None:
                    v[col] = encode_codename(v[col])
                    if v[col] == "":
                        logger.critical(
                            "The dump contains an instance of %s whose %s "
                            "field contains an invalid codename: `%s'.",
                            cls, col, v[col])
                        sys.exit(1)

            for cls, col in FILENAMES:
                if v["_class"] == cls and v[col] is not None:
                    v[col] = encode_codename(v[col], extra="%.")
                    if v[col] in {"", ".", ".."}:
                        logger.critical(
                            "The dump contains an instance of %s whose %s "
                            "field contains an invalid filename: `%s'.",
                            cls, col, v[col])
                        sys.exit(1)

            for cls, col in FILENAME_DICTS:
                if v["_class"] == cls and v[col] is not None:
                    v[col] = {encode_codename(k, extra="%."): v
                              for k, v in v[col].items()}
                    for k in v[col]:
                        if k in {"", ".", ".."}:
                            logger.critical(
                                "The dump contains an instance of %s whose %s "
                                "field contains an invalid filename: `%s'.",
                                cls, col, v[col])
                            sys.exit(1)

            for cls, col in DIGESTS:
                if v["_class"] == cls and v[col] is not None:
                    if not re.match("^([0-9a-f]{40}|x)$", v[col]):
                        logger.critical(
                            "The dump contains an instance of %s whose %s "
                            "field contains an invalid SHA-1 digest: `%s'.",
                            cls, col, v[col])
                        sys.exit(1)

            for cls, col in IP_ADDRESSES:
                if v["_class"] == cls and v[col] is not None:
                    v[col] = list(network.strip() for network in v[col].split())
                    for network in v[col]:
                        try:
                            ipaddress.ip_network(network)
                        except ValueError:
                            logger.critical(
                                "The dump contains an instance of %s whose %s "
                                "field contains an invalid IPv4 address: `%s'.",
                                cls, col, v[col])
                            sys.exit(1)

        return self.objs
