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


import typing

if typing.TYPE_CHECKING:
    from cmsranking.Store import Store


class InvalidKey(Exception):
    """Exception raised in case of invalid key."""
    pass


class InvalidData(Exception):
    """Exception raised in case of invalid data."""
    pass


class Entity:
    """Base virtual class which all entities should extend.

    Provide some virtual methods that other classes should implement.

    """
    key: str  # Will be set by the Store managing this entity

    def set(self, data: dict):
        """Set all properties using the given data.

        Accept the data format used on the HTTP interface.

        data: the properties of the entity, in the "external"
            format

        Raise InvalidData if not able to parse the data argument.

        """
        pass

    def get(self) -> dict:
        """Get all properties.

        Produce the data format used on the HTTP interface.

        return: the properties of the entity, in the "external"
            format

        """
        pass

    def consistent(self, stores: dict[str, "Store"]) -> bool:
        """Check if the entity is consistent.

        Verify that all references to other entities are correct (i.e.
        those entities actually exist).

        stores: a dict of Stores that can be used to
            validate references to other entities.

        return: the result of this check

        """
        return True
