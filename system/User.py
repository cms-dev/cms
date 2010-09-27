#!/usr/bin/python
# -*- coding: utf-8 -*-

import Utils
from CouchObject import CouchObject

class User(CouchObject):
    _to_copy = ["username", "password", "real_name", "ip", "hidden"]
    _to_copy_id_array = ["tokens"]

    def __init__(self, username, password,
                 real_name, ip, tokens = [], hidden = False,
                 couch_id = None):
        self.username = username
        self.password = password
        self.real_name = real_name
        self.ip = ip
        self.tokens = tokens
        self.hidden = hidden
        CouchObject.__init__(self, "user", couch_id)

    def choose_couch_id_basename(self):
        return "user-%s" % (self.username)

def sample_user(couch_id = None):
    import random
    return User("username-%d" % (random.randint(1, 1000)), "password",
                "Mister Real Name", "10.0.0.101", couch_id = couch_id)

if __name__ == "__main__":
    u = sample_user()
    print "Couch ID: %s" % (u.couch_id)
