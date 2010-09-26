#!/usr/bin/python
# -*- coding: utf-8 -*-

#import User
#import Problem
from CouchObject import CouchObject
from time import time

class Submission(CouchObject):

    _to_copy = ["timestamp","files","evaluation","executables","compilation_result","evaluation_status","token_timestamp"]
    _to_copy_id_array = ["user","problem"]

    def __init__(self,user,problem,timestamp,files,evaluation,executables,compilation_result,evaluation_status,token_timestamp):
        CouchObject.__init__(self)
        self.couch_id = ''
        self.user = user
        self.problem = problem
        self.timestamp = timestamp
        self.files = files
        self.evaluation = evaluation
        self.executables = executables
        self.compilation_result = compilation_result
        self.evaluation_status = evaluation_status
        self.token_timestamp = token_timestamp
        

if __name__ == "__main__":
    s = Submission([],[],time(),[],[],[],"","",None)
    couch_id=s.to_couch()
    print "Couch ID: %s" % (couch_id)
        
        

