#!/usr/bin/env python3

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

from cmsranking.Entity import Entity, InvalidData


class User(Entity):
    """The entity representing a user.

    It consists of the following properties:
    - f_name (unicode): the first name of the user
    - l_name (unicode): the last name of the user
    - team (unicode): the id of the team the user belongs to

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
            assert isinstance(data, dict), \
                "Not a dictionary"
            assert isinstance(data['f_name'], str), \
                "Field 'f_name' isn't a string"
            assert isinstance(data['l_name'], str), \
                "Field 'l_name' isn't a string"
            assert data['team'] is None or \
                isinstance(data['team'], str), \
                "Field 'team' isn't a string (or null)"
        except KeyError as exc:
            raise InvalidData("Field %s is missing" % exc)
        except AssertionError as exc:
            raise InvalidData(str(exc))

    def set(self, data):
        self.validate(data)
        self.f_name = data['f_name']
        self.l_name = data['l_name']
        self.team = data['team']

    def get(self):
        result = self.__dict__.copy()
        del result['key']
        return result

    def consistent(self, stores):
        return self.team is None or "team" not in stores \
               or self.team in stores["team"]
