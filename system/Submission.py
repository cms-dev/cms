#!/usr/bin/python
# -*- coding: utf-8 -*-

from CouchObject import CouchObject
from time import time

class Submission(CouchObject):

    _to_copy = ["timestamp","files","outcome","executables",
                "compilation_result","evaluation_status","token_timestamp"]
    _to_copy_id = ["user","task"]

    def __init__(self,user,task,timestamp,files,
                outcome,executables,compilation_result,
                evaluation_status,token_timestamp):
        CouchObject.__init__(self,"submission")
        self.user = user
        self.task = task
        self.timestamp = timestamp
        self.files = files
        self.outcome = outcome
        self.executables = executables
        self.compilation_result = compilation_result
        self.evaluation_status = evaluation_status
        self.token_timestamp = token_timestamp
        
if __name__ == "__main__":
    from User import User
    from Task import Task
    u = User("Tizio","112233","Tizio Caio","10.0.0.105")
    t = Task("task", "Sample task", [], "SHA1 of statement",
             1, 512,
             "TaskTypeBatch", ["task.%l"], ["SHA1 of manager_task.%l"],
             "ScoreTypeGroupMin", [{"multiplicator": 0, "testcases":1, "description":"Test of first function"},
                                   {"multiplicator": 0, "testcases":1, "description":"Test of second function"},
                                   {"multiplicator": 1, "testcases":5, "description":"Border cases"},
                                   {"multiplicator": 1, "testcases":5, "description":"First requirement"},
                                   {"multiplicator": 1, "testcases":5, "description":"Second requirement"}],
             [("SHA1 of input %d" % i, "SHA1 of output %d" % i) for i in xrange(17)], [0, 1],
             3, 15, 30)
    s = Submission(u,t,time(),{},[],{},"","",None)
    print u.to_couch()
    print t.to_couch()
    couch_id=s.to_couch()
    print "Couch ID: %s" % (couch_id)

