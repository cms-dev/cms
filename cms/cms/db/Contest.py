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

"""Contest-related database interface for SQLAlchemy. Not to be used
directly (import it from SQLAlchemyAll).

"""

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship, backref

from cms.db.SQLAlchemyUtils import Base


class Contest(Base):
    """Class to store a contest (which is a single day of a
    programming competition). Not to be used directly (import it from
    SQLAlchemyAll).

    """
    __tablename__ = 'contests'

    # Auto increment primary key.
    id = Column(Integer, primary_key=True)

    # Short name of the contest, and longer description. Both human
    # readable.
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)

    # Follows the enforcement of token for any person, for all the
    # task. This enforcements add up to the ones defined task-wise.
    # T_initial is the initial number, T_max is the maximum number in
    # any given time (or -1 to ignore), T_total is the maximum number
    # that can be used in the whole contest (or -1), T_min_interval
    # the minimum interval in seconds between to uses of a token,
    # Every T_gen_time from the beginning of the contest we generate
    # T_gen_number tokens.
    token_initial = Column(Integer, nullable=False)
    token_max = Column(Integer, nullable=False)
    token_total = Column(Integer, nullable=False)
    token_min_interval = Column(Integer, nullable=False)
    token_gen_time = Column(Integer, nullable=False)
    token_gen_number = Column(Integer, nullable=False)

    # Beginning and ending of the contest, unix times.
    start = Column(Integer, nullable=True)
    stop = Column(Integer, nullable=True)

    # Follows the description of the fields automatically added by
    # SQLAlchemy.
    # tasks (list of Task objects)
    # announcements (list of Announcement objects)
    # ranking_view (RankingView object)
    # users (list of User objects)

    # Moreover, we have the following method.
    # get_submissions (defined in SQLAlchemyAll)

    def __init__(self, name, description, tasks, users,
                 token_initial, token_max, token_total,
                 token_min_interval,
                 token_gen_time, token_gen_number,
                 start=None, stop=None, announcements=None,
                 ranking_view=None):
        self.name = name
        self.description = description
        self.tasks = tasks
        self.users = users
        self.token_initial = token_initial
        self.token_max = token_max
        self.token_total = token_total
        self.token_min_interval = token_min_interval
        self.token_gen_time = token_gen_time
        self.token_gen_number = token_gen_number
        self.start = start
        self.stop = stop
        if announcements == None:
            announcements = []
        self.announcements = announcements
        self.ranking_view = ranking_view

    #def update_ranking_view(self):
    #    self.ranking_view.scores = {}
    #    for user in self.users:
    #        self.ranking_view.scores[user.username] = []
    #        for task in self.tasks:
    #            score = task.scorer.scores.get(user.username, 0.0)
    #            self.ranking_view.scores[user.username].append(score)
    #    # This to_couch() call should never fail, because only
    #    # Evaluation Server modifies the ranking view
    #    self.ranking_view.to_couch()

    #def get_task(self, task_name):
    #    """
    #    Returns the first task in the contest with the given name.
    #    """
    #    for t in self.tasks:
    #        if t.name == task_name:
    #            return t
    #    raise KeyError("Task not found")

    #def get_task_index(self, task_name):
    #    """
    #    Returns the index of the first task in the contest with the
    #    given name.
    #    """
    #    for i, t in enumerate(self.tasks):
    #        if t.name == task_name:
    #            return i
    #    raise KeyError("Task not found")


class Announcement(Base):
    """Class to store a messages sent by the contest managers to all
    the users. Not to be used directly (import it from SQLAlchemyAll).

    """
    __tablename__ = 'announcements'

    # Auto increment primary key.
    id = Column(Integer, primary_key=True)

    # Contest for which the announcements are.
    contest_id = Column(Integer,
                        ForeignKey(Contest.id,
                                   onupdate="CASCADE",
                                   ondelete="CASCADE"),
                        nullable=False)
    contest = relationship(Contest, backref=backref('announcements'))

    # Time, subject and text of the announcements.
    timestamp = Column(Integer, nullable=False)
    subject = Column(String, nullable=False)
    text = Column(String, nullable=False)

    def __init__(self, timestamp, subject, text, contest=None):
        self.timestamp = timestamp
        self.subject = subject
        self.text = text
        self.contest = contest
