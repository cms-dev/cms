#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2011-2012 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

from Config import config
from Logger import logger

from Entity import Entity, InvalidKey, InvalidData

import json
import os


class Store(object):
    """A store for entities.

    Provide methods to perform the CRUD operations (create, retrieve, update,
    delete) on a set of entities, accessed by their unique key.
    It's very similar to a dict, except that keys are strings, values are of
    a single type (defined at init-time) and it's possible to get notified
    when something changes by providing appropriate callbacks.

    """
    def __init__(self, entity, dir_name):
        """Initialize an empty EntityStore.

        The entity definition given as argument will define what kind of
        entities will be stored. It cannot be changed.

        entity (class): the class definition of the entities that will
            be stored

        """
        if not issubclass(entity, Entity):
            raise ValueError("The 'entity' parameter "
                             "isn't a subclass of Entity")
        self._entity = entity
        self._path = os.path.join(config.lib_dir, dir_name)
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
                if name[-5:] == '.json' and name[:-5] != '':
                    with open(os.path.join(self._path, name), 'r') as f:
                        data = f.read()
                        item = self._entity()
                        item.load(json.loads(data))
                        item.key = name[:-5]
                        self._store[name[:-5]] = item
        except OSError:
            # the path isn't a directory or is inaccessible
            logger.error("OSError occured", exc_info=True)
        except IOError:
            logger.error("IOError occured", exc_info=True)
        except ValueError:
            logger.error("Invalid JSON\n" + os.path.join(self._path, name),
                extra={'request_body': data})
        except InvalidData, exc:
            logger.error(str(exc) + "\n" + os.path.join(self._path, name),
                extra={'request_body': data})

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

        key (str): the key with which the entity will be later accessed
        data (dict): the properties of the entity

        Raise InvalidKey if key isn't a str or if an entity with the same
        key is already present in the store.
        Raise InvalidData if data cannot be parsed, if it's missing some
        properties or if properties are of the wrong type.

        """
        # verify key
        if not isinstance(key, unicode) or key in self._store:
            raise InvalidKey
        # create entity
        try:
            item = self._entity()
            item.set(json.loads(data))
            item.key = key
            self._store[key] = item
        except ValueError:
            raise InvalidData('Invalid JSON')
        # notify callbacks
        for callback in self._create_callbacks:
            callback(key)
        # reflect changes on the persistent storage
        try:
            with open(os.path.join(self._path, key + '.json'), 'w') as f:
                f.write(json.dumps(self._store[key].dump()))
        except IOError:
            logger.error("IOError occured", exc_info=True)

    def update(self, key, data):
        """Update an entity.

        Update an existing entity with the given key and the given data.

        key (str): the key of the entity that has to be updated
        data (dict): the new properties of the entity

        Raise InvalidKey if key isn't a str or if no entity with that key
        is present in the store.
        Raise InvalidData if data cannot be parsed, if it's missing some
        properties or if properties are of the wrong type.

        """
        # verify key
        if not isinstance(key, unicode) or key not in self._store:
            raise InvalidKey
        # update entity
        try:
            item = self._entity()
            item.set(json.loads(data))
            item.key = key
            self._store[key] = item
        except ValueError:
            raise InvalidData('Invalid JSON')
        # notify callbacks
        for callback in self._update_callbacks:
            callback(key)
        # reflect changes on the persistent storage
        try:
            with open(os.path.join(self._path, key + '.json'), 'w') as f:
                f.write(json.dumps(self._store[key].dump()))
        except IOError:
            logger.error("IOError occured", exc_info=True)

    def delete(self, key):
        """Delete an entity.

        Delete an existing entity from the store.

        key (str): the key of the entity that has to be deleted

        Raise InvalidKey if key isn't a str or if no entity with that key
        is present in the store.

        """
        # verify key
        if not isinstance(key, unicode) or key not in self._store:
            raise InvalidKey
        # delete entity
        del self._store[key]
        # notify callbacks
        for callback in self._delete_callbacks:
            callback(key)
        # reflect changes on the persistent storage
        try:
            os.remove(os.path.join(self._path, key + '.json'))
        except OSError:
            logger.error("OSError occured", exc_info=True)

    def retrieve(self, key):
        """Retrieve an entity.

        Retrieve an existing entity from the store.

        key (str): the key of the entity that has to be retrieved

        Raise InvalidKey if key isn't a str or if no entity with that key
        is present in the store.

        """
        # verify key
        if not isinstance(key, unicode) or key not in self._store:
            raise InvalidKey
        # retrieve entity
        return json.dumps(self._store[key].get())

    def list(self):
        """List all entities."""
        result = dict()
        for key, value in self._store.iteritems():
            result[key] = value.get()
        return json.dumps(result)

    def __contains__(self, key):
        return key in self._store
