#!/usr/bin/python
# -*- coding: utf-8 -*-

import Utils
from CouchObject import CouchObject

class User(CouchObject):
    _to_copy = ["username", "password", "real_name", "ip"]
    _to_copy_id_array = ["tokens"]

    def __init__(self, username, password, real_name, ip):
        CouchObject.__init__(self, "user")
        self.username = username
        self.password = password
        self.real_name = real_name
        self.ip = ip
        self.tokens = []

def sample_user():
    import random
    return User("username-%d" % (random.randint(1, 1000)), "password", "Mister Real Name", "10.0.0.101")

if __name__ == "__main__":
    u = sample_user()
    couch_id = u.to_couch()
    print "Couch ID: %s" % (couch_id)
