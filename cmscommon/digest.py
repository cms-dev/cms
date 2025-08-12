#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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

import hashlib
import io

from cmscommon.binary import bin_to_hex


__all__ = [
    "Digester", "bytes_digest", "path_digest"
]


class Digester:
    """Simple wrapper of hashlib using our preferred hasher."""

    def __init__(self):
        self._hasher = hashlib.sha1()

    def update(self, b: bytes):
        """Add the bytes b to the hasher."""
        self._hasher.update(b)

    def digest(self) -> str:
        """Return the digest as an hex string."""
        return bin_to_hex(self._hasher.digest())


def bytes_digest(b: bytes) -> str:
    """Return the digest for the passed bytes.

    Currently CMS uses SHA1, but this should be treated as an implementation
    detail.

    b: some bytes.

    return: digest of the bytes.

    """
    d = Digester()
    d.update(b)
    return d.digest()


def path_digest(path: str) -> str:
    """Return the digest of the content of a file, given by its path.

    path: path of the file we are interested in.

    return: digest of the content of the file in path.

    """
    with open(path, 'rb') as fin:
        d = Digester()
        buf = fin.read(io.DEFAULT_BUFFER_SIZE)
        while len(buf) > 0:
            d.update(buf)
            buf = fin.read(io.DEFAULT_BUFFER_SIZE)
        return d.digest()
