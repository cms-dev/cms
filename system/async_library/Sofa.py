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

"""Sofa is a service to store (small) pieces of aggregated data that
satisfies this necessities:
1. data needs to be partially modified;
2. people need to know when some data has been modified;
3. data needs to be stored safely.


*** How to use Sofa.

* Create some subclass of SofaClass to store data. Special class
  attributes are:
  - _subobjects: a dictionary assigning to every attribute that is a
    SofaClass descendant the corresponding SofaClass child class;
  - _vector_subobjects: the same, but when the attribute is a list of
    SofaClass subobjects;
  - _to_delete: list of attribute not to be stored in Sofa.

* Start creating some objects. To every object assign an 'id', that
  will be used to create the unique _id assigned by Sofa to that
  object. Sofa assigns also a _rev attribute that stores the revision
  number. You do not need to care about _id and _rev.

* To store a new document, do not assign _id, and call
  object._put. Sofa assigns to the object the _id and _rev attributes.

* To get a document, you need its _id. Assign the correct _id to the
  object, and call object._get().

* To overwrite a document got from Sofa, call again object._put(). If
  the revision is not the same in the local and remote object, Sofa
  throws an exception.


*** How Sofa behaves.

* When you put an object, its subobjects are not put, unless they do
  not have an _id (i.e., they are not put if they are already present
  in Sofa, even if with an old revision).

* When you get an object, all its subobjects are refreshed, that is,
  taken to the current revision.

"""

import os
import re

import codecs

from AsyncLibrary import Service, \
     rpc_method, rpc_callback, logger
from Utils import ServiceCoord, mkdir, encode_json, decode_json


class Sofa(Service):
    """Offer capibilities of storing and retrieving small objects, and
    to be notified of changes.

    """

    def __init__(self, base_dir, shard):
        # TODO: implement locking and releasing

        logger.initialize(ServiceCoord("Sofa", shard))
        logger.debug("Sofa.__init__")
        Service.__init__(self, shard)

        self.documents = {}
        self.notification_list = {}

        # Create server directories
        self.base_dir = base_dir

        ret = True
        ret = ret and mkdir(self.base_dir)
        if not ret:
            logger.critical("Cannot create necessary directories.")
            self.exit()

        self._load_documents()

    def _load_documents(self):
        """Load in memory the documents already stored in the file
        system.

        """
        loaded = 0
        for cls in os.listdir(self.base_dir):
            self.documents[cls] = {}
            for _id in os.listdir(os.path.join(self.base_dir, cls)):
                loaded += 1
                document = codecs.open(
                    os.path.join(self.base_dir, cls, _id),
                    "r", "utf-8").read()
                self.documents[cls][_id] = decode_json(document)
        logger.info("Loaded %d documents, of which:" % loaded)
        for cls in self.documents:
            logger.info("  %d of class %s," % (len(self.documents[cls]), cls))

    @rpc_method
    def put_document(self, cls, document):
        """Method to insert a new document in Sofa.

        cls (string): the class of the document
        document (dict): the __dict__ of the object to store

        returns ((string, int)): the new _id and _rev assigned to the
                                 object

        """
        logger.debug("Sofa.put_document")
        logger.info("Put document: %s %s" % \
                    (cls, document.get("_id", document.get("id", ""))))

        # Creating hierarchy for the new object
        if cls not in self.documents:
            self.documents[cls] = {}

        # Assigning an _id if not present
        if not u"_id" in document:
            j = 0
            base_id = document.get(u"id", "")
            if base_id == u"":
                base_id = u"unknown"
            ident = u"%s-%d" % (base_id, j)
            while ident in self.documents[cls]:
                j += 1
                ident = u"%s-%d" % (base_id, j)
            document[u"_id"] = ident
            document[u"_rev"] = 0
        elif document[u"_rev"] != \
                 self.documents[cls][document[u"_id"]][u"_rev"]:
            raise ValueError("Revision number mismatch.")
        else:
            document[u"_rev"] += 1

        # Storing the object in memory and file system
        self.documents[cls][document[u"_id"]] = document
        # TODO: defer writing to file system??
        cls_dir = os.path.join(self.base_dir, cls)
        if mkdir(cls_dir):
            json_document = encode_json(document)
            try:
                with codecs.open(os.path.join(cls_dir, document[u"_id"]),
                                 "w", "utf-8") as document_file:
                    document_file.write(json_document)
            except IOError, OSError:
                logger.error("Unable to write file for document %s."
                             % document[u"_id"])
                raise IOError("Cannot store document.")
        else:
            logger.error("Unable to create directory %s." % cls_dir)
            raise IOError("Cannot store document.")

        if document[u"_id"] in self.notification_list:
            for s in self.notification_list[document[u"_id"]]:
                s[0].execute_rpc(s[1], s[2])

        return document[u"_id"], document[u"_rev"]

    def update_rev(self, obj):
        """Check if obj is a reference to a Sofa object (i.e., of the
        form [string, string, integer]) and if true update the
        reference to the last revision.

        obj (object): a value of a sofa object

        return: the up to date reference to the object, or KeyError if
                not a reference
        """
        if obj.__class__ != list or len(obj) != 3 \
               or obj[0].__class__ not in [str, unicode] \
               or obj[1].__class__ not in [str, unicode] \
               or obj[2].__class__ != int:
            raise KeyError
        if obj[0] not in self.documents:
            raise KeyError
        if obj[1] not in self.documents[obj[0]]:
            raise KeyError
        return [obj[0], obj[1], self.documents[obj[0]][obj[1]][u"_rev"]]

    @rpc_method
    def get_document(self, cls, _id):
        """Method to retrieve a document from Sofa.

        cls (string): the class of the document
        _id (string): the _id assigned to the object by Sofa

        return (dict): the __dict__ of the object, or KeyError if not
                       present

        """
        logger.debug("Sofa.get_document")
        logger.info("Get document: %s %s" % (cls, _id))
        if cls not in self.documents:
            raise KeyError("Class %s not recognized" % cls)
        if _id not in self.documents[cls]:
            raise KeyError("Id %s not recognized" % _id)
        for key, value in self.documents[cls][_id].iteritems():
            if self.documents[cls][_id][key].__class__ == list:
                for i, obj in enumerate(self.documents[cls][_id][key]):
                    try:
                        self.documents[cls][_id][key][i] = self.update_rev(obj)
                    except KeyError:
                        pass
            try:
                self.documents[cls][_id][key] = self.update_rev(value)
            except KeyError:
                pass
        return self.documents[cls][_id]

    @rpc_method
    def list_documents(self, cls, regexp_id=None):
        """Returns a list of all document of class cls with id
        matching the regexp given.

        cls (string): the class of documents to retrieve
        regexp_id (string): if the id satisfy this regexp, then we
                            include the document in the list (if None,
                            include all documents)

        return (list): the list of _ids (string) of documents

        """
        logger.debug("Sofa.list_document")
        logger.info("List document: %s %s" % (cls, regexp_id))
        if cls not in self.documents:
            return []
        else:
            if regexp_id != None:
                return [self.documents[cls][x][u"_id"]
                        for x in self.documents[cls]
                        if re.match(regexp_id,
                                    self.documents[cls][x]["id"]) != None]
            else:
                return [self.documents[cls][x][u"_id"]
                        for x in self.documents[cls]]

    @rpc_method
    def subscribe(self, _id, service, shard, method, plus):
        """The caller will be notified when the document identified by
        the _id changes.

        _id (string): the _id of the object we are interested in
        service (string): the service to notify
        shard (int): the shard to notify
        method (string): the method to send the notification to
        plus (object): the object to send together with the
                       notification

        return (bool): False if the object does not exists

        """
        if _id in self.notification_list:
            self.notification_list[_id].add(ServiceCoord(service, shard),
                                            method, plus)
        else:
            self.notification_list[_id] = set(ServiceCoord(service, shard),
                                             method, plus)


class SofaClass:
    """The parent class of any class that wants to be stored in Sofa.

    """
    _to_delete = ["sofa", "service"]
    _subobjects = {}
    _vector_subobjects = {}

    def __init__(self, service, sofa):
        # id is the name of the document as seen from the outside of
        # Sofa. When Sofa first meet a new object (because someone
        # asked to store it) it assigns an _id, which is a unique (in
        # a Sofa instance) identifier for that objects. Subsequent
        # request of storing on an object with an _id will not create
        # a new object, but update the already present one.

        try:
            self.id
        except AttributeError:
            self.id = ""
        self._rev = -1
        self.service = service
        self.sofa = sofa

    def __eq__(self, other):
        """Test equality of the dictionaries of two SofaObjects, maybe
        descending into children objects.

        other (SofaClass): the other object.
        """
        if self.__class__.__name__ != other.__class__.__name__:
            return False
        if self.__dict__.keys() != other.__dict__.keys():
            return False
        for key in self.__dict__:
            if key in self._to_delete:
                continue
            if not self.__dict__[key] == other.__dict__[key]:
                return False
        return True

    def __neq__(self, other):
        return not self == other

    def _put(self, callback, plus=None, bind_obj=None):
        """External interface for storing the document in Sofa.

        callback (method): method to call when done
        plus (object): additional argument for callback
        bind_obj (object): the scope of callback
        """
        if bind_obj == None:
            bind_obj = self.service
        self._put_internal(True, (callback, plus, bind_obj), None)

    @rpc_callback
    def _put_internal(self, data, plus, error):
        """Internal method used for storing the object in Sofa. This
        is going to be called repeatedly, because if we need to put
        subobjects, we terminate this method, call the _put for the
        subobject, and give this method as a callback.

        data (bool): True if subobject's put succedeed, False if not
        plus (object): (callback, plus, bind)
        error (string): the error of the subobject's put.
        """
        callback, new_plus, bind_obj = plus
        if bind_obj == None:
            bind_obj = self.service
        if error != None:
            if callback != None:
                callback(bind_obj, False, new_plus, error)
            return

        # Sending subobjects not already stored
        for key in self._subobjects:
            if not "_id" in self.__dict__[key].__dict__:
                self.__dict__[key]._put(SofaClass._put_internal, plus, self)
                return
        for key in self._vector_subobjects:
            for obj in self.__dict__[key]:
                if not "_id" in obj.__dict__:
                    obj._put(SofaClass._put_internal, plus, self)
                    return

        document = dict((x, self.__dict__[x])
                        for x in self.__dict__
                        if x not in self._to_delete)

        # Replacing subobjects with ids
        for key in self._subobjects:
            document[key] = [document[key].__class__.__name__,
                             document[key]._id, document[key]._rev]
        for key in self._vector_subobjects:
            document[key] = []
            for obj in self.__dict__[key]:
                document[key].append([obj.__class__.__name__,
                                      obj._id, obj._rev])

        self.sofa.put_document(cls=self.__class__.__name__,
                               document=document,
                               bind_obj=self,
                               callback=SofaClass._put_callback,
                               plus=plus)

    @rpc_callback
    def _put_callback(self, data, plus, error=None):
        """Method that is given as a callback to Sofa.put_document. It
        extracts the real callback and additional data from plus and
        call it. Also sets _id and _rev.

        data (string, int): the _id and _rev of the stored object
        plus (callback, plus, bind): the real callback
        error (string): the error, or None
        """
        callback, new_plus, bind_obj = plus
        if bind_obj == None:
            bind_obj = self.service
        if error == None:
            self._id, self._rev = data
        if callback != None:
            callback(bind_obj, data, new_plus, error)

    def _get(self, callback, plus=None, bind_obj=None):
        """External interface for retrieing the document from Sofa.

        callback (method): method to call when done
        plus (object): additional argument for callback
        bind_obj (object): the scope of callback
        """
        if bind_obj == None:
            bind_obj = self.service
        self.sofa.get_document(cls=self.__class__.__name__,
                               _id=self._id,
                               bind_obj=self,
                               callback=SofaClass._get_callback,
                               plus=(callback, plus, bind_obj))

    @rpc_callback
    def _get_callback(self, data, plus, error=None):
        """This is the callback for Sofa.get_document. It accept a
        dictionary with which update the current __dict__ of self. BUt
        some of these attributes need to be translated into
        subobject. When this happen and it is needed, we terminate
        this method, and call the get of the subobject, with
        _get_internal as a callback.

        data (dict): the attributes of the object as in Sofa
        plus (callback, plus, bind): the real callback's data
        error (string): the error of the top object's get_document
        """
        callback, new_plus, bind_obj = plus
        if bind_obj == None:
            bind_obj = self.service
        if error != None:
            if callback != None:
                callback(bind_obj, False, new_plus, error)
            return

        # Otherwise, we fill the object with the new data
        keys = data.keys()
        for key in keys:
            if key in self._subobjects:
                datum = data[key]
                del(data[key])
                if key not in self.__dict__ or \
                       self.__dict__[key].__class__.__name__ != datum[0] or \
                       not hasattr(self.__dict__[key], "_id") or \
                       self.__dict__[key]._id != datum[1] or \
                       not hasattr(self.__dict__[key], "_rev") or \
                       self.__dict__[key]._rev != datum[2]:
                    self.__dict__[key] = \
                        self._subobjects[key](self.service, self.sofa)
                    self.__dict__[key]._id = datum[1]
                    self.__dict__[key]._get(SofaClass._get_internal,
                                            plus + (data,), self)
                    return
            elif key in self._vector_subobjects:
                if key not in self.__dict__:
                    self.__dict__[key] = []
                for (i, datum) in enumerate(data[key]):
                    if datum == None:
                        continue
                    while len(self.__dict__[key]) <= i:
                        self.__dict__[key].append(None)
                    data[key][i] = None
                    if self.__dict__[key][i].__class__.__name__ != \
                           datum[0] or \
                           not hasattr(self.__dict__[key][i], "_id") or \
                           self.__dict__[key][i]._id != datum[1] or \
                           not hasattr(self.__dict__[key][i], "_rev") or \
                           self.__dict__[key][i]._rev != datum[2]:
                        obj = self._vector_subobjects[key](self.service,
                                                           self.sofa)
                        self.__dict__[key][i] = obj
                        obj._id = datum[1]
                        self.__dict__[key][i]._get(SofaClass._get_internal,
                                                   plus + (data,), self)
                        return
                del(data[key])
            else:
                self.__dict__[key] = data[key]
                del data[key]
        if callback != None:
            callback(bind_obj, True, new_plus, None)

    @rpc_callback
    def _get_internal(self, data, plus, error=None):
        """Internal method used for retrieving the object from
        Sofa. This is going to be called when we need to get
        subobjects. It just extract the correct data and call again
        the _get_callback for the top object.

        data: None
        plus (old_plus, dict): the real plus with the remaining
                               attribute to set for the parent object.
        error (string): the error of the subobject's get.

        """
        data = plus[3]
        plus = plus[:3]
        self._get_callback(data, plus, error)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print sys.argv[0], "shard"
    else:
        Sofa(shard=int(sys.argv[1]), base_dir="sf").run()
