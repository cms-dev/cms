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

from sqlalchemy.types import TypeDecorator, Unicode


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
