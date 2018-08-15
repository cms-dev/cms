#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2015 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2013-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
# Copyright © 2016 Amir Keivan Mohtashami <akmohtashami97@gmail.com>
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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa

from collections import namedtuple

from sqlalchemy.orm import joinedload

from cms.db import Submission
from cmscommon.constants import SCORE_MODE_MAX, SCORE_MODE_MAX_TOKENED_LAST


__all__ = [
    "compute_changes_for_dataset", "task_score",
]


SubmissionScoreDelta = namedtuple(
    'SubmissionScoreDelta',
    ['submission', 'old_score', 'new_score',
     'old_public_score', 'new_public_score',
     'old_ranking_score_details', 'new_ranking_score_details'])


def compute_changes_for_dataset(old_dataset, new_dataset):
    """This function will compute the differences expected when changing from
    one dataset to another.

    old_dataset (Dataset): the original dataset, typically the active one.
    new_dataset (Dataset): the dataset to compare against.

    returns (list): a list of tuples of SubmissionScoreDelta tuples
        where they differ. Those entries that do not differ will have
        None in the pair of respective tuple entries.

    """
    # If we are switching tasks, something has gone seriously wrong.
    if old_dataset.task is not new_dataset.task:
        raise ValueError(
            "Cannot compare datasets referring to different tasks.")

    task = old_dataset.task

    def compare(a, b):
        if a == b:
            return False, (None, None)
        else:
            return True, (a, b)

    # Construct query with all relevant fields to avoid roundtrips to the DB.
    submissions = \
        task.sa_session.query(Submission)\
            .filter(Submission.task == task)\
            .options(joinedload(Submission.participation))\
            .options(joinedload(Submission.token))\
            .options(joinedload(Submission.results)).all()

    ret = []
    for s in submissions:
        old = s.get_result(old_dataset)
        new = s.get_result(new_dataset)

        diff1, pair1 = compare(
            old.score if old is not None else None,
            new.score if new is not None else None)
        diff2, pair2 = compare(
            old.public_score if old is not None else None,
            new.public_score if new is not None else None)
        diff3, pair3 = compare(
            old.ranking_score_details if old is not None else None,
            new.ranking_score_details if new is not None else None)

        if diff1 or diff2 or diff3:
            ret.append(SubmissionScoreDelta(*(s,) + pair1 + pair2 + pair3))

    return ret


# Computing global scores (for ranking).

def task_score(participation, task):
    """Return the score of a contest's user on a task.

    participation (Participation): the user and contest for which to
        compute the score.
    task (Task): the task for which to compute the score.

    return ((float, bool)): the score of user on task, and True if not
        all submissions of the participation in the task have been scored.

    """
    # As this function is primarily used when generating a rankings table
    # (AWS's RankingHandler), we optimize for the case where we are generating
    # results for all users and all tasks. As such, for the following code to
    # be more efficient, the query that generated task and user should have
    # come from a joinedload with the submissions, tokens and
    # submission_results table. Doing so means that this function should incur
    # no exta database queries.

    submissions = [s for s in participation.submissions
                   if s.task is task and s.official]
    if len(submissions) == 0:
        return 0.0, False

    submissions_and_results = [
        (s, s.get_result(task.active_dataset))
        for s in sorted(submissions, key=lambda s: s.timestamp)]

    if task.score_mode == SCORE_MODE_MAX:
        return _task_score_max(submissions_and_results)
    elif task.score_mode == SCORE_MODE_MAX_TOKENED_LAST:
        return _task_score_max_tokened_last(submissions_and_results)
    else:
        raise ValueError("Unknown score mode '%s'" % task.score_mode)


def _task_score_max_tokened_last(submissions_and_results):
    """Compute score using the "max tokened last" score mode.

    This was used in IOI 2010-2012. The score of a participant on a task is
    the maximum score amongst all tokened submissions and the last submission
    (not yet computed scores count as 0.0).

    submissions_and_results ([(Submission, SubmissionResult|None)]): list of
        all submissions and their results for the participant on the task (on
        the dataset of interest); result is None if not available (that is,
        if the submission has not been compiled).

    return ((float, bool)): (score, partial), same as task_score().

    """
    partial = False

    # The score of the last submission (if computed, otherwise 0.0). Note that
    # partial will be set to True in the next loop.
    last_score = 0.0
    _, last_sr = submissions_and_results[-1]
    if last_sr is not None and last_sr.scored():
        last_score = last_sr.score

    # The maximum score amongst the tokened submissions (not yet computed
    # scores count as 0.0).
    max_tokened_score = 0.0
    for s, sr in submissions_and_results:
        if sr is not None and sr.scored():
            if s.tokened():
                max_tokened_score = max(max_tokened_score, sr.score)
        else:
            partial = True

    return max(last_score, max_tokened_score), partial


def _task_score_max(submissions_and_results):
    """Compute score using the "max" score mode.

    This was used in IOI 2013-2016. The score of a participant on a task is
    the maximum score amongst all submissions (not yet computed scores count
    as 0.0).

    submissions_and_results ([(Submission, SubmissionResult|None)]): list of
        all submissions and their results for the participant on the task (on
        the dataset of interest); result is None if not available (that is,
        if the submission has not been compiled).

    return ((float, bool)): (score, partial), same as task_score().

    """
    partial = False
    score = 0.0

    for _, sr in submissions_and_results:
        if sr is not None and sr.scored():
            score = max(score, sr.score)
        else:
            partial = True

    return score, partial
