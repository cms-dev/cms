#!/usr/bin/env python2
# -*- coding: utf-8 -*-

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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import six

from cmsranking.Entity import Entity, InvalidData
from cmsranking.Store import Store
from cmsranking.Submission import store as submission_store


class Task(Entity):
    """The entity representing a task.

    It consists of the following properties:
    - name (unicode): the human-readable name of the task
    - short_name (unicode): a shorter name for the task, usually a
        code-name
    - contest (unicode): the id of the contest the task belongs to
    - max_score (float): the maximum achievable score for the task
    - score_precision (int): how many decimal places to show in scores
    - data_headers ([unicode]): a list with the descriptions of the
        extra fields that will be provided with each submission for the
        task
    - order (int): the order of the tasks inside of the contest

    """
    def __init__(self):
        """Set the properties to some default values.

        """
        Entity.__init__(self)
        self.name = None
        self.short_name = None
        self.contest = None
        self.max_score = None
        self.extra_headers = None
        self.order = None
        self.score_mode = "max_tokened_last"

    @staticmethod
    def validate(data):
        """Validate the given dictionary.

        See if it contains a valid representation of this entity.

        """
        try:
            assert isinstance(data, dict), \
                "Not a dictionary"
            assert isinstance(data['name'], six.text_type), \
                "Field 'name' isn't a string"
            assert isinstance(data['short_name'], six.text_type), \
                "Field 'short_name' isn't a string"
            assert isinstance(data['contest'], six.text_type), \
                "Field 'contest' isn't a string"
            assert isinstance(data['max_score'], float), \
                "Field 'max_score' isn't a float"
            assert isinstance(data['score_precision'], six.integer_types), \
                "Field 'score_precision' isn't an integer"
            assert data['score_precision'] >= 0, \
                "Field 'score_precision' is negative"
            assert isinstance(data['extra_headers'], list), \
                "Field 'extra_headers' isn't a list of strings"
            assert isinstance(data['score_mode'], six.text_type), \
                "Field 'score_mode' isn't a string"
            for i in data['extra_headers']:
                assert isinstance(i, six.text_type), \
                    "Field 'extra_headers' isn't a list of strings"
            assert isinstance(data['order'], six.integer_types), \
                "Field 'order' isn't an integer"
        except KeyError as exc:
            raise InvalidData("Field %s is missing" % exc.message)
        except AssertionError as exc:
            raise InvalidData(exc.message)

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

    def consistent(self):
        from cmsranking.Contest import store as contest_store
        return self.contest in contest_store


store = Store(Task, 'tasks', [submission_store])
