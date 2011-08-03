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

from sqlalchemy import Column, Integer, String, Boolean, Unicode, Float, ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.collections import mapped_collection

from cms.db.SQLAlchemyUtils import Base
from cms.db.Contest import Contest
from cms.db.User import User
from cms.db.Task import Task

class RankingView(Base):
    __tablename__ = 'rankingviews'

    id = Column(Integer, primary_key=True)
    contest_id = Column(Integer, ForeignKey(Contest.id), nullable=False)
    timestamp = Column(Float, nullable=False)

    #scores (backref)
    contest = relationship(Contest, backref=backref("ranking_view", uselist=False))

    def __init__(self, contest, timestamp = 0.0):
        self.contest = contest
        self.timestamp = timestamp

    def set_score(self, score):
        score.rankingview = self
        self.scores[(score.user.username, score.task.num)] = score


class Score(Base):
    __tablename__ = 'scores'

    id = Column(Integer, primary_key=True)
    rankingview_id = Column(Integer, ForeignKey(RankingView.id), nullable=False)
    task_id = Column(Integer, ForeignKey(Task.id), nullable=False)
    user_id = Column(Integer, ForeignKey(User.id), nullable=False)
    score = Column(Float, nullable=False)

    rankingview = relationship(RankingView,
                               backref=backref("scores", collection_class=mapped_collection(lambda s: (s.user.username, s.task.num))))
    task = relationship(Task)
    user = relationship(User)

    def __init__(self, score, task=None, user=None, rankingview=None):
        self.score = score
        self.task = task
        self.user = user
        self.rankingview = rankingview
