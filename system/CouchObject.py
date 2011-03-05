#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2011 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2011 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2011 Matteo Boscariol <boscarim@hotmail.com>
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

# Global cache of known CouchObjects, used to build inter-object
# references
references = dict()

class CouchObject:

    # Fields that just have to be copied in CouchDB
    _to_copy = []

    # Fields that have to be treated as CouchObjects themselves, thus
    # copied with their IDs
    _to_copy_id = []

    # Fields that have to be treated as arrays of CouchObjects
    _to_copy_id_array = []

    def __init__(self, document_type, couch_id = None, couch_rev = None):
        """Create a new objects and, if couch_id is not specified,
        instantiate it on the database."""

        # couch_id and couch_rev must be specified both or none
        if (couch_id == None and couch_rev != None) or (couch_id != None and couch_rev == None):
            raise ValueError("couch_id and couch_rev must be specified both or none")

        self.document_type = document_type
        self.couch_id = couch_id
        self.couch_rev = couch_rev

        # Istantiate the object if it's not on the database
        if couch_id == None:
            self.to_couch()

    def __eq__(self, other):
        """Compare two objects by ID."""
        if other.__class__ != self.__class__:
            return False
        return self.couch_id == other.couch_id

    def choose_couch_id_basename(self):
        return self.document_type

    def choose_couch_id(self):
        # FIXME - This is not totally race free, but this shouldn't be
        # a problem in most cases
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
        ht = dict()
        ht["document_type"] = self.document_type

        if self.couch_id == None:
            newdoc = True
        else:
            newdoc = False
            ht["_id"] = self.couch_id
            ht["_rev"] = self.couch_rev

        def get_couch_id(obj):
            """Simple wrapper to manage correctly None references."""
            if obj == None:
                return None
            else:
                return obj.couch_id

        for key in self._to_copy:
            try:
                obj = self.__dict__[key]
                ht[key] = obj
            except KeyError:
                Utils.log("Required key %s not found." % (key))

        for key in self._to_copy_id:
            try:
                obj = self.__dict__[key]
                ht[key] = get_couch_id(obj)
            except KeyError:
                Utils.log("Required key %s not found." % (key))
            except AttributeError:
                Utils.log("Key %s not pointing to a CouchObject." % (key))

        for key in self._to_copy_id_array:
            try:
                obj = self.__dict__[key]
                ht[key] = [get_couch_id(elem) for elem in obj]
            except KeyError:
                Utils.log("Required key %s not found." % (key))
            except AttributeError:
                Utils.log("Key %s not pointing to a CouchObject." % (key))

        if newdoc:
            # Choose an ID, save the object and update revision number
            self.couch_id = self.choose_couch_id()
            db[self.couch_id] = ht
            self.couch_rev = ht['_rev']

            # Save the new object in the cache
            references[self.couch_id] = self

        else:
            # Update the object in the database and the revision
            # number in the object
            db[self.couch_id] = ht
            self.couch_rev = ht['_rev']

        return self.couch_id

    def refresh(self):
        # FIXME - While being refreshed, the object can be in an
        # inconsistent state
        db = Utils.get_couchdb_database()
        ht = db[self.couch_id]
        self.couch_rev = ht['_rev']
        del ht['_rev']
        del ht['_id']
        del ht['document_type']
        self.__dict__.update(ht)
        fix_references(self)

    def differences(self, x):
        """Find the fields that has different values than the object
        x, which has to be of the same type as self."""
        diff = []
        for f in self._to_copy + self._to_copy_id + self._to_copy_id_array:
            if x.__dict__[f] != self.__dict__[f]:
                diff.append(f)
        return diff

    def dump(self):
        def couch_id_or_none(obj):
            if obj == None:
                return 'None'
            else:
                return obj.couch_id

        res = "document_type: %s\ncouch_id: %s\ncouch_rev: %s" % (self.document_type, self.couch_id, self.couch_rev)
        for f in self._to_copy:
            res += "\n%s: %s" % (f, str(self.__dict__[f]))
        for f in self._to_copy_id:
            res += "\n%s: %s" % (f, couch_id_or_none(self.__dict__[f]))
        for f in self._to_copy_id_array:
            res += "\n%s: %s" % (f, map(couch_id_or_none, self.__dict__[f]))
        return res

def from_couch(couch_id, with_refresh = True):
    """Retrieve a document from the CouchDB database and convert it
    into the relevant object type. If with_references is set, then the
    object is refreshed from the database even if it's already present
    in the cache: this is recommended operation mode. Disabling
    with_refresh is intended for internal use only."""

    # If present, get the document from the cache, maybe after having
    # refreshed it
    if couch_id in references:
        if with_refresh:
            references[couch_id].refresh()
        return references[couch_id]

    # Retrieve the requested document from the database
    db = Utils.get_couchdb_database()
    try:
        ht = db[couch_id]
    except couchdb.ResourceNotFound:
        return None

    # Field conversion; this piece of code is heavily dependent on the
    # internal structure of the Document class
    ht['couch_id'] = couch_id
    ht['couch_rev'] = ht['_rev']
    del ht['_rev']
    del ht['_id']

    # Detect the document_type for this document
    try:
        document_type = ht['document_type']
    except KeyError:
        Utils.log("CouchDB document without document_type.")
        return None
    del ht['document_type']

    # Depending on the document_type, build the correct object; when
    # contructing the present object, references to other objects
    # still have to be resolved
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

    # Update the cache
    references[couch_id] = obj

    # Fix the references; this _MUST_ happen after the cache is
    # updated, otherwise infinite loop can arise
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
