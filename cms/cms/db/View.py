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

"""Views-related database interface for SQLAlchemy. Not to be used
directly (import from SQLAlchemyAll).

"""

from sqlalchemy import Column, ForeignKey, Integer, Float
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.collections import mapped_collection

from cms.db.SQLAlchemyUtils import Base
from cms.db.Contest import Contest
from cms.db.User import User
from cms.db.Task import Task


class RankingView(Base):
    """Class to store the current ranking of a contest. Not to be used
    directly (import it from SQLAlchemyAll).

    """
    __tablename__ = 'rankingviews'

    # Auto increment primary key.
    id = Column(Integer, primary_key=True)

    # Contest (id and object) the ranking refers to.
    contest_id = Column(Integer,
                        ForeignKey(Contest.id,
                                   onupdate="CASCADE", ondelete="CASCADE"),
                        nullable=False)
    contest = relationship(
        Contest,
        backref=backref("ranking_view",
                        uselist=False,
                        single_parent=True,
                        cascade="all, delete, delete-orphan"),
        single_parent=True)

    # Time the ranking was made.
    timestamp = Column(Integer, nullable=False)

    # Follows the description of the fields automatically added by
    # SQLAlchemy.
    # scores (dict of (user.username, task.num) to Score objects)

    def __init__(self, contest=None, timestamp=0.0, scores=None):
        self.contest = contest
        self.timestamp = timestamp
        if scores is None:
            scores = {}
        self.scores = scores

    def export_to_dict(self):
        """Export object data to a dictionary.

        """
        return {'timestamp': self.timestamp,
                'scores':    [score.export_to_dict() for score in self.scores.itervalues()]}

    def set_score(self, score):
        """Assigns the score to this ranking view. Used to create an
        empty ranking.

        score (object): the Score instance to assign

        """
        score.rankingview = self
        self.scores[(score.user.username, score.task.num)] = score


class Score(Base):
    """Class to store the score a user got in a task. Not to be used
    directly (import it from SQLAlchemyAll).

    """
    __tablename__ = 'scores'

    rankingview_keyfunc = lambda s: (s.user.username, s.task.num)

    # Auto increment primary key.
    id = Column(Integer, primary_key=True)

    # RankingView (id and object) owning the score.
    rankingview_id = Column(Integer,
                            ForeignKey(RankingView.id,
                                       onupdate="CASCADE", ondelete="CASCADE"),
                            nullable=False)
    rankingview = relationship(
        RankingView,
        backref=backref("scores",
                        collection_class=mapped_collection(
                            rankingview_keyfunc),
                        single_parent=True,
                        cascade="all, delete, delete-orphan"))

    # Task (id and object) the score refers to.
    task_id = Column(Integer,
                     ForeignKey(Task.id,
                                onupdate="CASCADE", ondelete="CASCADE"),
                     nullable=False)
    task = relationship(Task)

    # User (id and object) owning the score.
    user_id = Column(Integer,
                     ForeignKey(User.id,
                                onupdate="CASCADE", ondelete="CASCADE"),
                     nullable=False)
    user = relationship(User)

    # The actual score.
    score = Column(Float, nullable=False)

    def __init__(self, score, task=None, user=None, rankingview=None):
        self.score = score
        self.task = task
        self.user = user
        self.rankingview = rankingview

    def export_to_dict(self):
        """Export object data to a dictionary.

        """
        return {'user':  self.user.username,
                'task':  self.task.num,
                'score': self.score}
