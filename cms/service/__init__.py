#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
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
from __future__ import print_function
from __future__ import unicode_literals

import logging

from cms.db import SessionGen, Participation, Submission, SubmissionResult, \
    Task


logger = logging.getLogger(__name__)


def get_submissions(contest_id=None, user_id=None, task_id=None,
                    submission_id=None, session=None):
    """Search for submissions that match the given criteria

    The submissions will be returned as a list, and the first four
    parameters determine the filters used to decide which submissions
    to include. Some of them are incompatible, that is they cannot be
    non-None at the same time. When this happens it means that one of
    the parameters "implies" the other (for example, giving the user
    already gives the contest it belongs to). Trying to give them both
    is useless and could only lead to inconsistencies and errors.

    contest_id (int|None): id of the contest to filter with, or None.
    user_id (int|None): id of the user to filter with, or None.
    task_id (int|None): id of the task to filter with, or None.
    submission_id (int|None): id of the submission to filter with, or
        None.
    session (Session|None): the database session to use, or None to
        use a temporary one.

    return ([Submission]): the list of submission that match the given
        criteria

    """
    if session is None:
        with SessionGen() as session:
            return get_submissions(
                contest_id, user_id, task_id, submission_id, session)

    if task_id is not None and contest_id is not None:
        raise ValueError("contest_id is superfluous if task_id is given")
    if user_id is not None and contest_id is not None:
        raise ValueError("contest_id is superfluous if user_id is given")
    if submission_id is not None and contest_id is not None:
        raise ValueError("contest_id is superfluous if submission_id is given")
    if submission_id is not None and task_id is not None:
        raise ValueError("task_id is superfluous if submission_id is given")
    if submission_id is not None and user_id is not None:
        raise ValueError("user_id is superfluous if submission_id is given")

    query = session.query(Submission)
    if submission_id is not None:
        query = query.filter(Submission.id == submission_id)
    if user_id is not None:
        query = query.join(Participation) \
            .filter(Participation.user_id == user_id)
    if task_id is not None:
        query = query.filter(Submission.task_id == task_id)
    if contest_id is not None:
        query = query.join(Participation) \
            .filter(Participation.contest_id == contest_id) \
            .join(Task).filter(Task.contest_id == contest_id)
    return query.all()


def get_submission_results(contest_id=None, user_id=None, task_id=None,
                           submission_id=None, dataset_id=None, session=None):
    """Search for submission results that match the given criteria

    The submission results will be returned as a list, and the first
    five parameters determine the filters used to decide which
    submission results to include. Some of them are incompatible, that
    is they cannot be non-None at the same time. When this happens it
    means that one of the parameters "implies" the other (for example,
    giving the user already gives the contest it belongs to). Trying to
    give them both is useless and could only lead to inconsistencies
    and errors.

    contest_id (int|None): id of the contest to filter with, or None.
    user_id (int|None): id of the user to filter with, or None.
    task_id (int|None): id of the task to filter with, or None.
    submission_id (int|None): id of the submission to filter with, or
        None.
    dataset_id (int|None): id of the dataset to filter with, or None.
    session (Session|None): the database session to use, or None to
        use a temporary one.

    return ([SubmissionResult]): the list of submission results that
        match the given criteria

    """
    if session is None:
        with SessionGen() as session:
            return get_submission_results(
                contest_id, user_id, task_id, submission_id, dataset_id,
                session)

    if task_id is not None and contest_id is not None:
        raise ValueError("contest_id is superfluous if task_id is given")
    if user_id is not None and contest_id is not None:
        raise ValueError("contest_id is superfluous if user_id is given")
    if submission_id is not None and contest_id is not None:
        raise ValueError("contest_id is superfluous if submission_id is given")
    if submission_id is not None and task_id is not None:
        raise ValueError("task_id is superfluous if submission_id is given")
    if submission_id is not None and user_id is not None:
        raise ValueError("user_id is superfluous if submission_id is given")
    if dataset_id is not None and task_id is not None:
        raise ValueError("task_id is superfluous if dataset_id is given")
    if dataset_id is not None and contest_id is not None:
        raise ValueError("contest_id is superfluous if dataset_id is given")

    query = session.query(SubmissionResult).join(Submission)
    if submission_id is not None:
        query = query.filter(SubmissionResult.submission_id == submission_id)
    if dataset_id is not None:
        query = query.filter(SubmissionResult.dataset_id == dataset_id)
    if user_id is not None:
        query = query.join(Participation) \
            .filter(Participation.user_id == user_id)
    if task_id is not None:
        query = query.filter(Submission.task_id == task_id)
    if contest_id is not None:
        query = query.join(Participation) \
            .filter(Participation.contest_id == contest_id)\
            .join(Task).filter(Task.contest_id == contest_id)
    return query.all()


def get_datasets_to_judge(task):
    """Determine the datasets that ES and SS have to judge.

    Return a list of all Dataset objects that are either the
    active_dataset of their Task or have the autojudge flag set.
    These are the ones that are automatically judged in background by
    ES and SS, whereas any other submission has to be explictly judged
    by the contest admin (by invalidating it).

    task (Task): the task to query.

    return ([Dataset]): list of datasets to judge.

    """
    judge = []

    for dataset in task.datasets:
        if dataset.active or dataset.visualized or dataset.autojudge:
            judge.append(dataset)

    return judge
