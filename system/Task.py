#!/usr/bin/python
# -*- coding: utf-8 -*-

import Utils
from CouchObject import CouchObject

class Task(CouchObject):
    _to_copy = ["name", "title", "attachments", "statement",
                "time_limit", "memory_limit",
                "task_type", "submission_format", "managers",
                "score_type", "score_parameters",
                "testcases", "public_testcases",
                "token_num", "token_min_interval", "token_gen_time",
                ]

    TASK_TYPE_BATCH, TASK_TYPE_PROGRAMMING, TASK_TYPE_OUTPUT_ONLY = range(3)
    SCORE_TYPE_SUM = range(1)

    def __init__(self, name, title, attachments, statement,
                 time_limit, memory_limit,
                 task_type, submission_format, managers,
                 score_type, score_parameters,
                 testcases, public_testcases,
                 token_num, token_min_interval, token_gen_time,
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
        self.token_num = token_num
        self.token_min_interval = token_min_interval
        self.token_gen_time = token_gen_time
        CouchObject.__init__(self, "task", couch_id)

    def choose_couch_id_basename(self):
        return "task-%s" % (self.name)

def sample_task(couch_id = None):
    import random
    return Task("task-%d" % (random.randint(1,1000)), "Sample task", [], "SHA1 of statement",
                1, 512,
                "TaskTypeBatch", ["task.%l"], ["SHA1 of manager_task.%l"],
                "ScoreTypeGroupMin", [{"multiplicator": 0, "testcases":1, "description":"Test of first function"},
                                      {"multiplicator": 0, "testcases":1, "description":"Test of second function"},
                                      {"multiplicator": 1, "testcases":5, "description":"Border cases"},
                                      {"multiplicator": 1, "testcases":5, "description":"First requirement"},
                                      {"multiplicator": 1, "testcases":5, "description":"Second requirement"}],
                [("SHA1 of input %d" % i, "SHA1 of output %d" % i) for i in xrange(17)], [0, 1],
                3, 15, 30, couch_id = couch_id)

if __name__ == "__main__":
    t = sample_task()
    print "Couch ID: %s" % (t.couch_id)
