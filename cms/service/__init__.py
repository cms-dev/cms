#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

from cms import logger
from cms.db.SQLAlchemyAll import SessionGen, Contest, User, Task, Submission


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

    contest_id (int): id of the contest to filter with, or None.
    user_id (int): id of the user to filter with, or None.
    task_id (int): id of the task to filter with, or None.
    submission_id (int): id of the submission to filter with, or None.
    session (Session): the database session to use, or None to use a
                       temporary one.
    returns (list of Submissions): the list of submission that match
                                   the given criteria

    """
    if session is None:
        with SessionGen(commit=False) as session:
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

    q = session.query(Submission)
    if submission_id is not None:
        q = q.filter(Submission.id == submission_id)
    if user_id is not None:
        q = q.filter(Submission.user_id == user_id)
    if task_id is not None:
        q = q.filter(Submission.task_id == task_id)
    if contest_id is not None:
        q = q.join(User).filter(User.contest_id == contest_id)\
             .join(Task).filter(Task.contest_id == contest_id)
    return q.all()
