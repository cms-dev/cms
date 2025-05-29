#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2011-2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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


class Task(Entity):
    """The entity representing a task.

    It consists of the following properties:
    - name: the human-readable name of the task
    - short_name: a shorter name for the task, usually a
        code-name
    - contest: the id of the contest the task belongs to
    - max_score: the maximum achievable score for the task
    - score_precision: how many decimal places to show in scores
    - extra_headers: a list with the descriptions of the
        extra fields that will be provided with each submission for the
        task
    - order: the order of the tasks inside of the contest
    - score_mode: TODO why no docstring?

    """
    def __init__(self):
        """Set the properties to some default values.

        """
        Entity.__init__(self)
        self.name: str = None
        self.short_name: str = None
        self.contest: str = None
        self.max_score: float = None
        self.score_precision: int # TODO why is this not set here?
        self.extra_headers: list[str] = None
        self.order: int = None
        self.score_mode: str = None

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
            assert isinstance(data['short_name'], str), \
                "Field 'short_name' isn't a string"
            assert isinstance(data['contest'], str), \
                "Field 'contest' isn't a string"
            assert isinstance(data['max_score'], float), \
                "Field 'max_score' isn't a float"
            assert isinstance(data['score_precision'], int), \
                "Field 'score_precision' isn't an integer"
            assert data['score_precision'] >= 0, \
                "Field 'score_precision' is negative"
            assert isinstance(data['extra_headers'], list), \
                "Field 'extra_headers' isn't a list of strings"
            assert isinstance(data['score_mode'], str), \
                "Field 'score_mode' isn't a string"
            for i in data['extra_headers']:
                assert isinstance(i, str), \
                    "Field 'extra_headers' isn't a list of strings"
            assert isinstance(data['order'], int), \
                "Field 'order' isn't an integer"
        except KeyError as exc:
            raise InvalidData("Field %s is missing" % exc)
        except AssertionError as exc:
            raise InvalidData(str(exc))

    def set(self, data):
        self.validate(data)
        self.name = data['name']
        self.short_name = data['short_name']
        self.contest = data['contest']
        self.max_score = data['max_score']
        self.score_precision = data['score_precision']
        self.extra_headers = data['extra_headers']
        self.order = data['order']
        self.score_mode = data['score_mode']

    def get(self):
        result = self.__dict__.copy()
        del result['key']
        return result

    def consistent(self, stores):
        return "contest" not in stores or self.contest in stores["contest"]
