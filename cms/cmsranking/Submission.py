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

from Entity import Entity, InvalidData
from Store import Store


class Submission(Entity):
    """The entity representing a submission.

    It consists of the following properties:
    - user (str): the key of the user who submitted
    - task (str): the key of the task of the submission
    - time (int): the time the submission has been submitted

    """
    @staticmethod
    def validate(data):
        try:
            assert type(data) is dict, \
                "Not a dictionary"
            assert type(data['user']) is unicode, \
                "Field 'user' isn't a string"
            assert type(data['task']) is unicode, \
                "Field 'task' isn't a string"
            assert type(data['time']) is int, \
                "Field 'time' isn't an integer (unix timestamp)"
        except KeyError as field:
            raise InvalidData("Field %s is missing" % field)
        except AssertionError as message:
            raise InvalidData(message)

    def set(self, data):
        self.validate(data)
        self.user = data['user']
        self.task = data['task']
        self.time = data['time']

    def get(self):
        return self.__dict__

    def load(self, data):
        self.validate(data)
        self.user = data['user']
        self.task = data['task']
        self.time = data['time']

    def dump(self):
        return self.__dict__


store = Store(Submission, 'submissions')
