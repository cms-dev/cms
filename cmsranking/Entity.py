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


class InvalidKey(Exception):
    """Exception raised in case of invalid key."""
    pass


class InvalidData(Exception):
    """Exception raised in case of invalid data."""
    pass


class Entity(object):
    """Base virtual class which all entities should extend.

    Provide some virtual methods that other classes should implement.

    """
    def set(self, data):
        """Set all properties using the given data.

        Accept the data format used on the HTTP interface.

        data (str): the properties of the entity, in the "external" format

        Raise InvalidData if not able to parse the data argument.

        """
        pass

    def get(self):
        """Get all properties.

        Produce the data format used on the HTTP interface.

        return (str): the properties of the entity, in the "external" format

        """
        pass

    def load(self, data):
        """Set all properties using the given data.

        Accept the data format used for the file storage.

        data (str): the properties of the entity, in the "internal" format

        Raise InvalidData if not able to parse the data argument.

        """
        pass

    def dump(self):
        """Get all properties.

        Produce the data format used for the file storage.

        return (str): the properties of the entity, in the "internal" format

        """
        pass

    def consistent(self):
        """Check if the entity is consistent.

        Verify that all references to other entities are correct (i.e. those
        entities actually exist).

        return (bool): the result of this check

        """
        return True
