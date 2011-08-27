#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2011 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""A module providing storage facilities for entities.

It provides four EntityStore instances for the four main entity types.
Each EntityStore provides methods to modify the data and to receive
notifications about data updates.

Entities are represented as dicts, containing the entity's properties.

The EntityStores are persistent: they store the data on disk and load
it again when the program is restared.

"""


class InvalidKey(Exception):
    """Exception raised in case of invalid key."""
    pass


class InvalidData(Exception):
    """Exception raised in case of invalid data."""
    pass


class _Entity(object):
    """Base virtual class which all entities should extend.

    Provide some virtual methods that other classes should implement.

    """
    def __init__(self, data):
        """Initialize the entity.

        Do some generic init-stuff and then call the load() method, which
        should have been implemented by each entity.

        data (dict): the properties of the entity

        """
        self.load(data)

    def load(self, data):
        """Validate and load the data given as argument.

        Check if the dict given as argument provides all needed data, then
        update the entity's properties with that data.

        data (dict): the properties of the entity

        Raise InvalidData if not able to parse the data argument.

        """
        pass

    def dump(self):
        """Return a dict with all properties of the entity.

        If the returned dict is given to the load() method it should produce
        an entity identical to this one.

        return (dict): the properties of the entity

        """
        pass


class _Contest(_Entity):
    """The entity representing a contest.

    It consists of the following properties:
    - name (str): the human-readable name of the contest

    """
    def load(self, data):
        """Validate and load the data given as argument.

        See the description of load() in _Entity.

        """
        # validate
        try:
            assert type(data) is dict
            assert type(data['name']) is str or type(data['name']) is unicode
        except (KeyError, AssertionError):
            raise InvalidData
        # load
        self.name = data['name']

    def dump(self):
        """Return a dict with all properties of the entity.

        See the description of dump() in _Entity.

        """
        # dump
        return self.__dict__


class _Task(_Entity):
    """The entity representing a task.

    It consists of the following properties:
    - name (str): the human-readable name of the task
    - contest (str): the id of the contest the task belongs to
    - score (float): the maximum achievable score for the task
    - data_headers (list of str): a list with the descriptions of the extra
        fields that will be provided with each submission for the task

    """
    def load(self, data):
        """Validate and load the data given as argument.

        See the description of load() in _Entity.

        """
        # validate
        try:
            assert type(data) is dict
            assert type(data['name']) is str or type(data['name']) is unicode
            assert (type(data['contest']) is str or
                   type(data['contest']) is unicode)
            assert type(data['score']) is float
            assert type(data['data_headers']) is list
            for i in data['data_headers']:
                assert type(i) is str or type(i) is unicode
        except (KeyError, AssertionError):
            raise InvalidData
        # load
        self.name = data['name']
        self.contest = data['contest']
        self.score = data['score']
        self.data_headers = data['data_headers']

    def dump(self):
        """Return a dict with all properties of the entity.

        See the description of dump() in _Entity.

        """
        # dump
        return self.__dict__


class _Team(_Entity):
    """The entity representing a team.

    It consists of the following properties:
    - name (str): the human-readable name of the team

    """
    def load(self, data):
        """Validate and load the data given as argument.

        See the description of load() in _Entity.

        """
        # validate
        try:
            assert type(data) is dict
            assert type(data['name']) is str or type(data['name']) is unicode
        except (KeyError, AssertionError):
            raise InvalidData
        # load
        self.name = data['name']

    def dump(self):
        """Return a dict with all properties of the entity.

        See the description of dump() in _Entity.

        """
        # dump
        return self.__dict__


class _User(_Entity):
    """The entity representing a user.

    It consists of the following properties:
    - f_name (str): the first name of the user
    - l_name (str): the last name of the user
    - team (str): the id of the team the user belongs to

    """
    def load(self, data):
        """Validate and load the data given as argument.

        See the description of load() in _Entity.

        """
        # validate
        try:
            assert type(data) is dict
            assert (type(data['f_name']) is str or
                   type(data['f_name']) is unicode)
            assert (type(data['l_name']) is str or
                   type(data['l_name']) is unicode)
            assert type(data['team']) is str or type(data['team']) is unicode
        except (KeyError, AssertionError):
            raise InvalidData
        # load
        self.f_name = data['f_name']
        self.l_name = data['l_name']
        self.team = data['team']

    def dump(self):
        """Return a dict with all properties of the entity.

        See the description of dump() in _Entity.

        """
        # dump
        return self.__dict__


class EntityStore(object):
    """A store for entities.

    Provide methods to perform the CRUD operations (create, retrieve, update,
    delete) on a set of entities, accessed by their unique key.
    It's very similar to a dict, except that keys are strings, values are of
    a single type (defined at init-time) and it's possible to get notified
    when something changes by providing appropriate callbacks.

    """
    def __init__(self, entity):
        """Initialize an empty EntityStore.

        The entity definition given as argument will define what kind of
        entities will be stored. It cannot be changed.

        entity (class): the class definition of the entities that will
            be stored

        """
        assert issubclass(entity, _Entity)
        self._entity = entity
        self._store = dict()

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
        if not isinstance(key, str) or key in self._store:
            raise InvalidKey
        self._store[key] = self._entity(data)

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
        if not isinstance(key, str) or not key in self._store:
            raise InvalidKey
        self._store[key] = self._entity(data)

    def delete(self, key):
        """Delete an entity.

        Delete an existing entity from the store.

        key (str): the key of the entity that has to be deleted

        Raise InvalidKey if key isn't a str or if no entity with that key
        is present in the store.

        """
        if not isinstance(key, str) or not key in self._store:
            raise InvalidKey
        del self._store[key]

    def retrieve(self, key):
        """Retrieve an entity.

        Retrieve an existing entity from the store.

        key (str): the key of the entity that has to be retrieved

        Raise InvalidKey if key isn't a str or if no entity with that key
        is present in the store.

        """
        if not isinstance(key, str) or not key in self._store:
            raise InvalidKey
        return self._store[key]

contest_store = EntityStore(_Contest)
task_store = EntityStore(_Task)
team_store = EntityStore(_Team)
user_store = EntityStore(_User)
