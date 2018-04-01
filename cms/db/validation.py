#!/usr/bin/env python
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

"""Constraints adding server-side validation to a SQLAlchemy Column.

This module provides classes that can be used to add constraints to
textual Columns in order to ensure that the values in these columns
always match a given regular expression (unless they are NULL). These
conditions are enforced server-side, by the database itself, and are
added to the table upon creation. Only PostgreSQL and psycopg2 are
supported.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa

from sqlalchemy import all_, and_, func, literal_column
from sqlalchemy.schema import CheckConstraint
from sqlalchemy.sql.expression import ColumnClause

from cms.db.filecacher import FileCacher


# TODO In SQLAlchemy 1.2 we can get rid of literal_column. See:
# https://bitbucket.org/zzzeek/sqlalchemy/issues/3957/incorrect-rendering-of-sqltext-for-column
# https://groups.google.com/d/topic/sqlalchemy/J6VPG_1Fj2U/discussion

class CodenameConstraint(CheckConstraint):
    """Check that the column uses a limited alphabet."""

    def __init__(self, column_name):
        column = ColumnClause(column_name)
        super(CodenameConstraint, self).__init__(
            column.op("~")(literal_column("'^[A-Za-z0-9_-]+$'")))


class FilenameConstraint(CheckConstraint):
    """Check that the column is a filename using a simple alphabet."""

    def __init__(self, column_name):
        column = ColumnClause(column_name)
        super(FilenameConstraint, self).__init__(and_(
            column.op("~")(literal_column("'^[A-Za-z0-9_.%-]+$'")),
            column != literal_column("'.'"),
            column != literal_column("'..'")))


class FilenameListConstraint(CheckConstraint):
    """Check that the column is a list of filenames (as above)."""

    def __init__(self, column_name):
        column = ColumnClause(column_name)
        # Postgres allows the condition "<sth> <op> ALL (<array>)" that
        # is true iff for all elements of array "<sth> <op> <element>".
        # This works for (in)equality but, as the order of the operands
        # is preserved, it doesn't work for regexp matching, where the
        # syntax is "<text> ~ <pattern>". Our regexp operates on a per
        # character basis so we can work around it by concatenating the
        # items of the array (using array_to_string) and match the
        # regexp on the result.
        empty = literal_column("''")
        super(FilenameListConstraint, self).__init__(and_(
            func.array_to_string(column, empty).op("~")(
                literal_column("'^[A-Za-z0-9_.%-]*$'")),
            empty != all_(column),
            literal_column("'.'") != all_(column),
            literal_column("'..'") != all_(column)))


class DigestConstraint(CheckConstraint):
    """Check that the column is a valid SHA1 hex digest."""

    def __init__(self, column_name):
        column = ColumnClause(column_name)
        super(DigestConstraint, self).__init__(
            column.op("~")(literal_column(
                "'^([0-9a-f]{40}|%s)$'" % FileCacher.TOMBSTONE_DIGEST)))
