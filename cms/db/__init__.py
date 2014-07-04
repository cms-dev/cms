#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
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

"""Utilities functions that interacts with the database.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import joinedload, configure_mappers

from cms import config


logger = logging.getLogger(__name__)


# Define what this package will provide.

__all__ = [
    "version", "engine",
    # session
    "Session", "ScopedSession", "SessionGen", "custom_psycopg2_connection",
    # base
    "metadata", "Base",
    # types
    "RepeatedUnicode",
    # contest
    "Contest", "Announcement",
    # user
    "User", "Message", "Question",
    # task
    "Task", "Statement", "Attachment", "SubmissionFormatElement", "Dataset",
    "Manager", "Testcase",
    # submission
    "Submission", "File", "Token", "SubmissionResult", "Executable",
    "Evaluation",
    # usertest
    "UserTest", "UserTestFile", "UserTestManager", "UserTestResult",
    "UserTestExecutable",
    # fsobject
    "FSObject",
    # init
    "init_db",
    # drop
    "drop_db",
    # util
    "get_contest_list", "is_contest_id", "ask_for_contest",
    ]


# Instantiate or import these objects.

version = 12


engine = create_engine(config.database, echo=config.database_debug,
                       pool_size=20, pool_recycle=120)


from .session import Session, ScopedSession, SessionGen, \
    custom_psycopg2_connection

from .types import RepeatedUnicode
from .base import metadata, Base
from .contest import Contest, Announcement
from .user import User, Message, Question
from .task import Task, Statement, Attachment, SubmissionFormatElement, \
    Dataset, Manager, Testcase
from .submission import Submission, File, Token, SubmissionResult, \
    Executable, Evaluation
from .usertest import UserTest, UserTestFile, UserTestManager, \
    UserTestResult, UserTestExecutable
from .fsobject import FSObject

from .init import init_db
from .drop import drop_db

from .util import get_contest_list, is_contest_id, ask_for_contest


configure_mappers()


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
