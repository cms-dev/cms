#!/usr/bin/env python3

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

Used by DumpImporter and DumpUpdater.

This updater changes the score details so that they provide the score as
a fraction of the max score rather than in absolute terms.

"""

import logging


logger = logging.getLogger(__name__)


# The fields that a subtask always has.
SUBTASK_PARTIAL_KEYS = {"idx", "testcases"}
# The fields it has when all its testcases are public or when viewed
# with "elevated privileges" (i.e., as a contestant having played a
# token or as an admin).
SUBTASK_FULL_KEYS = SUBTASK_PARTIAL_KEYS | {"score", "max_score"}

# The fields that a testcase always has.
TESTCASE_PARTIAL_KEYS = {"idx"}
# The fields it has when it is public or when viewed with "elevated
# privileges" (i.e., as a contestant having played a token or as an
# admin).
TESTCASE_FULL_KEYS = \
    TESTCASE_PARTIAL_KEYS | {"outcome", "text", "time", "memory"}

# The possible "public outcomes" of a testcase (i.e., human-readable
# descriptions of the numerical outcome).
OUTCOMES = {"Correct", "Not correct", "Partially correct"}


def is_number(v):
    return isinstance(v, (int, float))


def is_group_score_details(details: object) -> bool:
    """Return whether the details were produced by a Group* score type.

    details: the (possibly public) score details of a
        submission result.

    return: the answer to the question "do they look like they
        were generated by a Group* score type?".

    """

    if not isinstance(details, list):
        return False

    for subtask in details:
        if not isinstance(subtask, dict):
            return False

        keys = set(subtask.keys())
        # Whether the subtask exposes all its information, which
        # requires all its testcases to do the same.
        subtask_is_visible = False

        if keys == SUBTASK_FULL_KEYS:
            if not is_number(subtask["score"]) \
                    or not is_number(subtask["max_score"]):
                return False
            subtask_is_visible = True
        elif keys != SUBTASK_PARTIAL_KEYS:
            return False

        if not isinstance(subtask["idx"], int) \
                or not isinstance(subtask["testcases"], list):
            return False

        for testcase in subtask["testcases"]:
            if not isinstance(testcase, dict):
                return False

            keys = set(testcase.keys())

            if keys == TESTCASE_FULL_KEYS:
                if testcase["outcome"] not in OUTCOMES \
                        or not isinstance(testcase["text"], list) \
                        or not all(isinstance(s, str)
                                   for s in testcase["text"]) \
                        or not (testcase["time"] is None
                                or is_number(testcase["time"])) \
                        or not (testcase["memory"] is None
                                or is_number(testcase["memory"])):
                    return False
            elif keys != TESTCASE_PARTIAL_KEYS or subtask_is_visible:
                return False

            if not isinstance(testcase["idx"], str):
                return False

    return True


def convert_score_details(details: object) -> bool:
    """Convert the details' subtasks from scores to score_fractions.

    If the given (possibly public) score details came from a Group*
    score type, modify them in-place so that the subtasks, which used
    to store the score as an "absolute" value, end up storing it as a
    fraction of the maximum score.

    details: the (possibly public) score details of a
        submission result.

    return: whether the conversion required an educated guess
        which might not have been perfectly accurate, for example
        because the source data came from a custom Group* score type
        (not from a builtin one), or used partial scores, negative
        scores or scores larger than one.

    """

    inaccurate = False

    if not is_group_score_details(details):
        return inaccurate

    for subtask in details:
        if "score" not in subtask:
            continue

        if subtask["max_score"] == 0:
            # Assuming all outcomes are between 0 and 1, all builtin
            # Group* score types have the property that the fraction is
            # 1 iff all public outcomes are correct and is 0 iff any
            # public outcome is not correct.
            if all(testcase["outcome"] == "Correct"
                   for testcase in subtask["testcases"]):
                subtask["score_fraction"] = 1.0
            elif any(testcase["outcome"] == "Not correct"
                     for testcase in subtask["testcases"]):
                subtask["score_fraction"] = 0.0
            else:
                # Any value strictly between 0 and 1 would work here.
                subtask["score_fraction"] = 0.5

            # Warn the admin about our guesswork.
            inaccurate = True

        else:
            subtask["score_fraction"] = subtask["score"] / subtask["max_score"]

        del subtask["score"]

    return inaccurate


class Updater:

    def __init__(self, data):
        assert data["_version"] == 32
        self.objs = data

    def run(self):
        # See convert_score_details.
        inaccurate = False

        for k, v in self.objs.items():
            if k.startswith("_"):
                continue

            if v["_class"] == "SubmissionResult":

                # We could perform the conversion based only on the
                # dataset's current score type but it isn't necessarily
                # the one that generated the score details, hence this
                # could lead to false positive and negatives. So instead
                # we convert only if it really looks like the details
                # came from a group score type.

                if convert_score_details(v["score_details"]):
                    inaccurate = True

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
