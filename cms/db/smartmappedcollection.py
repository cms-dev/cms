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

import weakref

from sqlalchemy import event, util, __version__ as sa_version
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

    if sa_version.startswith("1."):
        event.listen(mapper, "after_configured", add_event_handlers)

    return prop


class SAEventWeakWrapperToMethod(object):
    """Forward SA events to a method of a weakly-referenced object.

    """
    def __init__(self, target, event_name, object_, method_name):
        """Add listener to given event, to forward to given method.

        Setup an SQLAlchemy listener for the given event on the given
        target. When an event is received it's forwarded verbatim to
        the given method of the given object, if the object still
        exists. When the object gets deleted, the listener is removed.

        As long as this wrapper is registered as an event listener
        SQLAlchemy keeps a (strong) reference to it and prevents it
        from being destroyed. Thus if the wrapper didn't store a weak
        reference to the wrapped object it would keep it alive as well,
        possibly causing a memory leak.

        target (object): an object on which one can listen for
            SQLAlchemy events.
        event_name (string): the name of an event on such object.
        object_ (object): an instance of a class that will receive
            these events.
        method_name (string): the name of the method of such class that
            will be called.

        """
        self.target = target
        self.event_name = event_name
        self.object = weakref.ref(object_, self._death_callback)
        self.method_name = method_name
        self.attached = True

        event.listen(self.target, self.event_name, self._event_callback)

    def detach(self):
        """Remove the SQLAlchemy listener."""
        if self.attached:
            event.remove(self.target, self.event_name, self._event_callback)
            self.attached = False

    def _event_callback(self, *args, **kwargs):
        """Called by SQLAlchemy to alert us of an event."""
        object_ = self.object()
        if object_ is not None:
            getattr(object_, self.method_name)(*args, **kwargs)

    def _death_callback(self, ref):
        """Called when the object we're forwarding to is deleted."""
        assert ref is self.object
        self.detach()


class SmartMappedCollection(MappedCollection):

    def __init__(self, column_name):
        # Whether the collection is currently being used for a parent's
        # relationship attribute or not.
        self.linked = False

        # Map the id() of values to their key. This is well defined
        # because we ensure uniqueness of values (as the key is a
        # function of the value: the attribute we're mapping from).
        # This speeds up key retrieval.
        self.inverse_map = dict()

        self.event_wrapper = None

        # Useful references, that will be obtained upon linking.
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

        parent_cls = type(adapter.owner_state.obj())
        parent_rel_name = adapter.attr.key
        parent_rel_prop = \
            class_mapper(parent_cls).get_property(parent_rel_name)
        self.child_cls = parent_rel_prop.mapper.class_
        self.child_rel_name = parent_rel_prop.back_populates
        self.child_rel_prop = \
            class_mapper(self.child_cls).get_property(self.child_key_name)

        self.event_wrapper = SAEventWeakWrapperToMethod(
            self.child_rel_prop, 'set', self, 'on_key_update')

    # Called when the object stops being used. We basically undo what
    # was done in on_dispose and restore a pristine state.
    def on_dispose(self):
        assert self.linked
        self.linked = False

        self.event_wrapper.detach()
        self.event_wrapper = None

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
    #   attribute set to the parent object;
    # - all elements of self.values() are distinct;
    # - for each (key, value) in self.items(), key is equal to the
    #   self.child_key_name attribute of value.

    # The general rule here is: don't ever assume anything about the
    # state of the child, neither about its relationship attribute
    # (i.e. who it considers its parent) nor on its key attribute.

    # This method is called when the key of a child object changes. In
    # such an event the binding in the dictionary has to change as well
    # (i.e. del d[old_key] and d[new_key] = value).
    def on_key_update(self, value, new_key, unused_old_key,
                      unused_sa_initiator=None):
        assert self.linked
        old_key = self.inverse_map.get(id(value), None)
        if old_key is not None and new_key != old_key:
            if dict.__contains__(self, new_key):
                other_value = dict.__getitem__(self, new_key)
                del self.inverse_map[id(other_value)]
                # We use the method of MappedCollection because we want
                # it to trigger all the necessary Alchemy machinery to
                # detach the child from the parent.
                MappedCollection.__delitem__(self, new_key)
            # We use the methods of dict directly because we want this
            # to be transparent to Alchemy: the child was and remains
            # bound, only its key changes, and Alchemy doesn't care
            # about this.
            self.inverse_map[id(value)] = new_key
            dict.__delitem__(self, old_key)
            dict.__setitem__(self, new_key, value)

    # This method is called when a binding to a new child is performed.
    # The only additional feature with respect to the superclass method
    # is that it enforces the key stored in the child to be equal to
    # the one that is being used to bind the child to the collection.
    @collection.internally_instrumented
    def __setitem__(self, new_key, value, _sa_initiator=None):
        # TODO We could check if the object's type is correct.
        assert self.linked
        # This is the only difference with the standard behavior.
        setattr(value, self.child_key_name, new_key)
        self.inverse_map[id(value)] = new_key
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
