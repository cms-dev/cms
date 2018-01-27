#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

Used by ContestImporter and DumpUpdater.

This updater changes the in-database column type for some columns.

"""

from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

import json
import logging

logger = logging.getLogger(__name__)


class Updater(object):

    def __init__(self, data):
        assert data["_version"] == 28
        self.objs = data

    def run(self):
        for k, v in self.objs.iteritems():
            if k.startswith("_"):
                continue

            if v["_class"] == "Dataset":
                v["task_type_parameters"] = \
                    json.loads(v["task_type_parameters"])
                v["score_type_parameters"] = \
                    json.loads(v["score_type_parameters"])
                if v["score_type"] == "Sum":
                    v["score_type_parameters"] = [v["score_type_parameters"]]
                elif not isinstance(v["score_type_parameters"], list):
                    logger.warning("A Dataset uses a custom score type, `%s', "
                                   "whose parameters are not in list format. "
                                   "It needs to be manually updated in order "
                                   "to keep working properly.", v["score_type"])




            # TODO find "Execution killed with signal %d (could be triggered by violating memory limits)# and replace %d by %s




            if v["_class"] == "SubmissionResult":
                if v["score_details"] is not None:
                    v["score_details"] = json.loads(v["score_details"])
                if v["public_score_details"] is not None:
                    v["public_score_details"] = \
                        json.loads(v["public_score_details"])
                if v["ranking_score_details"] is not None:
                    v["ranking_score_details"] = \
                        json.loads(v["ranking_score_details"])
                if v["compilation_text"] is not None:
                    v["compilation_text"] = json.loads(v["compilation_text"])
                else:
                    v["compilation_text"] = []

            if v["_class"] == "Evaluation":
                if v["text"] is not None:
                    v["execution_text"] = json.loads(v["text"])
                else:
                    v["execution_text"] = []
                del v["text"]

            if v["_class"] == "UserTestResult":
                if v["compilation_text"] is not None:
                    v["compilation_text"] = json.loads(v["compilation_text"])
                else:
                    v["compilation_text"] = []
                if v["execution_text"] is not None:
                    v["execution_text"] = json.loads(v["execution_text"])
                else:
                    v["execution_text"] = []

            if v["_class"] == "User":
                v["preferred_languages"] = json.loads(v["preferred_languages"])

            if v["_class"] == "Task":
                v["primary_statements"] = json.loads(v["primary_statements"])

        return self.objs
