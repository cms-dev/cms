#!/usr/bin/python
# -*- coding: utf-8 -*-

import User
import Task
from CouchObject import CouchObject
from time import time

class Submission(CouchObject):

    _to_copy = ["timestamp","files","outcome","executables","compilation_result","evaluation_status","token_timestamp"]
    _to_copy_id = ["user","task"]

    def __init__(self,user,task,timestamp,files,outcome,executables,compilation_result,evaluation_status,token_timestamp):
        self.user = user
        self.task = task
        self.timestamp = timestamp
        self.files = files
        self.outcome = outcome
        self.executables = executables
        self.compilation_result = compilation_result
        self.evaluation_status = evaluation_status
        self.token_timestamp = token_timestamp
        CouchObject.__init__(self, "submission")
        
if __name__ == "__main__":
    s = Submission(User.sample_user(),Task.sample_task(),time(),{},[],{},"","",None)
    couch_id=s.to_couch()
    print "Couch ID: %s" % (couch_id)

