#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2013 Stefano Maggiolo <s.maggiolo@gmail.com>
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
from __future__ import unicode_literals

from sqlalchemy.types import TypeDecorator, Unicode


class RepeatedUnicode(TypeDecorator):
    """Implement (short) lists of unicode strings.

    """
    impl = Unicode

    def process_bind_param(self, value, unused_dialect):
        """Encode value in a single unicode.

        value ([unicode]): the list to encode.

        return (unicode): the unicode string encoding value.

        raise (ValueError): if some string contains ",".

        """
        # This limitation may be removed if necessary.
        if any("," in val for val in value):
            raise ValueError("Comma cannot be encoded.")
        return ",".join(value)

    def process_result_value(self, value, unused_dialect):
        """Decode values from a single unicode.

        value (unicode): the unicode string to decode.

        return ([unicode]): the decoded list.

        """
        return value.split(",")
