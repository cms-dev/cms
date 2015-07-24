#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""Tests for SmartMappedCollection container.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import unittest

from sqlalchemy.schema import Column, ForeignKey, UniqueConstraint
from sqlalchemy.types import Integer, Unicode
from sqlalchemy.orm import backref, relationship
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.ext.declarative import declarative_base

from cms.db.smartmappedcollection import \
    smart_mapped_collection, smc_sa10_workaround


class TestSmartMappedCollection(unittest.TestCase):

    def setUp(self):
        self.sa_base = declarative_base()

        class FooParent(self.sa_base):
            __tablename__ = "parents"
            id = Column(
                Integer,
                primary_key=True)

        class FooChild(self.sa_base):
            __tablename__ = "children"
            __table_args__ = (
                UniqueConstraint("parent_id", "key"),
            )
            id = Column(
                Integer,
                primary_key=True)
            parent_id = Column(
                Integer,
                ForeignKey(FooParent.id,
                           onupdate="CASCADE", ondelete="CASCADE"),
                nullable=False,
                index=True)
            parent = smc_sa10_workaround(relationship(
                FooParent,
                backref=backref(
                    "children",
                    # collection_class=attribute_mapped_collection("key"),
                    collection_class=smart_mapped_collection("key"),
                    cascade="all, delete-orphan",
                    passive_deletes=True)))
            key = Column(
                Unicode,
                nullable=False)
            value = Column(
                Unicode,
                nullable=False)

        self.sa_parent = FooParent
        self.sa_child = FooChild

        self.parent = self.sa_parent()
        self.child = self.sa_child()
        self.child.key = "a"
        self.child.value = "1"

    def assertDoesNotBelong(self, key):
        """Verify that self.child is not bound to self.parent (but that
        it still has the given key).

        """
        self.assertIsNone(self.child.parent)
        self.assertDictEqual(self.parent.children, dict())
        self.assertEqual(self.child.key, key)

    def assertBelongs(self, key):
        """Verify that self.child is bount to self.parent with the
        given key.

        """
        self.assertIs(self.child.parent, self.parent)
        self.assertDictEqual(self.parent.children, {key: self.child})
        self.assertEqual(self.child.key, key)

    def test_bind_from_child(self):
        """Verify that `child.parent = parent` binds and `child.parent
        = None` unbinds.

        """
        self.assertDoesNotBelong("a")
        self.child.parent = self.parent
        self.assertBelongs("a")
        self.child.parent = None
        self.assertDoesNotBelong("a")

    def test_bind_from_parent1(self):
        """Verify that `parent.children = [child]` binds and
        `parent.children = []` unbinds.

        """
        self.assertDoesNotBelong("a")
        self.parent.children = [self.child]
        self.assertBelongs("a")
        self.parent.children = []
        self.assertDoesNotBelong("a")

    def test_bind_from_parent1b(self):
        """Verify that `parent.children += [child]` binds.

        """
        self.assertDoesNotBelong("a")
        self.parent.children += [self.child]
        self.assertBelongs("a")

    def test_bind_from_parent2(self):
        """Verify that `parent.children = {'a': child}` binds and
        `parent.children = dict()` unbinds.

        """
        self.assertDoesNotBelong("a")
        self.parent.children = {"a": self.child}
        self.assertBelongs("a")
        self.parent.children = dict()
        self.assertDoesNotBelong("a")

    def test_bind_from_parent2b(self):
        """Verify that `parent.children += {'a': child}` binds.

        """
        self.assertDoesNotBelong("a")
        self.parent.children += {"a": self.child}
        self.assertBelongs("a")

    def test_bind_from_parent3(self):
        """Verify that `parent.children['a'] = child` binds and `del
        parent.children['a']` unbinds.

        """
        self.assertDoesNotBelong("a")
        self.parent.children["a"] = self.child
        self.assertBelongs("a")
        del self.parent.children["a"]
        self.assertDoesNotBelong("a")

    def test_bind_from_parent4(self):
        """Verify that `parent.children.set(child)` binds and
        `parent.children.remove(child)` unbinds (SQLAlchemy-specific).

        """
        self.assertDoesNotBelong("a")
        self.parent.children.set(self.child)
        self.assertBelongs("a")
        self.parent.children.remove(self.child)
        self.assertDoesNotBelong("a")

    # TODO Maybe also verify that MappedCollection.update, .setdefault,
    # .pop, .popitem and .clear continue to work as documented.

    def test_adding_changes_key(self):
        """Verify that after `parent.children['b'] = child` child.key
        has been set to 'b'.

        """
        # Premise: child unbound (with key 'a').
        self.assertDoesNotBelong("a")
        # Operation: parent.children['b'] = child.
        self.parent.children["b"] = self.child
        # Result: child bound, with key 'b'.
        self.assertBelongs("b")

    def test_readding_moves_and_changes_key(self):
        """Verify that after `parent.children['b'] = child` child's
        previous binding has been removed and its key has been set to
        'b'.

        """
        # Premise: child bound, with key 'a'.
        self.assertDoesNotBelong("a")
        self.child.parent = self.parent
        self.assertBelongs("a")
        # Operation: parent.childen['b'] = child.
        self.parent.children["b"] = self.child
        # Result: child bound, with key 'b'.
        self.assertBelongs("b")

    def test_adding_releases_old_binding(self):
        """Verify that after `parent.children['a'] = child2` the child
        that was previously bound to 'a' has been unbound.

        """
        # Premise: child bound, with key 'a'; child2 bound, with key 'b'.
        self.assertDoesNotBelong("a")
        self.child.parent = self.parent
        self.assertBelongs("a")
        child2 = self.sa_child()
        child2.key = "b"
        child2.value = "2"
        self.assertIs(self.child.parent, self.parent)
        self.assertIsNone(child2.parent)
        self.assertDictEqual(self.parent.children, {"a": self.child})
        self.assertEqual(self.child.key, "a")
        self.assertEqual(child2.key, "b")
        # Operation: parent.children['a'] = child2.
        self.parent.children["a"] = child2
        # Result: child unbound (with key 'a'); child2 bound, with key 'a'.
        self.assertIsNone(self.child.parent)
        self.assertIs(child2.parent, self.parent)
        self.assertDictEqual(self.parent.children, {"a": child2})
        self.assertEqual(self.child.key, "a")
        self.assertEqual(child2.key, "a")

    def test_changing_key_moves(self):
        """Verify that after `child.key = 'b'` child is now bound to
        'b' in parent.children (and nothing is bound to 'a').

        """
        # Premise: child bound, with key 'a'.
        self.assertDoesNotBelong("a")
        self.child.parent = self.parent
        self.assertBelongs("a")
        # Operation: child.key = 'b'.
        self.child.key = "b"
        # Result: child bound, with key 'b'.
        self.assertBelongs("b")

    def test_changing_key_moves_and_releases_old_binding(self):
        """Verify that after `child2.key = 'a'` child2 is now bound to
        'a' in parent.children and the child that was previously bound
        to 'a' has been unbound.

        """
        # Premise: child bound, with key 'a'; child2 bound, with key 'b'.
        self.assertDoesNotBelong("a")
        self.child.parent = self.parent
        self.assertBelongs("a")
        child2 = self.sa_child()
        child2.key = "b"
        child2.value = "2"
        child2.parent = self.parent
        self.assertIs(self.child.parent, self.parent)
        self.assertIs(child2.parent, self.parent)
        self.assertDictEqual(self.parent.children,
                             {"a": self.child, "b": child2})
        self.assertEqual(self.child.key, "a")
        self.assertEqual(child2.key, "b")
        # Operation: child2.key = 'a'.
        child2.key = "a"
        # Result: child unbound (with key 'a'); child2 bound, with key 'a'.
        self.assertIsNone(self.child.parent)
        self.assertIs(child2.parent, self.parent)
        self.assertDictEqual(self.parent.children, {"a": child2})
        self.assertEqual(self.child.key, "a")
        self.assertEqual(child2.key, "a")


if __name__ == "__main__":
    unittest.main()
