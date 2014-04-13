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
            assert isinstance(data['f_name'], six.text_type), \
                "Field 'f_name' isn't a string"
            assert isinstance(data['l_name'], six.text_type), \
                "Field 'l_name' isn't a string"
            assert data['team'] is None or \
                isinstance(data['team'], six.text_type), \
                "Field 'team' isn't a string (or null)"
        except KeyError as exc:
            raise InvalidData("Field %s is missing" % exc.message)
        except AssertionError as exc:
            raise InvalidData(exc.message)

    def set(self, data):
        self.validate(data)
        self.f_name = data['f_name']
        self.l_name = data['l_name']
        self.team = data['team']

    def get(self):
        result = self.__dict__.copy()
        del result['key']
        return result

    def consistent(self):
        from cmsranking.Team import store as team_store
        return self.team is None or self.team in team_store


store = Store(User, 'users', [submission_store])
