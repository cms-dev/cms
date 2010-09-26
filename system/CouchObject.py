#!/usr/bin/python
# -*- coding: utf-8 -*-

import Utils
import couchdb

class CouchObject:
    _to_copy = []
    _to_copy_id = []
    _to_copy_id_array = []

    def __init__(self, document_type):
        self.document_type = document_type
        self.couch_id = ''

    def to_couch(self):
        db = Utils.get_couchdb_database()
        if self.couch_id == '':
            ht = dict()
            ht["document_type"] = self.document_type
        else:
            ht = db[self.couch_id]
        for i in self._to_copy:
            if i in self.__dict__:
                ht[i] = self.__dict__[i]
        for i in CouchObject._to_copy_id:
            if i in self.__dict__:
                ht[i] = self.__dict__[i].get_couch_id()
        for i in CouchObject._to_copy_id_array:
            if i in self.__dict__:
                ht[i] = [j.get_couch_id() for j in self.__dict__[i]]
        if self.couch_id == '':
            self.couch_id = db.create(ht)
        else:
            db[self.couch_id] = ht
        return self.couch_id

if __name__ == "__main__":
    c = CouchObject()
    couch_id = c.to_couch()
    print "Couch ID: %s" % (couch_id)
