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

import User


class Team(Entity):
    """The entity representing a team.

    It consists of the following properties:
    - name (str): the human-readable name of the team

    """
    def __init__(self):
        """Set the properties to some default values.

        """
        Entity.__init__(self)
        self.name = None

    @staticmethod
    def validate(data):
        """Validate the given dictionary.

        See if it contains a valid representation of this entity.

        """
        try:
            assert type(data) is dict, \
                "Not a dictionary"
            assert type(data['name']) is unicode or \
                   type(data['name']) is str, \
                "Field 'name' isn't a string"
        except KeyError as field:
            raise InvalidData("Field %s is missing" % field)
        except AssertionError as message:
            raise InvalidData(str(message))

    def set(self, data):
        self.validate(data)
        self.name = data['name']

    def get(self):
        result = self.__dict__.copy()
        del result["key"]
        return result

    def load(self, data):
        self.validate(data)
        self.name = data['name']

    def dump(self):
        result = self.__dict__.copy()
        del result["key"]
        return result


store = Store(Team, 'teams', [User])
