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

import logging

from collections import namedtuple

from sqlalchemy.orm import joinedload

from cms import SCORE_MODE_MAX, SCORE_MODE_MAX_TOKENED_LAST
from cms.db import Submission
from cms.locale import DEFAULT_TRANSLATION

from .language import Language, CompiledLanguage


__all__ = [
    # __init__.py
    "JobException", "format_status_text",
    "compute_changes_for_dataset", "task_score",
    # language.py
    "Language", "CompiledLanguage",
]


logger = logging.getLogger(__name__)


SubmissionScoreDelta = namedtuple(
    'SubmissionScoreDelta',
    ['submission', 'old_score', 'new_score',
     'old_public_score', 'new_public_score',
     'old_ranking_score_details', 'new_ranking_score_details'])


class JobException(Exception):
    """Exception raised by a worker doing a job.

    """
    def __init__(self, msg=""):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)

    def __repr__(self):
        return "JobException(\"%s\")" % (repr(self.msg))


def format_status_text(status, translation=DEFAULT_TRANSLATION):
    """Format the given status text in the given locale.

    A status text is the content of SubmissionResult.compilation_text,
    Evaluation.text and UserTestResult.(compilation|evaluation)_text.
    It is a list whose first element is a string with printf-like
    placeholders and whose other elements are the data to use to fill
    them.
    The first element will be translated using the given translator (or
    the identity function, if not given), completed with the data and
    returned.

    status ([unicode]): a status, as described above.
    translation (Translation): the translation to use.

    """
    _ = translation.gettext

    try:
        if not isinstance(status, list):
            raise TypeError("Invalid type: %r" % type(status))

        # The empty msgid corresponds to the headers of the pofile.
        text = _(status[0]) if status[0] != '' else ''
        return text % tuple(status[1:])
    except Exception:
        logger.error("Unexpected error when formatting status "
                     "text: %r", status, exc_info=True)
        return _("N/A")


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

    return ((float, bool)): the score of user on task, and True if the
        score could change because of a submission yet to score.

    """
    # As this function is primarily used when generating a rankings table
    # (AWS's RankingHandler), we optimize for the case where we are generating
    # results for all users and all tasks. As such, for the following code to
    # be more efficient, the query that generated task and user should have
    # come from a joinedload with the submissions, tokens and
    # submission_results table.  Doing so means that this function should incur
    # no exta database queries.

    # If the score could change due to submission still being compiled
    # / evaluated / scored.
    partial = False

    submissions = [s for s in participation.submissions
                   if s.task is task and s.official]
    submissions.sort(key=lambda s: s.timestamp)

    if len(submissions) == 0:
        return 0.0, False

    if task.score_mode == SCORE_MODE_MAX:
        # Like in IOI 2013-2016: maximum score amongst all submissions.

        # The maximum score amongst all submissions (not yet computed
        # scores count as 0.0).
        max_score = 0.0

        for s in submissions:
            sr = s.get_result(task.active_dataset)
            if sr is not None and sr.scored():
                max_score = max(max_score, sr.score)
            else:
                partial = True

        score = max_score

    elif task.score_mode == SCORE_MODE_MAX_TOKENED_LAST:
        # Like in IOI 2010-2012: maximum score among all tokened
        # submissions and the last submission.

        # The score of the last submission (if computed, otherwise 0.0).
        last_score = 0.0
        # The maximum score amongst the tokened submissions (not yet computed
        # scores count as 0.0).
        max_tokened_score = 0.0

        # Last score: if the last submission is scored we use that,
        # otherwise we use 0.0 (and mark that the score is partial
        # when the last submission could be scored).
        last_s = submissions[-1]
        last_sr = last_s.get_result(task.active_dataset)

        if last_sr is not None and last_sr.scored():
            last_score = last_sr.score
        else:
            partial = True

        for s in submissions:
            if s.tokened():
                sr = s.get_result(task.active_dataset)
                if sr is not None and sr.scored():
                    max_tokened_score = max(max_tokened_score, sr.score)
                else:
                    partial = True

        score = max(last_score, max_tokened_score)

    else:
        raise ValueError("Unknown score mode '%s'" % task.score_mode)

    return score, partial
