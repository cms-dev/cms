#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2013-2015 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from sqlalchemy import util
from sqlalchemy import event
from sqlalchemy.orm import class_mapper, mapper
from sqlalchemy.orm.collections import \
    collection, collection_adapter, MappedCollection


# Workaround to make SmartMappedCollection work with SQLAlchemy 1.0.
# Until v0.9 detection of a new collection being created and (un)bound
# to a relationship was done by the @collection.linker decorator on a
# method. Starting with v1.0 it's done by registering two events on the
# relationship property.
def smc_sa10_workaround(prop):
    def add_event_handlers():
        # We have the relationship from the child to the parent but we
        # need the inverse. This is only defined after the mapper has
        # been configured. That's why this is inside a listener for the
        # "after_configured" event.
        parent_prop = getattr(prop.mapper.class_, prop.back_populates)

        def cb_on_init(target, coll, adapter):
            coll.on_init()
        event.listen(parent_prop, "init_collection", cb_on_init)

        def cb_on_dispose(target, coll, adapter):
            coll.on_dispose()
        event.listen(parent_prop, "dispose_collection", cb_on_dispose)

    event.listen(mapper, "after_configured", add_event_handlers)

    return prop


class SmartMappedCollection(MappedCollection):

    def __init__(self, column_name):
        # Whether the collection is currently being used for a parent's
        # relationship attribute or not.
        self.linked = False

        # Useful references, that will be obtained upon linking.
        self.parent_obj = None
        self.child_cls = None
        self.child_rel_name = None
        self.child_rel_prop = None
        self.child_key_name = column_name

        MappedCollection.__init__(self, lambda x: getattr(x, column_name))

    def __eq__(self, other):
        return self is other

    def __hash__(self):
        return hash(id(self))

    # Called when the object starts being used as a collection for a
    # parent's relationship attribute. We just get some data about the
    # relationship and the classes involved therein, and register an
    # event to detect when the key of a child gets updated.
    def on_init(self):
        assert not self.linked
        self.linked = True

        adapter = collection_adapter(self)

        self.parent_obj = adapter.owner_state.obj()
        parent_cls = type(self.parent_obj)
        parent_rel_name = adapter.attr.key
        parent_rel_prop = \
            class_mapper(parent_cls).get_property(parent_rel_name)
        self.child_cls = parent_rel_prop.mapper.class_
        self.child_rel_name = parent_rel_prop.back_populates
        self.child_rel_prop = \
            class_mapper(self.child_cls).get_property(self.child_key_name)

        event.listen(self.child_rel_prop, 'set', self.on_key_update)

    # Called when the object stops being used. We basically undo what
    # was done in on_dispose and restore a pristine state.
    def on_dispose(self):
        assert self.linked
        self.linked = False

        event.remove(self.child_rel_prop, 'set', self.on_key_update)

        self.parent_obj = None
        self.child_cls = None
        self.child_rel_name = None
        self.child_rel_prop = None

    # This is the old pre-1.0 interface for detecting when the data
    # structure was linked to or unlinked from an attribute.
    @collection.linker
    def _link(self, adapter):
        assert adapter == collection_adapter(self)

        if adapter is not None:
            # init_collection
            self.on_init()
        else:
            # dispose_collection
            self.on_dispose()

    # The following two methods have to maintain consistency, i.e.:
    # - self.values() is equal to all and only those objects of the
    #   self.child_cls class that have the self.child_rel_name
    #   attribute set to self.parent_obj;
    # - all elements of self.values() are distinct;
    # - for each (key, value) in self.items(), key is equal to the
    #   self.child_key_name attribute of value.

    # This method is called when the key of a child object changes. In
    # such an event the binding in the dictionary has to change as well
    # (i.e. del d[old_key] and d[new_key] = value). Actually, we simply
    # delegate this task to the method just after this one.
    def on_key_update(self, value, new_key, old_key, _):
        assert self.linked
        if getattr(value, self.child_rel_name) is self.parent_obj \
                and new_key != old_key:
            self.__setitem__(new_key, value)

    # This method is called when a binding to a new child is performed.
    # As the child could come from anywhere we first detach it from its
    # former parent (if any; note that this could also be ourselves).
    # Then, as we want to bind it to new_key, we update its key to be
    # that value. Finally we add it to the dictionary: this operation,
    # implicitly, removes the old binding of the new key (if any).
    @collection.internally_instrumented
    def __setitem__(self, new_key, value, _sa_initiator=None):
        # TODO We could check if the object's type is correct.
        assert self.linked
        setattr(value, self.child_rel_name, None)
        setattr(value, self.child_key_name, new_key)
        MappedCollection.__setitem__(self, new_key, value, _sa_initiator)

    # This method converts a data structure into an iterable of values.
    # It allows us to use the syntactic sugar "foo.children = bar"
    # (where bar is a dict, a list, ...) because it gets translated to
    # for v in converter(bar): foo.children.set(v)
    @collection.converter
    def _convert(self, coll):
        # TODO We could check if the objects' type is correct.
        type_ = util.duck_type_collection(coll)
        if type_ is dict:
            for key, value in util.dictlike_iteritems(coll):
                if key != self.keyfunc(value):
                    raise TypeError(
                        "Found incompatible key '%r' for value '%r'" %
                        (key, value))
                yield value
        elif type_ in (list, set):
            for value in coll:
                yield value
        else:
            raise TypeError("Object '%r' is not dict-like nor iterable" % coll)

    # This extends the above syntactic sugar to "foo.children += bar".
    def __iadd__(self, coll):
        for value in self._convert(coll):
            self.set(value)
        return self


def smart_mapped_collection(column):
    return lambda: SmartMappedCollection(column)
