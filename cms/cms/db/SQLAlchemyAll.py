#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2011 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2011 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2011 Matteo Boscariol <boscarim@hotmail.com>
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

from sqlalchemy.orm import relationship, backref

from cms.db.SQLAlchemyUtils import db, Base, metadata, Session, SessionGen

from cms.db.Contest import Contest, Announcement
from cms.db.View import RankingView, Score
from cms.db.User import User, Message, Question
from cms.db.Task import Task, Manager, Testcase, Attachment, \
     SubmissionFormatElement
from cms.db.Submission import Submission, Token, Evaluation, File, Executable

# Load all import_from_dict() class methods
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
Contest.get_submissions = get_submissions


def create_empty_ranking_view(self, timestamp=0):
    """Resets all scores to 0 at the given timestamp.

    timestamp (int): the time to assign to the 0 score.

    """
    self.ranking_view = RankingView(self, timestamp=timestamp)
    for user in self.users:
        for task in self.tasks:
            self.ranking_view.set_score(Score(0.0, user=user, task=task))
Contest.create_empty_ranking_view = create_empty_ranking_view


def update_ranking_view(self, scorers):
    """Updates the ranking view with the scores coming from the
    ScoreType instance of every task in the contest.

    """
    for task in self.tasks:
        scorer = scorers[task.id]
        for user in self.users:
            score = scorer.scores.get(user.username, 0.0)
            self.ranking_view.scores[(user.username, task.num)].score = score
Contest.update_ranking_view = update_ranking_view


# The following is a method of User that cannot be put in the right
# file because of circular dependencies.

def get_tokens(self):
    """Returns a list of tokens used by a user.

    returns (list): list of tokens.

    """
    return self.get_session().query(Token).join(Submission).\
           filter(Submission.user == self).all()
User.get_tokens = get_tokens


if __name__ == "__main__":
    if "redrop" in sys.argv[1:]:
        metadata.drop_all()
    else:
        metadata.create_all()
