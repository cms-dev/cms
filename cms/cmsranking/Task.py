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

from cmsranking.Entity import Entity, InvalidData
from cmsranking.Store import Store


class Task(Entity):
    """The entity representing a task.

    It consists of the following properties:
    - name (str): the human-readable name of the task
    - contest (str): the id of the contest the task belongs to
    - score (float): the maximum achievable score for the task
    - data_headers (list of str): a list with the descriptions of the extra
        fields that will be provided with each submission for the task
    - order (int): the order of the tasks inside of the contest

    """
    def __init__(self):
        """Set the properties to some default values.

        """
        Entity.__init__(self)
        self.name = None
        self.contest = None
        self.score = None
        self.extra_headers = None
        self.order = None

    @staticmethod
    def validate(data):
        """Validate the given dictionary.

        See if it contains a valid representation of this entity.

        """
        try:
            assert type(data) is dict, \
                "Not a dictionary"
            assert type(data['name']) is unicode, \
                "Field 'name' isn't a string"
            assert type(data['contest']) is unicode, \
                "Field 'contest' isn't a string"
            assert type(data['score']) is float, \
                "Field 'score' isn't a float"
            assert type(data['extra_headers']) is list, \
                "Field 'extra_headers' isn't a list of strings"
            for i in data['extra_headers']:
                assert type(i) is unicode, \
                    "Field 'extra_headers' isn't a list of strings"
            assert type(data['order']) is int, \
                "Field 'order' isn't an integer"
            assert data['order'] >= 0, \
                "Field 'order' is negative"
        except KeyError as field:
            raise InvalidData("Field %s is missing" % field)
        except AssertionError as message:
            raise InvalidData(message)

    def set(self, data):
        self.validate(data)
        self.name = data['name']
        self.contest = data['contest']
        self.score = data['score']
        self.extra_headers = data['extra_headers']
        self.order = data['order']

    def get(self):
        return self.__dict__

    def load(self, data):
        self.validate(data)
        self.name = data['name']
        self.contest = data['contest']
        self.score = data['score']
        self.extra_headers = data['extra_headers']
        self.order = data['order']

    def dump(self):
        return self.__dict__


store = Store(Task, 'tasks')
