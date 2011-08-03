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

from sqlalchemy import Column, Integer, String, Boolean, Unicode, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship, backref

from SQLAlchemyUtils import Base

class Contest(Base):
    __tablename__ = 'contests'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    token_initial = Column(Integer, nullable=False)
    token_max = Column(Integer, nullable=False)
    token_total = Column(Integer, nullable=False)
    token_min_interval = Column(Float, nullable=False)
    token_gen_time = Column(Float, nullable=False)
    start = Column(Integer, nullable=True)
    stop = Column(Integer, nullable=True)

    #tasks (backref)
    #announcements (skipped for now)
    #ranking_view (backref)
    #tasks (backref)
    #users (backref)
    #get_submissions (in SQLAlchemyAll)

    def __init__(self, name, description, tasks, users,
                 token_initial, token_max, token_total,
                 token_min_interval, token_gen_time,
                 start = None, stop = None, announcements = [],
                 ranking_view = None):
        self.name = name
        self.description = description
        self.tasks = tasks
        self.users = users
        self.token_initial = token_initial
        self.token_max = token_max
        self.token_total = token_total
        self.token_min_interval = token_min_interval
        self.token_gen_time = token_gen_time
        self.start = start
        self.stop = stop
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


def sample_contest():
    c = Contest("hello", "Hello world",
                #[Task.sample_task() for i in range(3)],
                #[User.sample_user() for i in range(10)],
                [], [],
                10, 3, 3, 30, 60)
    #s = Submission.sample_submission()
    #c.submissions.append(s)
    # These to_couch() calls should never fail, because they act on
    # freshly created document
    #c.to_couch()
    #s.task = c.tasks[0]
    #s.user = c.users[0]
    #s.to_couch()
    #u = c.users[0]
    #u.username = "username"
    #u.to_couch()
    return c
