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

from cms import logger
from cms.db.SQLAlchemyAll import SessionGen, Contest, Submission, Task, User


def get_submissions(contest_id,
                    submission_id=None,
                    user_id=None,
                    task_id=None):
    """Return a list of submission_ids restricted with the given
    information.

    We allow at most one of the parameters to be non-None. If all
    parameters are, we return all submissions for the given contest.

    contest_id (int): the id of the contest.

    submission_id (int): id of the submission to invalidate, or None.
    user_id (int): id of the user we want to invalidate, or None.
    task_id (int): id of the task we want to invalidate, or None.
    level (string): 'compilation' or 'evaluation'

    """
    if [x is not None
        for x in [submission_id, user_id, task_id]].count(True) > 1:
        err_msg = "Too many arguments for invalidate_submission."
        logger.warning(err_msg)
        raise ValueError(err_msg)

    submission_ids = []
    if submission_id is not None:
        submission_ids = [submission_id]
    elif user_id is not None:
        with SessionGen(commit=False) as session:
            user = User.get_from_id(user_id, session)
            submission_ids = [x.id for x in user.submissions]
    elif task_id is not None:
        with SessionGen(commit=False) as session:
            submissions = session.query(Submission)\
                .join(Task).filter(Task.id == task_id)
            submission_ids = [x.id for x in submissions]
    else:
        with SessionGen(commit=False) as session:
            contest = session.query(Contest).\
                filter_by(id=contest_id).first()
            submission_ids = [x.id for x in contest.get_submissions()]

    return submission_ids
