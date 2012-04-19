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

import Team
import Submission


class User(Entity):
    """The entity representing a user.

    It consists of the following properties:
    - f_name (str): the first name of the user
    - l_name (str): the last name of the user
    - team (str): the id of the team the user belongs to

    """
    def __init__(self):
        """Set the properties to some default values.

        """
        Entity.__init__(self)
        self.f_name = None
        self.l_name = None
        self.team = None

    @staticmethod
    def validate(data):
        """Validate the given dictionary.

        See if it contains a valid representation of this entity.

        """
        try:
            assert type(data) is dict, \
                "Not a dictionary"
            assert type(data['f_name']) is unicode or \
                   type(data['f_name']) is str, \
                "Field 'f_name' isn't a string"
            assert type(data['l_name']) is unicode or \
                   type(data['l_name']) is str, \
                "Field 'l_name' isn't a string"
            assert data['team'] is None or \
                   type(data['team']) is unicode or \
                   type(data['team']) is str, \
                "Field 'team' isn't a string (or null)"
        except KeyError as field:
            raise InvalidData("Field %s is missing" % field)
        except AssertionError as message:
            raise InvalidData(str(message))

    def set(self, data):
        self.validate(data)
        self.f_name = data['f_name']
        self.l_name = data['l_name']
        self.team = data['team']

    def get(self):
        result = self.__dict__.copy()
        del result["key"]
        return result

    def load(self, data):
        self.validate(data)
        self.f_name = data['f_name']
        self.l_name = data['l_name']
        self.team = data['team']

    def dump(self):
        result = self.__dict__.copy()
        del result["key"]
        return result

    def consistent(self):
        return self.team is None or self.team in Team.store


store = Store(User, 'users', [Submission])
