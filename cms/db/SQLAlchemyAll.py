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

"""This is the main inteface to the db objects. In particular, every
db objects must be imported from this module.

"""

import sys

from cms.db.SQLAlchemyUtils import db, Base, metadata, Session, \
     ScopedSession, SessionGen

from cms.db.Contest import Contest, Announcement
from cms.db.User import User, Message, Question
from cms.db.Task import Task, Manager, Testcase, Attachment, \
     SubmissionFormatElement, Statement
from cms.db.Submission import Submission, Token, Evaluation, File, Executable
from cms.db.UserTest import UserTest, UserTestFile, UserTestExecutable, \
    UserTestManager
from cms.db.FSObject import FSObject
import cms.db.ImportFromDict


# The following are methods of Contest that cannot be put in the right
# file because of circular dependencies.

def get_submissions(self):
    """Returns a list of submissions (with the information about the
    corresponding task) referring to the contest.

    returns (list): list of submissions.

    """
    return self.get_session().query(Submission).join(Task).\
           filter(Task.contest == self).all()


def get_user_tests(self):
    """Returns a list of user tests (with the information about the
    corresponding user) referring to the contest.

    return (list): list of user tests.

    """
    return self.get_session().query(UserTest).join(User).\
        filter(User.contest == self).all()

Contest.get_submissions = get_submissions
Contest.get_user_tests = get_user_tests


# The following is a method of User that cannot be put in the right
# file because of circular dependencies.

def get_tokens(self):
    """Returns a list of tokens used by a user.

    returns (list): list of tokens.

    """
    return self.get_session().query(Token).join(Submission).\
           filter(Submission.user == self).all()
User.get_tokens = get_tokens


metadata.create_all()


if __name__ == "__main__":
    if "redrop" in sys.argv[1:]:
        metadata.drop_all()
