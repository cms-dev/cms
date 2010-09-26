#!/usr/bin/python
# -*- coding: utf-8 -*-

import Utils
import couchdb

class Contest:
    def __init__(self, name, description, problems, users, token_num, token_min_interval, token_gen_time):
        self.couch_id = ''
        self.name = name
        self.description = description
        self.problems = problems
        self.users = users
        self.token_num = token_num
        self.token_min_interval = token_min_interval
        self.token_gen_time = token_gen_time

    def get_couch_id(self):
        return self.couch_id

    def to_couch(self):
        ht = dict()
        to_copy = ["name", "description", "token_num", "token_min_interval", "token_gen_time", "start", "stop"]
        to_copy_id_array = ["problems", "users"]
        for i in to_copy:
            if i in self.__dict__:
                ht[i] = self.__dict__[i]
            for i in to_copy_id_array:
                if i in self.__dict__:
                    ht[i] = [j.get_couch_id() for j in self.__dict__[i]]
        db = Utils.get_couchdb_database()
        self.couch_id = db.create(ht)
        return self.couch_id

if __name__ == "__main__":
    c = Contest("hello", "Hello world", [], [], 3, 15, 30)
    couch_id = c.to_couch()
    print "Couch ID: %s" % (couch_id)
