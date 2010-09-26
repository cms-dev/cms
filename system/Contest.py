#!/usr/bin/python
# -*- coding: utf-8 -*-

import Utils
from CouchObject import CouchObject

class Contest(CouchObject):
    _to_copy = ["name", "description", "token_num", "token_min_interval", "token_gen_time", "start", "stop"]
    _to_copy_id_array = ["problems", "users"]

    def __init__(self, name, description, problems, users, token_num, token_min_interval, token_gen_time):
        CouchObject.__init__(self, "contest")
        self.name = name
        self.description = description
        self.problems = problems
        self.users = users
        self.token_num = token_num
        self.token_min_interval = token_min_interval
        self.token_gen_time = token_gen_time

if __name__ == "__main__":
    c = Contest("hello", "Hello world", [], [], 3, 15, 30)
    couch_id = c.to_couch()
    print "Couch ID: %s" % (couch_id)
    c = Contest("second", "Second test", [], [], 3, 15, 30)
    couch_id = c.to_couch()
    c.name = "secondtest"
    couch_id2 = c.to_couch()
    assert couch_id == couch_id2
    print "Couch ID: %s" % (couch_id)
