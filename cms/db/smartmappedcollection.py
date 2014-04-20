#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

from sqlalchemy import util
from sqlalchemy import event
from sqlalchemy.orm import class_mapper
from sqlalchemy.orm.collections import \
    collection, collection_adapter, MappedCollection, \
    __set as sa_set, __del as sa_del


# XXX When dropping support for SQLAlchemy pre-0.7.6, remove these two
# lines.
from sqlalchemy.orm.collections import _instrument_class
_instrument_class(MappedCollection)


# XXX When SQLAlchemy will support removal of attribute events, remove
# the following class and global variable:

class _EventManager(object):
    def __init__(self):
        self.handlers = dict()

    def listen(self, cls, prp, handler):
        if (cls, prp) not in self.handlers:
            self.handlers[(cls, prp)] = weakref.WeakSet()
            event.listen(class_mapper(cls)._props[prp],
                         'set', self.make_callback(cls, prp))

        self.handlers[(cls, prp)].add(handler)

    # No need to enable handlers to be removed: they'll automatically
    # vanish when they are garbage collected, as they are weakrefs.

    def make_callback(self, cls, prp):
        def callback(target, new_key, old_key, _sa_initiator):
            for handler in self.handlers[(cls, prp)]:
                handler._on_column_change(target, new_key, old_key,
                                          _sa_initiator)
        return callback


_event_manager = _EventManager()


class SmartMappedCollection(MappedCollection):

    def __init__(self, column):
        self._column = column

        self._linked = False

        self._parent_rel = None
        self._parent_obj = None
        self._parent_cls = None
        self._child_rel = None
        self._child_cls = None

    def __eq__(self, other):
        return self is other

    def __hash__(self):
        return hash(id(self))

    # XXX When dropping support for SQLAlchemy pre-0.8, rename this
    # decorator to 'collection.linker'.
    @collection.link
    def _link(self, adapter):
        assert adapter == collection_adapter(self)

        if adapter is not None:
            # LINK
            assert not self._linked
            self._linked = True

            assert self is adapter.data

            self._parent_rel = adapter.attr.key
            self._parent_obj = adapter.owner_state.obj()
            self._parent_cls = type(self._parent_obj)
            parent_rel_prop = \
                class_mapper(self._parent_cls)._props[self._parent_rel]
            self._child_rel = parent_rel_prop.back_populates
            self._child_cls = parent_rel_prop.mapper.class_
            # This is at the moment not used, but may be in the future.
            # child_rel_prop = \
            #     class_mapper(self._child_cls)._props[self._child_rel]

            # XXX When SQLAlchemy will support removal of attribute
            # events, use the following code:
            #event.listen(class_mapper(self._child_cls)._props[self._column],
            #             'set', self._on_column_change)
            # In the meanwhile we have to use this:
            _event_manager.listen(self._child_cls, self._column, self)

        else:
            # UNLINK
            assert self._linked
            self._linked = False

            # XXX When SQLAlchemy will support removal of attribute
            # events, use the following code:
            #event.remove(class_mapper(self._child_cls)._props[self._column],
            #             'set', self._on_column_change)
            # In the meanwhile we just rely on EventManager + weakrefs.

            self._parent_rel = None
            self._parent_obj = None
            self._parent_cls = None
            self._child_rel = None
            self._child_cls = None

    # XXX When dropping support for SQLAlchemy pre-0.8, remove this line.
    _sa_on_link = _link

    # The following two methods do all the hard work. Their mission is
    # to keep everything consistent, that is to get from a (hopefully
    # consistent) initial state to a consistent final state after
    # having dome something useful (i.e. what they were written for).
    # This is what we consider a consistent state:
    # - self.values() is equal to all and only those objects of the
    #   self._child_cls class that have the self._child_rel attribute
    #   set to self._parent_obj;
    # - all elements of self.values() are distinct (that is, this is an
    #   invertible mapping);
    # - for each (key, value) in self.items(), key is equal to the
    #   self._column attribute of value.

    # This method is called before the attribute is really changed, and
    # trying to change it again from inside this method will cause an
    # infinte recursion loop. Don't do that! This also means that the
    # method does actually leave the collection in an inconsistent
    # state, but SQLAlchemy will fix that immediately after.
    def _on_column_change(self, value, new_key, old_key, _sa_initiator):
        assert self._linked
        if getattr(value, self._child_rel) is self._parent_obj:
            # Get the old_key (the parameter may not be reliable) and
            # do some consistency checks.
            assert value in self.itervalues()
            old_key = list(k for k, v in self.iteritems() if v is value)
            assert len(old_key) == 1
            old_key = old_key[0]
            assert old_key == getattr(value, self._column)

            # If necessary, move this object (and remove any old object
            # with this key).
            if new_key != old_key:
                dict.__delitem__(self, old_key)
                if new_key in self:
                    sa_del(self,
                           dict.__getitem__(self, new_key),
                           _sa_initiator)
                    dict.__delitem__(self, new_key)
                dict.__setitem__(self, new_key, value)

    # When this method gets called, the child object may think it's
    # already bound to the collection (i.e. its self._child_rel is set
    # to self._parent_obj) but it actually isn't (i.e. it's not in
    # self.values()). This method has to fix that.
    @collection.internally_instrumented
    def __setitem__(self, new_key, value, _sa_initiator=None):
        # TODO We could check if the object's type is correct.
        assert self._linked
        if value in self.itervalues():
            # Just some consistency checks, for extra safety!
            assert getattr(value, self._child_rel) is self._parent_obj
            old_key = list(k for k, v in self.iteritems() if v is value)
            assert len(old_key) == 1
            old_key = old_key[0]
            assert old_key == getattr(value, self._column)

            # If needed, we make SQLAlchemy call _on_column_changed to
            # do the rest of the job (and repeat the above checks).
            if new_key != getattr(value, self._column):
                setattr(value, self._column, new_key)
        else:
            # We change the attribute before adding it to the collection
            # to prevent the (unavoidable) call to _on_column_change
            # from doing any damage.
            if new_key != getattr(value, self._column):
                setattr(value, self._column, new_key)

            # Remove any old object with this key and add this instead.
            if new_key in self:
                sa_del(self, dict.__getitem__(self, new_key), _sa_initiator)
                dict.__delitem__(self, new_key)
            value = sa_set(self, value, _sa_initiator)
            dict.__setitem__(self, new_key, value)

    def keyfunc(self, value):
        return getattr(value, self._column)

    @collection.converter
    def _convert(self, collection):
        # TODO We could check if the objects' type is correct.
        type_ = util.duck_type_collection(collection)
        if type_ is dict:
            for key, value in util.dictlike_iteritems(collection):
                if key != self.keyfunc(value):
                    raise TypeError(
                        "Found incompatible key '%r' for value '%r'" %
                        (key, value))
                yield value
        elif type_ in (list, set):
            for value in collection:
                yield value
        else:
            raise TypeError("Object '%r' is not dict-like nor iterable" %
                            collection)

    # XXX When dropping support for SQLAlchemy pre-0.8, remove this.
    _sa_converter = _convert

    def __iadd__(self, collection):
        for value in self._convert(collection):
            self.set(value)
        return self


def smart_mapped_collection(column):
    return lambda: SmartMappedCollection(column)
