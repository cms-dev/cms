#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Luca Wehrstedt <luca.wehrstedt@gmail.com
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

This updater changes the score details so that they provide the score as
a fraction of the max score rather than in absolute terms.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa
from six import iterkeys, iteritems

import logging


logger = logging.getLogger(__name__)


PUBLIC_SUBTASK_KEYS = {"idx", "testcases"}
PRIVATE_SUBTASK_KEYS = PUBLIC_SUBTASK_KEYS | {"score", "max_score"}

PUBLIC_TESTCASE_KEYS = {"idx"}
PRIVATE_TESTCASE_KEYS = \
    PUBLIC_TESTCASE_KEYS | {"outcome", "text", "time", "memory"}

OUTCOMES = {"Correct", "Not correct", "Partially correct"}

NUMBER = (int, float)


def is_group_score_details(details):
    if not isinstance(details, list):
        return False

    for subtask in details:
        if not isinstance(subtask, dict):
            return False

        keys = set(iterkeys(subtask))
        subtask_is_private = False

        if keys == PRIVATE_SUBTASK_KEYS:
            if not isinstance(subtask["score"], NUMBER) \
                    or not isinstance(subtask["max_score"], NUMBER):
                return False
            subtask_is_private = True
        elif keys != PUBLIC_SUBTASK_KEYS:
            return False

        if not isinstance(subtask["idx"], int) \
                or not isinstance(subtask["testcases"], list):
            return False

        for testcase in subtask["testcases"]:
            if not isinstance(testcase, dict):
                return False

            keys = set(iterkeys(testcase))

            if keys == PRIVATE_TESTCASE_KEYS:
                if testcase["outcome"] not in OUTCOMES \
                        or not isinstance(testcase["text"], list) \
                        or not all(isinstance(s, str)
                                   for s in testcase["text"]) \
                        or not (testcase["time"] is None
                                or isinstance(testcase["time"], NUMBER)) \
                        or not (testcase["memory"] is None
                                or isinstance(testcase["memory"], NUMBER)):
                    return False
            elif keys != PUBLIC_TESTCASE_KEYS or subtask_is_private:
                return False

            if not isinstance(testcase["idx"], str):
                return False

    return True


def convert_score_details(details):
    # Whether we were unable to accurately rebuild the original results.
    inaccurate = False

    for subtask in details:
        if "score" not in subtask:
            continue

        if subtask["max_score"] == 0:
            if all(testcase["outcome"] == "Correct"
                   for testcase in subtask["testcases"]):
                subtask["score_fraction"] = 1.0
            elif any(testcase["outcome"] == "Not correct"
                     for testcase in subtask["testcases"]):
                subtask["score_fraction"] = 0.0
            else:
                # Any value strictly between 0 and 1 would work here.
                subtask["score_fraction"] = 0.5
            inaccurate = True

        else:
            subtask["score_fraction"] = subtask["score"] / subtask["max_score"]

        del subtask["score"]

    return inaccurate


class Updater(object):

    def __init__(self, data):
        assert data["_version"] == 32
        self.objs = data

    def run(self):
        # Whether we were unable to accurately rebuild the original
        # results.
        inaccurate = False

        for k, v in iteritems(self.objs):
            if k.startswith("_"):
                continue

            if v["_class"] == "SubmissionResult":

                # We could perform the conversion based only on the
                # dataset's current score type but it isn't necessarily
                # the one that generated the score details, hence this
                # could lead to false positive and negatives. So instead
                # we convert only if it really looks like the details
                # came from a group score type.

                if is_group_score_details(v["score_details"]):
                    if convert_score_details(v["score_details"]):
                        inaccurate = True

                if is_group_score_details(v["public_score_details"]):
                    if convert_score_details(v["public_score_details"]):
                        inaccurate = True

        if inaccurate:
            logger.info("Some subtasks have a maximum score of zero. They used "
                        "to be reported as successful even if some of their "
                        "testcases failed. This has now been fixed but the old "
                        "data may not have been accurately converted. You are "
                        "advised to check manually or to rescore all affected "
                        "submissions to be safe.")

        return self.objs
