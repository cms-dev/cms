#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright (C) 2010 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright (C) 2010 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright (C) 2010 Matteo Boscariol <boscarim@hotmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import couchdb

import Utils

references = dict()

class CouchObject:
    _to_copy = []
    _to_copy_id = []
    _to_copy_id_array = []

    def __init__(self, document_type, couch_id = None):
        self.document_type = document_type
        self.couch_id = couch_id
        if couch_id == None:
            self.to_couch()

    def __eq__(self, other):
        if other.__class__ != self.__class__:
            return False
        return self.couch_id == other.couch_id

    def choose_couch_id_basename(self):
        return self.document_type

    def choose_couch_id(self):
        # FIXME - This is not totally race free, but this shouldn't be a problem in most cases
        basename = self.choose_couch_id_basename()
        db = Utils.get_couchdb_database()
        num = 0
        while True:
            couch_id = "%s-%d" % (basename, num)
            if couch_id not in db:
                return couch_id
            num += 1

    def to_couch(self):
        db = Utils.get_couchdb_database()
        if self.couch_id == None:
            ht = dict()
            ht["document_type"] = self.document_type
            self.couch_id = self.choose_couch_id()
        else:
            try:
                ht = db[self.couch_id]
            except couchdb.ResourceNotFound:
                ht = dict()
                ht["document_type"] = self.document_type

        for key in self._to_copy:
            try:
                obj = self.__dict__[key]
                ht[key] = obj
            except KeyError:
                Utils.log("Required key %s not found." % (key))

        for key in self._to_copy_id:
            try:
                obj = self.__dict__[key]
                ht[key] = obj.couch_id
            except KeyError:
                Utils.log("Required key %s not found." % (key))
            except AttributeError:
                Utils.log("Key %s not pointing to a CouchObject." % (key))

        for key in self._to_copy_id_array:
            try:
                obj = self.__dict__[key]
                ht[key] = [elem.couch_id for elem in obj]
            except KeyError:
                Utils.log("Required key %s not found." % (key))
            except AttributeError:
                Utils.log("Key %s not pointing to a CouchObject." % (key))

        if self.couch_id == None:
            self.couch_id = db.create(ht)
            references[self.couch_id] = self
        else:
            db[self.couch_id] = ht
        return self.couch_id

    def refresh(self):
        db = Utils.get_couchdb_database()
        ht = db[self.couch_id]
        del ht['_rev']
        del ht['_id']
        del ht['document_type']
        self.__dict__.update(ht)
        fix_references(self)

def from_couch(couch_id, with_refresh = True):
    if couch_id in references:
        if with_refresh:
            references[couch_id].refresh()
        return references[couch_id]
    db = Utils.get_couchdb_database()
    ht = db[couch_id] # FIXME - Error handling
    del ht['_rev']
    del ht['_id']
    ht['couch_id'] = couch_id
    try:
        document_type = ht['document_type']
    except KeyError:
        Utils.log("CouchDB document without document_type.")
        return None
    del ht['document_type']
    if document_type == 'contest':
        from Contest import Contest
        obj = Contest(**ht)
    elif document_type == 'task':
        from Task import Task
        obj = Task(**ht)
    elif document_type == 'user':
        from User import User
        obj = User(**ht)
    elif document_type == 'submission':
        from Submission import Submission
        obj = Submission(**ht)
    elif document_type == 'rankingview':
        from View import RankingView
        obj = RankingView(**ht)
    references[couch_id] = obj
    fix_references(obj)
    return obj

def fix_references(obj):
    for key in obj._to_copy_id:
        if obj.__dict__[key] != None:
            obj.__dict__[key] = from_couch(obj.__dict__[key], with_refresh = False)
    for key in obj._to_copy_id_array:
        obj.__dict__[key] = [from_couch(elem, with_refresh = False) for elem in obj.__dict__[key]]

if __name__ == "__main__":
    c = CouchObject()
    couch_id = c.to_couch()
    print "Couch ID: %s" % (couch_id)
