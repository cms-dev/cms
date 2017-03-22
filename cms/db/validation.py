#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2017 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

from sqlalchemy import or_, not_
from sqlalchemy.event import listens_for
from sqlalchemy.orm import mapper
from sqlalchemy.schema import CheckConstraint


class ValidationConstraint(object):
    """Constraint adding server-side validation to a SQLAlchemy Column.

    An instance of (a subclass of) this object has to be provided as an
    argument to the constructor of the Column object to which it has to
    apply. It results in a CheckConstraint being added to the table of
    the class said column is defined on.

    """
    # In order to create a CheckConstraint we need to know the name of
    # the column, but the Column object doesn't know this itself until
    # it gets eventually assigned to a class-level attribute and the
    # metaclass magic of SQLAlchemy kicks in. We could ask the user to
    # provide the name as an argument, but that would lead to ugly
    # redundancy. The solution we adopt stores the Column objects we
    # want to add a constraint to, listens to an SQLAlchemy that gets
    # fired when all the mappers are ready and only then attaches the
    # CheckConstraint to the table. This is all mostly legal, with the
    # exception of this class exposing a method that mimics an
    # undocumented internal SQLAlchemy interface.
    columns = list()

    @staticmethod
    def get_condition(column):
        """Build an expression checking that the given Column is valid."""
        raise NotImplementedError()

    @staticmethod
    @listens_for(mapper, "mapper_configured")
    def _mapper_configured_handler(class_mapper, _):
        """Add the constraints to the table of the given mapper."""
        table = class_mapper.mapped_table
        for obj, column in ValidationConstraint.columns:
            if table.columns.contains_column(column):
                table.append_constraint(
                    CheckConstraint(obj.get_condition(column)))

    # This is the method called by the Column object's constructor to
    # let us bind to it. We sort of abuse this.
    def _set_parent_with_dispatch(self, column):
        self.columns.append((self, column))


class CodenameConstraint(ValidationConstraint):
    """Check that the column uses a limited alphabet."""
    @staticmethod
    def get_condition(column):
        return column.op("~")("^[A-Za-z0-9_-]+$")


class FilenameConstraint(ValidationConstraint):
    """Check that the column is a valid POSIX path component."""
    @staticmethod
    def get_condition(column):
        # These are the path components allowed by ext2/3/4 and by any
        # other POSIX-compliant filesystem. Observe that NULL (0) chars
        # are forbidden but they are already forbidden by PostgreSQL.
        return not_(or_(
            column == "", column == ".", column == "..", column.contains("/")))


class DigestConstraint(ValidationConstraint):
    """Check that the column is a valid SHA1 hex digest."""
    @staticmethod
    def get_condition(column):
        return column.op("~")("^[0-9a-f]{40}$")


class IPv4Constraint(ValidationConstraint):
    """Check that the column is a valid IPv4 address (plus subnet?)."""
    RE255 = "[0-9]|[1-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-5]"
    RE32 = "[0-9]|[1-2][0-9]|3[0-2]"

    @staticmethod
    def get_condition(column):
        return column.op("~")(
            "^(%(re255)s)\.(%(re255)s)\.(%(re255)s)\.(%(re255)s)(/(%(re32)s))?$"
            % {"re255": IPv4Constraint.RE255, "re32": IPv4Constraint.RE32})
