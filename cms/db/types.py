#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2013 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2014-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""Custom types for SQLAlchemy.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *
from future.builtins import *

import psycopg2.extras
import sqlalchemy
from sqlalchemy.dialects.postgresql import ARRAY


# Have psycopg2 use the Python types in ipaddress to represent the INET
# and CIDR data types of PostgreSQL.
psycopg2.extras.register_ipaddress()


# Taken from:
# http://docs.sqlalchemy.org/en/rel_1_0/dialects/postgresql.html#using-json-jsonb-with-array
# Some specialized types (like CIDR) have a natural textual
# representation and PostgreSQL automatically converts them to and from
# it. However that conversion isn't automatic when these types are
# wrapped inside an ARRAY (e.g., TEXT[] can't be automatically cast to
# CIDR[]). This subclass of ARRAY performs such casting explicitly for
# each entry.
class CastingArray(ARRAY):
    def bind_expression(self, bindvalue):
        return sqlalchemy.cast(bindvalue, self)
