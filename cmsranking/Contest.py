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


class Contest(Entity):
    """The entity representing a contest.

    It consists of the following properties:
    - name (unicode): the human-readable name of the contest
    - begin (int): the unix timestamp at which the contest begins
    - end (int): the unix timestamp at which the contest ends
    - score_precision (int): how many decimal places to show in scores

    """
    def __init__(self):
        """Set the properties to some default values.

        """
        Entity.__init__(self)
        self.name = None
        self.begin = None
        self.end = None
        self.score_precision = None

    @staticmethod
    def validate(data):
        """Validate the given dictionary.

        See if it contains a valid representation of this entity.

        """
        try:
            assert isinstance(data, dict), \
                "Not a dictionary"
            assert isinstance(data['name'], str), \
                "Field 'name' isn't a string"
            assert isinstance(data['begin'], int), \
                "Field 'begin' isn't an integer"
            assert isinstance(data['end'], int), \
                "Field 'end' isn't an integer"
            assert data['begin'] <= data['end'], \
                "Field 'begin' is greater than 'end'"
            assert isinstance(data['score_precision'], int), \
                "Field 'score_precision' isn't an integer"
            assert data['score_precision'] >= 0, \
                "Field 'score_precision' is negative"
        except KeyError as exc:
            raise InvalidData("Field %s is missing" % exc)
        except AssertionError as exc:
            raise InvalidData(str(exc))

    def set(self, data):
        self.validate(data)
        self.name = data['name']
        self.begin = data['begin']
        self.end = data['end']
        self.score_precision = data['score_precision']

    def get(self):
        result = self.__dict__.copy()
        del result['key']
        return result
