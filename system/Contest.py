#!/usr/bin/python
# -*- coding: utf-8 -*-

import Utils
from CouchObject import CouchObject

class Contest(CouchObject):
    _to_copy = ["name", "description", "token_num", "token_min_interval", "token_gen_time", "start", "stop"]
    _to_copy_id_array = ["tasks", "users", "submissions"]

    def __init__(self, name, description, tasks, users, token_num, token_min_interval, token_gen_time, start = None, stop = None, submissions = [], couch_id = None):
        self.name = name
        self.description = description
        self.tasks = tasks
        self.users = users
        self.token_num = token_num
        self.token_min_interval = token_min_interval
        self.token_gen_time = token_gen_time
        self.start = start
        self.stop = stop
        self.submissions = submissions
        CouchObject.__init__(self, "contest", couch_id)

def sample_contest(couch_id = None):
    import User
    import Task
    import Submission
    c = Contest("hello", "Hello world", [Task.sample_task() for i in range(3)], [User.sample_user() for i in range(10)], 3, 15, 30, couch_id = couch_id)
    s = Submission.sample_submission(couch_id = 'sample_submission')
    c.submissions.append(s)
    c.to_couch()
    s.task = c.tasks[0]
    s.user = c.users[0]
    s.to_couch()
    u = c.users[0]
    u.username = "username"
    u.to_couch()
    return c

if __name__ == "__main__":
    c = sample_contest(couch_id = 'sample_contest')
    print "Couch ID: %s" % (c.couch_id)
