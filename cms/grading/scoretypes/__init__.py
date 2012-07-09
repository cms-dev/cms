#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
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

import simplejson as json

from cms import logger, plugin_lookup


def get_score_type(submission=None, task=None):
    """Given a task, istantiate the corresponding ScoreType class.

    submission (Submission): the submission that needs the task type.
    task (Task): the task we want to score.

    return (object): an instance of the correct ScoreType class.

    """
    # Validate arguments.
    if [x is not None
        for x in [submission, task]].count(True) != 1:
        raise ValueError("Need at most one way to get the score type.")

    if submission is not None:
        task = submission.task

    score_type_name = task.score_type
    try:
        score_type_parameters = json.loads(task.score_parameters)
    except json.decoder.JSONDecodeError as error:
        logger.error("Cannot decode score type parameters.\n%r." % error)
        raise
    public_testcases = dict((testcase.num, testcase.public)
                            for testcase in task.testcases)

    cls = plugin_lookup(score_type_name,
                        "cms.grading.scoretypes", "scoretypes")

    return cls(score_type_parameters, public_testcases)
