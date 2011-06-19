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
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.ext.orderinglist import ordering_list

from SQLAlchemyUtils import Base
from Contest import Contest

class Task(Base):
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True)
    num = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    title = Column(String, nullable=False)
    #attachments (skipped for now)
    statement = Column(String, nullable=False)
    time_limit = Column(Float, nullable=False)
    task_type = Column(String, nullable=False)
    #submission_format (skipped for now)
    #managers (skipped for now)
    #public_testcases (skipped for now)
    token_initial = Column(Integer, nullable=False)
    token_max = Column(Integer, nullable=False)
    token_total = Column(Integer, nullable=False)
    token_min_interval = Column(Float, nullable=False)
    token_gen_time = Column(Float, nullable=False)
    contest_id = Column(Integer, ForeignKey(Contest.id), nullable=False)

    #testcases (backref)
    contest = relationship(Contest,
                           backref=backref('tasks', collection_class=ordering_list('num'), order_by=[num]))

    TASK_TYPE_BATCH = "TaskTypeBatch"
    TASK_TYPE_PROGRAMMING = "TaskTypeProgramming"
    TASK_TYPE_OUTPUT_ONLY = "TaskTypeOutputOnly"

    def __init__(self, name, title, attachments, statement,
                 time_limit, memory_limit,
                 task_type, submission_format, managers,
                 score_type, score_parameters,
                 testcases, public_testcases,
                 token_initial, token_max, token_total,
                 token_min_interval, token_gen_time,
                 contest):
        self.name = name
        self.title = title
        self.attachments = attachments
        self.statement = statement
        self.time_limit = time_limit
        self.memory_limit = memory_limit
        self.task_type = task_type
        self.submission_format = submission_format
        self.managers = managers
        self.score_type = score_type
        self.score_parameters = score_parameters
        #self.scorer = ScoreTypes.get_score_type_class(score_type,
        #                                              score_parameters)
        self.testcases = testcases
        self.public_testcases = public_testcases
        self.token_initial = token_initial
        self.token_max = token_max
        self.token_total = token_total
        self.token_min_interval = token_min_interval
        self.token_gen_time = token_gen_time
        self.contest = contest

    #def choose_couch_id_basename(self):
    #    return "task-%s" % (self.name)

    #def valid_submission(self, files):
    #    return True

class Testcase(Base):
    __tablename__ = 'task_testcases'

    id = Column(Integer, primary_key=True)
    num = Column(Integer, nullable=False)
    input = Column(String, nullable=False)
    output = Column(String, nullable=False)
    task_id = Column(Integer, ForeignKey(Task.id), nullable=False)

    task = relationship(Task,
                        backref=backref('testcases', collection_class=ordering_list('num'), order_by=[num]))

    def __init__(self, input, output, num=None, task=None):
        self.input = input
        self.output = output
        self.num = num
        self.task = task

def sample_task(contest):
    import random
    return Task("task-%d" % (random.randint(1,1000)), "Sample task", [],
                "SHA1 of statement", 1, 512, "TaskTypeBatch", ["task.%l"],
                {"manager_task.%l": "SHA1 of manager_task.%l"}, "ScoreTypeGroupMin",
                [{"multiplicator": 0, "testcases":1, "description":"Test of first function"},
                 {"multiplicator": 0, "testcases":1, "description":"Test of second function"},
                 {"multiplicator": 1, "testcases":5, "description":"Border cases"},
                 {"multiplicator": 1, "testcases":5, "description":"First requirement"},
                 {"multiplicator": 1, "testcases":5, "description":"Second requirement"}],
                [Testcase("SHA1 of input %d" % i, "SHA1 of output %d" % i) for i in xrange(17)],
                [0, 1], 10, 3, 3, 30, 60,
                contest)
