#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Utilities to generate "unique" test ids."""

import random

from cmscommon.digest import bytes_digest


def unique_long_id():
    """Return a unique id of type long."""
    if not hasattr(unique_long_id, "id"):
        unique_long_id.id = random.randint(0, 1_000_000_000)
    unique_long_id.id += 1
    return unique_long_id.id


def unique_unicode_id():
    """Return a unique id of type unicode."""
    return str(unique_long_id())


def unique_digest():
    """Return a unique digest-like string."""
    return bytes_digest(unique_unicode_id().encode("utf-8"))
