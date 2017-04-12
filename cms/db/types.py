#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2013 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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
from __future__ import print_function
from __future__ import unicode_literals

import ipaddress

import psycopg2.extras
import sqlalchemy
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.types import TypeDecorator, Unicode


# Have psycopg2 use the types in ipaddress to represent the CIDR type.
# A handy function to do that has been added in v2.7, for versions
# before that we do it ourselves. See:
# https://github.com/psycopg/psycopg2/commit/643ba70bad0f19a68c06ec95de2691c28e060e48

try:
    psycopg2.extras.register_ipaddress()

except AttributeError:
    from psycopg2.extensions import new_type, new_array_type, register_type, \
        register_adapter, QuotedString

    def cast_interface(s, cur=None):
        if s is None:
            return None
        return ipaddress.ip_interface(unicode(s))

    def cast_ipnetwork(s, cur=None):
        if s is None:
            return None
        return ipaddress.ip_network(unicode(s))

    inet = new_type((869,), b'INET', cast_interface)
    ainet = new_array_type((1041,), b'INET[]', inet)

    cidr = new_type((650,), b'CIDR', cast_ipnetwork)
    acidr = new_array_type((651,), b'CIDR[]', cidr)

    for c in [inet, ainet, cidr, acidr]:
        register_type(c, None)

    def adapt_ipaddress(obj):
        return QuotedString(str(obj))

    for t in [ipaddress.IPv4Interface, ipaddress.IPv6Interface,
              ipaddress.IPv4Network, ipaddress.IPv6Network]:
        register_adapter(t, adapt_ipaddress)


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


class RepeatedUnicode(TypeDecorator):
    """Implement (short) lists of unicode strings.

    All values need to contain some non-whitespace characters and no
    comma. Leading and trailing whitespace will be stripped.

    """
    impl = Unicode

    def process_bind_param(self, value, unused_dialect):
        """Encode value in a single unicode.

        value ([unicode]): the list to encode.

        return (unicode): the unicode string encoding value.

        raise (ValueError): if some string contains "," or is composed
            only by whitespace.

        """
        # This limitation may be removed if necessary.
        if any("," in val for val in value):
            raise ValueError("Comma cannot be encoded.")
        if any(len(val) == 0 or val.isspace() for val in value):
            raise ValueError("Cannot be only whitespace.")
        return ",".join(val.strip() for val in value)

    def process_result_value(self, value, unused_dialect):
        """Decode values from a single unicode.

        value (unicode): the unicode string to decode.

        return ([unicode]): the decoded list.

        """
        return list(val.strip() for val in value.split(",")
                    if len(val) > 0 and not val.isspace())
