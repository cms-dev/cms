#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright (C) 2010 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright (C) 2010 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright (C) 2010 Matteo Boscariol <boscarim@hotmail.com>
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

import Utils
from CouchObject import CouchObject

class Task(CouchObject):
    _to_copy = ["name", "title", "attachments", "statement",
                "time_limit", "memory_limit",
                "task_type", "submission_format", "managers",
                "score_type", "score_parameters",
                "testcases", "public_testcases",
                "token_initial", "token_max", "token_total",
                "token_min_interval", "token_gen_time"
                ]

    TASK_TYPE_BATCH = "TaskTypeBatch"
    TASK_TYPE_PROGRAMMING = "TaskTypeProgramming"
    TASK_TYPE_OUTPUT_ONLY = "TaskTypeOutputOnly"
    SCORE_TYPE_SUM = range(1)

    def __init__(self, name, title, attachments, statement,
                 time_limit, memory_limit,
                 task_type, submission_format, managers,
                 score_type, score_parameters,
                 testcases, public_testcases,
                 token_initial, token_max, token_total,
                 token_min_interval, token_gen_time,
                 couch_id = None):
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
        self.testcases = testcases
        self.public_testcases = public_testcases
        self.token_initial = token_initial
        self.token_max = token_max
        self.token_total = token_total
        self.token_min_interval = token_min_interval
        self.token_gen_time = token_gen_time
        CouchObject.__init__(self, "task", couch_id)

    def choose_couch_id_basename(self):
        return "task-%s" % (self.name)

    def valid_submission(self, files):
        return True

def sample_task(couch_id = None):
    import random
    return Task("task-%d" % (random.randint(1,1000)), "Sample task", [],
                "SHA1 of statement", 1, 512, "TaskTypeBatch", ["task.%l"],
                {"manager_task.%l": "SHA1 of manager_task.%l"}, "ScoreTypeGroupMin",
                [{"multiplicator": 0, "testcases":1, "description":"Test of first function"},
                 {"multiplicator": 0, "testcases":1, "description":"Test of second function"},
                 {"multiplicator": 1, "testcases":5, "description":"Border cases"},
                 {"multiplicator": 1, "testcases":5, "description":"First requirement"},
                 {"multiplicator": 1, "testcases":5, "description":"Second requirement"}],
                [("SHA1 of input %d" % i, "SHA1 of output %d" % i) for i in xrange(17)], [0, 1],
                10, 3, 3, 30, 60,
                couch_id = couch_id)

if __name__ == "__main__":
    t = sample_task()
    print "Couch ID: %s" % (t.couch_id)
