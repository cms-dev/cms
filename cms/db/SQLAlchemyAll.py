#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
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

"""This is the main inteface to the db objects. In particular, every
db objects must be imported from this module.

"""

import sys

from sqlalchemy.orm import joinedload
from sqlalchemy.exc import OperationalError

from cms import logger
from cms.db.SQLAlchemyUtils import Base, metadata, Session, \
    ScopedSession, SessionGen, drop_everything
from cms.db.Contest import Contest, Announcement
from cms.db.User import User, Message, Question
from cms.db.Task import Task, Manager, Dataset, Testcase, Attachment, \
    SubmissionFormatElement, Statement
from cms.db.Submission import Submission, SubmissionResult, Token, \
    Evaluation, File, Executable
from cms.db.UserTest import UserTest, UserTestResult, UserTestFile, \
    UserTestExecutable, UserTestManager
from cms.db.FSObject import FSObject


# The following are methods of Contest that cannot be put in the right
# file because of circular dependencies.

def get_submissions(self):
    """Returns a list of submissions (with the information about the
    corresponding task) referring to the contest.

    returns (list): list of submissions.

    """
    return self.sa_session.query(Submission)\
               .join(Task).filter(Task.contest == self)\
               .options(joinedload(Submission.token))\
               .options(joinedload(Submission.results)).all()


def get_submission_results(self):
    """Returns a list of submission results for all submissions in
    the current contest, as evaluated against the active dataset
    for each task.

    returns (list): list of submission results.

    """
    return self.sa_session.query(SubmissionResult)\
               .join(Submission).join(Task).filter(Task.contest == self)\
               .filter(Task.active_dataset_id == SubmissionResult.dataset_id)\
               .all()


def get_user_tests(self):
    """Returns a list of user tests (with the information about the
    corresponding user) referring to the contest.

    return (list): list of user tests.

    """
    return self.sa_session.query(UserTest)\
               .join(Task).filter(Task.contest == self)\
               .options(joinedload(UserTest.results)).all()


def get_user_test_results(self):
    """Returns a list of user_test results for all user_tests in
    the current contest, as evaluated against the active dataset
    for each task.

    returns (list): list of user test results.

    """
    return self.sa_session.query(UserTestResult)\
               .join(UserTest).join(Task).filter(Task.contest == self)\
               .filter(Task.active_dataset_id == UserTestResult.dataset_id)\
               .all()

Contest.get_submissions = get_submissions
Contest.get_submission_results = get_submission_results
Contest.get_user_tests = get_user_tests
Contest.get_user_test_results = get_user_test_results


# The following is a method of User that cannot be put in the right
# file because of circular dependencies.

def get_tokens(self):
    """Returns a list of tokens used by a user.

    returns (list): list of tokens.

    """
    return self.sa_session.query(Token)\
               .join(Submission).filter(Submission.user == self).all()

User.get_tokens = get_tokens


try:
    metadata.create_all()
except OperationalError:
    logger.error("Cannot connect to the database. Please ensure that it is "
                 "running and the connection line `database' in cms.conf is "
                 "correct (in particular, username and password).")
    sys.exit(1)


if __name__ == "__main__":
    if "redrop" in sys.argv[1:]:
        drop_everything()
