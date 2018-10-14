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


class Submission(Entity):
    """The entity representing a submission.

    It consists of the following properties:
    - user (unicode): the key of the user who submitted
    - task (unicode): the key of the task of the submission
    - time (int): the time the submission has been submitted

    """
    def __init__(self):
        """Set the properties to some default values.

        """
        Entity.__init__(self)
        self.user = None
        self.task = None
        self.time = None

    @staticmethod
    def validate(data):
        """Validate the given dictionary.

        See if it contains a valid representation of this entity.

        """
        try:
            assert isinstance(data, dict), \
                "Not a dictionary"
            assert isinstance(data['user'], str), \
                "Field 'user' isn't a string"
            assert isinstance(data['task'], str), \
                "Field 'task' isn't a string"
            assert isinstance(data['time'], int), \
                "Field 'time' isn't an integer (unix timestamp)"
        except KeyError as exc:
            raise InvalidData("Field %s is missing" % exc)
        except AssertionError as exc:
            raise InvalidData(str(exc))

    def set(self, data):
        self.validate(data)
        self.user = data['user']
        self.task = data['task']
        self.time = data['time']

    def get(self):
        result = self.__dict__.copy()
        del result['key']
        del result['score']
        del result['token']
        del result['extra']
        return result

    def consistent(self, stores):
        return ("task" not in stores or self.task in stores["task"]) \
               and ("user" not in stores or self.user in stores["user"])
