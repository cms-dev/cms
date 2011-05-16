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

"""Testing suite for FileCacher

"""

import os

from AsyncLibrary import rpc_callback, rpc_method, logger
from DecoratedServices import TestService
from Utils import ServiceCoord, decode_json
from Sofa import SofaClass


class ChildClass(SofaClass):
    """Example of a very simple Sofa object.

    """
    def __init__(self, service, sofa):
        self.child_member = "child"
        self.id = "id_child"
        SofaClass.__init__(self, service, sofa)


class ParentClass(SofaClass):
    """Example of a Sofa object with subobjects.

    """
    _subobjects = {"child": ChildClass}
    _vector_subobjects = {"children": ChildClass}

    def __init__(self, service, sofa):
        self.child = ChildClass(service, sofa)
        self.child.child_member = "child_alone"
        self.children = []
        for i in xrange(2):
            self.children.append(ChildClass(service, sofa))
            self.children[i].child_member = "child_%s" % i
        SofaClass.__init__(self, service, sofa)
        self.parent_member = "parent"
        self.id = "id_parent"


class TestSofa(TestService):
    """Service that performs automatically some tests for the
    Sofa service.

    """

    def __init__(self, shard):
        logger.initialize(ServiceCoord("TestSofa", shard))
        logger.debug("TestSofa.__init__")
        TestService.__init__(self, shard)
        self.SofaService = self.connect_to(
            ServiceCoord("Sofa", 0))
        if not self.SofaService.connected:
            logger.error("Please run the Sofa service.")
            self.exit()


### TEST 000 ###

    def test_000(self):
        """Put a new parent document in Sofa

        """
        self.parent = ParentClass(self, self.SofaService)
        logger.info("  I am sending the parent object to Sofa")
        self.parent._put(TestSofa.test_000_callback,
                         ("Test #", 0))

    @rpc_callback
    def test_000_callback(self, data, plus, error=None):
        if error != None:
            self.test_end(False, "Error received: %s." % error)
        elif plus != ("Test #", 0):
            self.test_end(False, "Plus object not received correctly.")
        elif not os.path.exists(os.path.join("sf", "ParentClass", data[0])):
            self.test_end(False, "Parent not stored in local cache.")
        elif not os.path.exists(os.path.join("sf", "ChildClass",
                self.parent.child._id)):
            self.test_end(False, "Child not stored in local cache.")
        elif not os.path.exists(os.path.join("sf", "ChildClass",
                self.parent.children[1]._id)):
            self.test_end(False, "Children not stored in local cache.")

        self.parent_dict = decode_json(open(
            os.path.join("sf", "ParentClass", data[0])).read())
        self.child_dict = decode_json(open(
            os.path.join("sf", "ChildClass",
                         self.parent.child._id)).read())
        self.children_dict = decode_json(open(
            os.path.join("sf", "ChildClass",
                         self.parent.children[1]._id)).read())

        if self.parent_dict["id"] != "id_parent" or \
               self.parent_dict["parent_member"] != "parent" or \
               self.parent_dict["child"] != ["ChildClass",
                                             self.parent.child._id,
                                             self.parent.child._rev] or \
               self.parent_dict["children"][1] != \
                            ["ChildClass",
                             self.parent.children[1]._id,
                             self.parent.children[1]._rev]:
            self.test_end(False, "Parent not stored correctly.")
        elif self.child_dict["id"] != "id_child" or \
                 self.child_dict["child_member"] != "child_alone":
            self.test_end(False, "Child not stored correctly.")
        elif self.children_dict["id"] != "id_child" or \
                 self.children_dict["child_member"] != "child_1":
            self.test_end(False, "Children not stored correctly.")
        else:
            self.test_end(True, "Document stored correctly " +
                          "and plus object received.")


### TEST 001 ###

    def test_001(self):
        """Retrieve the parents list.

        """
        logger.info("  I am retrieving the list of parents")
        self.SofaService.list_documents(cls="ParentClass",
                                        callback=TestSofa.test_001_callback,
                                        plus=("Test #", 1))

    @rpc_callback
    def test_001_callback(self, data, plus, error=None):
        if error != None:
            self.test_end(False, "Error received: %s." % error)
        elif plus != ("Test #", 1):
            self.test_end(False, "Plus object not received correctly.")
        elif self.parent._id not in data:
            self.test_end(False, "Parent not in Sofa.")
        else:
            self.test_end(True, "List and plus object received correctly.")


### TEST 002 ###

    def test_002(self):
        """Retrieve the children list.

        """
        logger.info("  I am retrieving the list of children")
        self.SofaService.list_documents(cls="ChildClass",
                                        callback=TestSofa.test_002_callback,
                                        plus=("Test #", 2))

    @rpc_callback
    def test_002_callback(self, data, plus, error=None):
        if error != None:
            self.test_end(False, "Error received: %s." % error)
        elif plus != ("Test #", 2):
            self.test_end(False, "Plus object not received correctly.")
        elif self.parent.child._id not in data:
            self.test_end(False, "Child not in Sofa.")
        elif self.parent.children[1]._id not in data:
            self.test_end(False, "Children not in Sofa.")
        else:
            self.test_end(True, "List and plus object received correctly.")


### TEST 003 ###

    def test_003(self):
        """Retrieve the parent from Sofa.

        """
        logger.info("  I am retrieving a copy of parent.")
        self.new_parent = ParentClass(self, self.SofaService)
        self.new_parent._id = self.parent._id
        self.new_parent._get(TestSofa.test_003_callback,
                             ("Test #", 3))

    @rpc_callback
    def test_003_callback(self, data, plus, error=None):
        if error != None:
            self.test_end(False, "Error received: %s." % error)
        elif plus != ("Test #", 3):
            self.test_end(False, "Plus object not received correctly.")
        elif not data:
            self.test_end(False, "Did not get parent.")
        elif not self.new_parent == self.parent:
            self.test_end(False, "Did not get parent correctly.")
        else:
            self.test_end(True, "Parent and plus received correctly.")


### TEST 004 ###

    def test_004(self):
        """Retrieve the parent again from Sofa.

        """
        logger.info("  I am retrieving again the same copy of parent. " +
                    "Only one get document should be issued")
        self.new_parent._get(TestSofa.test_004_callback,
                             ("Test #", 4))

    @rpc_callback
    def test_004_callback(self, data, plus, error=None):
        if error != None:
            self.test_end(False, "Error received: %s." % error)
        elif plus != ("Test #", 4):
            self.test_end(False, "Plus object not received correctly.")
        elif not data:
            self.test_end(False, "Did not get parent.")
        elif not self.new_parent == self.parent:
            self.test_end(False, "Did not get parent correctly.")
        else:
            self.test_end(True, "Parent and plus received correctly.")


### TEST 005 ###

    def test_005(self):
        """Put again one of the children in Sofa.

        """
        logger.info("  I am sending the subobject child to Sofa")
        self.child_rev = self.parent.child._rev
        self.parent.child.child_member = "new_child_alone"
        self.parent.child._put(TestSofa.test_005_callback,
                               ("Test #", 5))

    @rpc_callback
    def test_005_callback(self, data, plus, error=None):
        if error != None:
            self.test_end(False, "Error received: %s." % error)
        elif plus != ("Test #", 5):
            self.test_end(False, "Plus object not received correctly.")
        elif not os.path.exists(os.path.join("sf", "ChildClass",
                self.parent.child._id)):
            self.test_end(False, "Child not stored in local cache.")

        self.child_dict = decode_json(open(
            os.path.join("sf", "ChildClass",
                         self.parent.child._id)).read())

        if self.child_dict["id"] != "id_child" or \
               self.child_dict["child_member"] != "new_child_alone" or \
               self.child_dict["_rev"] != self.child_rev + 1 or \
               self.parent.child._rev != self.child_rev + 1:
            self.test_end(False, "Child not stored correctly.")
        else:
            self.test_end(True, "Document stored correctly " +
                          "and plus object received.")


### TEST 006 ###

    def test_006(self):
        """Put again one of the children in Sofa.

        """
        logger.info("  I am sending the subobject child to Sofa")
        self.children_rev = self.parent.children[1]._rev
        self.parent.children[1].child_member = "new_child_1"
        self.parent.children[1]._put(TestSofa.test_006_callback,
                                     ("Test #", 6))

    @rpc_callback
    def test_006_callback(self, data, plus, error=None):
        if error != None:
            self.test_end(False, "Error received: %s." % error)
        elif plus != ("Test #", 6):
            self.test_end(False, "Plus object not received correctly.")
        elif not os.path.exists(os.path.join("sf", "ChildClass",
                self.parent.child._id)):
            self.test_end(False, "Child not stored in local cache.")

        self.children_dict = decode_json(open(
            os.path.join("sf", "ChildClass",
                         self.parent.children[1]._id)).read())

        if self.children_dict["id"] != "id_child" or \
               self.children_dict["child_member"] != "new_child_1" or \
               self.children_dict["_rev"] != self.children_rev + 1 or \
               self.parent.children[1]._rev != self.children_rev + 1:

            self.test_end(False, "Children 1 not stored correctly.")
        else:
            self.test_end(True, "Document stored correctly " +
                          "and plus object received.")


### TEST 007 ###

    def test_007(self):
        """Retrieve the parent again from Sofa, when children have
        changed.

        """
        logger.info("  I am retrieving again the same copy of parent. " +
                    "Only two children's get documents should be issued")
        self.new_parent._get(TestSofa.test_007_callback,
                             ("Test #", 7))

    @rpc_callback
    def test_007_callback(self, data, plus, error=None):
        if error != None:
            self.test_end(False, "Error received: %s." % error)
        elif plus != ("Test #", 7):
            self.test_end(False, "Plus object not received correctly.")
        elif not data:
            self.test_end(False, "Did not get parent.")
        elif not self.new_parent == self.parent:
            self.test_end(False, "Did not get parent correctly.")
        else:
            self.test_end(True, "Parent and plus received correctly.")


### TEST 008 ###

    def test_008(self):
        """Subscribing to the parent.

        """
        logger.info("  I am subscring to the parent.")
        self.SofaService.subscribe(_id=self.new_parent._id,
                                   service=self.__class__.__name__,
                                   shard=self.shard,
                                   method="on_parent_change",
                                   plus_obj=("Test #", 8, "b"),
                                   callback=TestSofa.test_008_callback,
                                   plus=("Test #", 8))

    @rpc_callback
    def test_008_callback(self, data, plus, error=None):
        if error != None:
            self.test_end(False, "Error received: %s." % error)
        elif plus != ("Test #", 8):
            self.test_end(False, "Plus object not received correctly.")
        elif not data:
            self.test_end(False, "Did not received True.")
        else:
            self.test_end(True, "Parent and plus received correctly.")


### TEST 009 ###

    def test_009(self):
        """Updating the parent

        """
        logger.info("  I am updating the parent to get the notification.")
        self.new_parent._put(TestSofa.test_009_callback,
                             ("Test #", 9))

    @rpc_callback
    def test_009_callback(self, data, plus, error=None):
        if error != None:
            self.test_end(False, "Error received: %s." % error)
        elif plus != ("Test #", 9):
            self.test_end(False, "Plus object not received correctly.")
        elif not os.path.exists(os.path.join("sf", "ParentClass", data[0])):
            self.test_end(False, "Parent not stored in local cache.")
        elif not os.path.exists(os.path.join("sf", "ChildClass",
                self.parent.child._id)):
            self.test_end(False, "Child not stored in local cache.")
        elif not os.path.exists(os.path.join("sf", "ChildClass",
                self.parent.children[1]._id)):
            self.test_end(False, "Children not stored in local cache.")

        self.parent_dict = decode_json(open(
            os.path.join("sf", "ParentClass", data[0])).read())
        self.child_dict = decode_json(open(
            os.path.join("sf", "ChildClass",
                         self.parent.child._id)).read())
        self.children_dict = decode_json(open(
            os.path.join("sf", "ChildClass",
                         self.parent.children[1]._id)).read())

        if self.parent_dict["id"] != "id_parent" or \
               self.parent_dict["parent_member"] != "parent" or \
               self.parent_dict["child"] != ["ChildClass",
                                             self.parent.child._id,
                                             self.parent.child._rev] or \
               self.parent_dict["children"][1] != \
                            ["ChildClass",
                             self.parent.children[1]._id,
                             self.parent.children[1]._rev]:
            self.test_end(False, "Parent not stored correctly.")
        elif self.child_dict["id"] != "id_child" or \
                 self.child_dict["child_member"] != "new_child_alone":
            self.test_end(False, "Child not stored correctly.")
        elif self.children_dict["id"] != "id_child" or \
                 self.children_dict["child_member"] != "new_child_1":
            self.test_end(False, "Children not stored correctly.")

    @rpc_method
    def on_parent_change(self, _id, plus):
        if plus != ["Test #", 8, "b"]:
            self.test_end(False, "Plus object not received correctly.")
        elif _id[:9] != "id_parent":
            self.test_end(False, "Wrong id received.")
        else:
            self.test_end(True, "Notification received correctly.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print sys.argv[0], "shard"
    else:
        TestSofa(int(sys.argv[1])).run()
