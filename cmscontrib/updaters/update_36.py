#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa
from six import iteritems

import logging


logger = logging.getLogger(__name__)

# Fields that contain filenames.
FILENAME_FIELDS = {"Executable": "filename",
                   "UserTestManager": "filename",
                   "UserTestExecutable": "filename",
                   "PrintJob": "filename",
                   "Attachment": "filename",
                   "Manager": "filename"}
# Fields that contain filename schemas.
FILENAME_SCHEMA_FIELDS = {"File": "filename",
                          "UserTestFile": "filename"}
# Fields that contain arrays of filename schemas.
FILENAME_SCHEMA_ARRAY_FIELDS = {"Task": "submission_format"}


class Updater(object):

    def __init__(self, data):
        assert data["_version"] == 35
        self.objs = data

        self.warn = False

    def check_filename(self, filename):
        if "%" in filename:
            filename = filename.replace("%", "__")
            self.warn = True
        return filename

    def check_filename_schema(self, schema):
        if schema.endswith(".%l"):
            if "%" in schema[:-3]:
                schema = schema[:-3].replace("%", "__") + ".%l"
                self.warn = True
        elif "%" in schema:
            schema = schema.replace("%", "__")
            self.warn = True
        return schema

    def run(self):
        for k, v in iteritems(self.objs):
            if k.startswith("_"):
                continue
            if v["_class"] in FILENAME_FIELDS:
                attr = FILENAME_FIELDS[v["_class"]]
                v[attr] = self.check_filename(v[attr])
            if v["_class"] in FILENAME_SCHEMA_FIELDS:
                attr = FILENAME_SCHEMA_FIELDS[v["_class"]]
                v[attr] = self.check_filename_schema(v[attr])
            if v["_class"] in FILENAME_SCHEMA_ARRAY_FIELDS:
                attr = FILENAME_SCHEMA_ARRAY_FIELDS[v["_class"]]
                v[attr] = list(self.check_filename_schema(schema)
                               for schema in v[attr])

        if self.warn:
            logger.warning("Some files contained '%' (the percent sign) in "
                           "their names: this is now forbidden, and the "
                           "occurrences have been replaced by '__'.")

        return self.objs
