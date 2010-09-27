#!/usr/bin/python
# -*- coding: utf-8 -*-

from CouchObject import CouchObject
from time import time
import User
import Task

class Submission(CouchObject):

    _to_copy = ["timestamp", "files", "outcome", "executables",
                "compilation_result", "evaluation_status", "token_timestamp"]
    _to_copy_id = ["user", "task"]

    def __init__(self, user, task, timestamp,files,
                 outcome, executables, compilation_result,
                 evaluation_status, token_timestamp,
                 couch_id = None):
        self.user = user
        self.task = task
        self.timestamp = timestamp
        self.files = files
        self.outcome = outcome
        self.executables = executables
        self.compilation_result = compilation_result
        self.evaluation_status = evaluation_status
        self.token_timestamp = token_timestamp
        CouchObject.__init__(self, "submission", couch_id)

    def __eq__(self, other):
        return self.couch_id == other.couch_id

    def invalid(self):
        self.outcome = None
        self.compilation_result = None
        self.evaluation_result = None
        self.executables = None
        self.to_couch()

def sample_submission(couch_id = None):
    return Submission(User.sample_user(), Task.sample_task(), time(), {}, None, None, None, None, None, couch_id = couch_id)

if __name__ == "__main__":
    s = sample_submission()
    print "Couch ID: %s" % (s.couch_id)

