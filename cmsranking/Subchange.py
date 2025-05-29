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


class Subchange(Entity):
    """The entity representing a change in the status of a submission.

    It consists of the following properties:
    - submission: the key of the affected submission
    - time: the time the change takes effect
    - score: optional, the new score
    - token: optional, the new token status
    - extra: optional, the new details

    """
    def __init__(self):
        """Set the properties to some default values.

        """
        Entity.__init__(self)
        self.submission: str = None
        self.time: int = None
        self.score: float | None = None
        self.token: bool | None = None
        self.extra: list[str] | None = None

    @staticmethod
    def validate(data):
        """Validate the given dictionary.

        See if it contains a valid representation of this entity.

        """
        try:
            assert isinstance(data, dict), \
                "Not a dictionary"
            assert isinstance(data['submission'], str), \
                "Field 'submission' isn't a string"
            assert isinstance(data['time'], int), \
                "Field 'time' isn't an integer (unix timestamp)"
            if 'score' in data:
                assert isinstance(data['score'], float), \
                    "Field 'score' isn't a float"
            if 'token' in data:
                assert isinstance(data['token'], bool), \
                    "Field 'token' isn't a boolean"
            if 'extra' in data:
                assert isinstance(data['extra'], list), \
                    "Field 'extra' isn't a list of strings"
                for i in data['extra']:
                    assert isinstance(i, str), \
                        "Field 'extra' isn't a list of strings"
        except KeyError as exc:
            raise InvalidData("Field %s is missing" % exc)
        except AssertionError as exc:
            raise InvalidData(str(exc))

    def set(self, data):
        self.validate(data)
        self.submission = data['submission']
        self.time = data['time']
        self.score = (data['score'] if 'score' in data else None)
        self.token = (data['token'] if 'token' in data else None)
        self.extra = (data['extra'] if 'extra' in data else None)

    def get(self):
        result = self.__dict__.copy()
        del result['key']
        for field in ['score', 'token', 'extra']:
            if result[field] is None:
                del result[field]
        return result

    def consistent(self, stores):
        return "submission" not in stores \
               or self.submission in stores["submission"]
