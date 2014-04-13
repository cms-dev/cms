#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2011-2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

import io
import json
import logging
import os
import re

from gevent.lock import RLock

from cmsranking.Config import config
from cmsranking.Entity import Entity, InvalidKey, InvalidData


logger = logging.getLogger(__name__)


# Global shared lock for all Store instances.
LOCK = RLock()


class Store(object):
    """A store for entities.

    Provide methods to perform the CRUD operations (create, retrieve,
    update, delete) on a set of entities, accessed by their unique key.
    It's very similar to a dict, except that keys are strings, values
    are of a single type (defined at init-time) and it's possible to
    get notified when something changes by providing appropriate
    callbacks.

    """
    def __init__(self, entity, dir_name, depends=None):
        """Initialize an empty EntityStore.

        The entity definition given as argument will define what kind
        of entities will be stored. It cannot be changed.

        entity (type): the class definition of the entities that will
            be stored

        """
        if not issubclass(entity, Entity):
            raise ValueError("The 'entity' parameter "
                             "isn't a subclass of Entity")
        self._entity = entity
        self._path = os.path.join(config.lib_dir, dir_name)
        self._depends = depends if depends is not None else []
        self._store = dict()
        self._create_callbacks = list()
        self._update_callbacks = list()
        self._delete_callbacks = list()

        try:
            os.mkdir(self._path)
        except OSError:
            # it's ok: it means the directory already exists
            pass

        try:
            for name in os.listdir(self._path):
                # TODO check that the key is '[A-Za-z0-9_]+'
                if name[-5:] == '.json' and name[:-5] != '':
                    with io.open(os.path.join(self._path, name), 'rb') as rec:
                        item = self._entity()
                        item.set(json.load(rec, encoding='utf-8'))
                        item.key = name[:-5]
                        self._store[name[:-5]] = item
        except OSError:
            # the path isn't a directory or is inaccessible
            logger.error("Path is not a directory or is not accessible",
                         exc_info=True)
        except IOError:
            logger.error("I/O error occured", exc_info=True)
        except ValueError:
            logger.error("Invalid JSON", exc_info=False,
                         extra={'location': os.path.join(self._path, name)})
        except InvalidData as exc:
            logger.error(exc.message, exc_info=False,
                         extra={'location': os.path.join(self._path, name)})

    def add_create_callback(self, callback):
        """Add a callback to be called when entities are created.

        Callbacks can be any kind of callable objects. They must accept
        a single argument: the key of the entity.

        """
        self._create_callbacks.append(callback)

    def add_update_callback(self, callback):
        """Add a callback to be called when entities are updated.

        Callbacks can be any kind of callable objects. They must accept
        a single argument: the key of the entity.

        """
        self._update_callbacks.append(callback)

    def add_delete_callback(self, callback):
        """Add a callback to be called when entities are deleted.

        Callbacks can be any kind of callable objects. They must accept
        a single argument: the key of the entity.

        """
        self._delete_callbacks.append(callback)

    def create(self, key, data):
        """Create a new entity.

        Create a new entity with the given key and the given data.

        key (unicode): the key with which the entity will be later
            accessed
        data (dict): the properties of the entity

        raise (InvalidKey): if key isn't a unicode or if an entity
            with the same key is already present in the store.
        raise (InvalidData): if data cannot be parsed, if it's missing
            some properties or if properties are of the wrong type.

        """
        if not isinstance(key, unicode) or key in self._store:
            raise InvalidKey("Key already in store.")

        # create entity
        with LOCK:
            item = self._entity()
            item.set(data)
            if not item.consistent():
                raise InvalidData("Inconsistent data")
            item.key = key
            self._store[key] = item
            # notify callbacks
            for callback in self._create_callbacks:
                callback(key, item)
            # reflect changes on the persistent storage
            try:
                path = os.path.join(self._path, key + '.json')
                with io.open(path, 'wb') as rec:
                    json.dump(self._store[key].get(), rec, encoding='utf-8')
            except IOError:
                logger.error("I/O error occured while creating entity",
                             exc_info=True)

    def update(self, key, data):
        """Update an entity.

        Update an existing entity with the given key and the given
        data.

        key (unicode): the key of the entity that has to be updated
        data (dict): the new properties of the entity

        raise (InvalidKey): if key isn't a unicode or if no entity
            with that key is present in the store.
        raise (InvalidData): if data cannot be parsed, if it's missing
            some properties or if properties are of the wrong type.

        """
        if not isinstance(key, unicode) or key not in self._store:
            raise InvalidKey("Key not in store.")

        # update entity
        with LOCK:
            item = self._entity()
            item.set(data)
            if not item.consistent():
                raise InvalidData("Inconsistent data")
            item.key = key
            old_item = self._store[key]
            self._store[key] = item
            # notify callbacks
            for callback in self._update_callbacks:
                callback(key, old_item, item)
            # reflect changes on the persistent storage
            try:
                path = os.path.join(self._path, key + '.json')
                with io.open(path, 'wb') as rec:
                    json.dump(self._store[key].get(), rec, encoding='utf-8')
            except IOError:
                logger.error("I/O error occured while updating entity",
                             exc_info=True)

    def merge_list(self, data_dict):
        """Merge a list of entities.

        Take a dictionary of entites and, for each of them:
         - if it's not present in the store, create it
         - if it's present, update it

        data_dict (dict): the dictionary of entities

        raise (InvalidData) if data cannot be parsed, if an entity is
            missing some properties or if properties are of the wrong
            type.

        """
        with LOCK:
            if not isinstance(data_dict, dict):
                raise InvalidData("Not a dictionary")
            item_dict = dict()
            for key, value in data_dict.iteritems():
                try:
                    # FIXME We should allow keys to be arbitrary unicode
                    # strings, so this just needs to be a non-empty check.
                    if not re.match('[A-Za-z0-9_]+', key):
                        raise InvalidData("Invalid key")
                    item = self._entity()
                    item.set(value)
                    if not item.consistent():
                        raise InvalidData("Inconsistent data")
                    item.key = key
                    item_dict[key] = item
                except InvalidData as exc:
                    exc.message = "[entity %s] %s" % (key, exc)
                    exc.args = exc.message,
                    raise exc

            for key, value in item_dict.iteritems():
                is_new = key not in self._store
                old_value = self._store.get(key)
                # insert entity
                self._store[key] = value
                # notify callbacks
                if is_new:
                    for callback in self._create_callbacks:
                        callback(key, value)
                else:
                    for callback in self._update_callbacks:
                        callback(key, old_value, value)
                # reflect changes on the persistent storage
                try:
                    path = os.path.join(self._path, key + '.json')
                    with io.open(path, 'wb') as rec:
                        json.dump(value.get(), rec, encoding='utf-8')
                except IOError:
                    logger.error(
                        "I/O error occured while merging entity lists",
                        exc_info=True)

    def delete(self, key):
        """Delete an entity.

        Delete an existing entity from the store.

        key (unicode): the key of the entity that has to be deleted

        raise (InvalidKey): if key isn't a unicode or if no entity
            with that key is present in the store.

        """
        if not isinstance(key, unicode) or key not in self._store:
            raise InvalidKey("Key not in store.")

        with LOCK:
            # delete entity
            old_value = self._store[key]
            del self._store[key]
            # enforce consistency
            for depend in self._depends:
                for o_key, o_value in list(depend._store.iteritems()):
                    if not o_value.consistent():
                        depend.delete(o_key)
            # notify callbacks
            for callback in self._delete_callbacks:
                callback(key, old_value)
            # reflect changes on the persistent storage
            try:
                os.remove(os.path.join(self._path, key + '.json'))
            except OSError:
                logger.error("Unable to delete entity", exc_info=True)

    def delete_list(self):
        """Delete all entities.

        Delete all existing entities from the store.

        """
        with LOCK:
            # delete all entities
            for key in list(self._store.iterkeys()):
                self.delete(key)

    def retrieve(self, key):
        """Retrieve an entity.

        Retrieve an existing entity from the store.

        key (unicode): the key of the entity that has to be retrieved

        raise (InvalidKey): if key isn't a unicode or if no entity
            with that key is present in the store.

        """
        if not isinstance(key, unicode) or key not in self._store:
            raise InvalidKey("Key not in store.")

        # retrieve entity
        return self._store[key].get()

    def retrieve_list(self):
        """Retrieve a list of all entities."""
        result = dict()
        for key, value in self._store.iteritems():
            result[key] = value.get()
        return result

    def __contains__(self, key):
        return key in self._store
