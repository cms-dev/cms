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

        for key in self._to_copy:
            try:
                obj = self.__dict__[key]
                ht[key] = obj
            except KeyError:
                log("Required key %s not found." % (key))

        for key in self._to_copy_id:
            try:
                obj = self.__dict__[key]
                ht[key] = obj.couch_id
                obj.to_couch()
            except KeyError:
                log("Required key %s not found." % (key))
            except AttributeError:
                log("Key %s not pointing to a CouchObject." % (key))

        for key in self._to_copy_id_array:
            try:
                obj = self.__dict__[key]
                ht[key] = [elem.couch_id for elem in obj]
                for elem in obj:
                    elem.to_couch()
            except KeyError:
                log("Required key %s not found." % (key))
            except AttributeError:
                log("Key %s not pointing to a CouchObject." % (key))

        if self.couch_id == '':
            self.couch_id = db.create(ht)
        else:
            db[self.couch_id] = ht
        return self.couch_id

def from_couch(couch_id):
    db = Utils.get_couchdb_database()
    ht = db[couch_id] # FIXME - Error handling
    del ht['document_type']
    del ht['_rev']
    del ht['_id']
    if ht['document_type'] == 'contest':
        from Contest import Contest
        return Contest(**ht)

if __name__ == "__main__":
    c = CouchObject()
    couch_id = c.to_couch()
    print "Couch ID: %s" % (couch_id)
