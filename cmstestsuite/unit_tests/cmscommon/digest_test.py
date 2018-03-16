#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

"""Tests for the the digest module"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa
from six import PY2

import unittest

from cmstestsuite.unit_tests.filesystemmixin import FileSystemMixin

from cmscommon.digest import Digester, bytes_digest, path_digest


_EMPTY_DIGEST = "da39a3ee5e6b4b0d3255bfef95601890afd80709"
_CONTENT_DIGEST = "040f06fd774092478d450774f5ba30c5da78acc8"


class TestDigester(unittest.TestCase):

    def setUp(self):
        super(TestDigester, self).setUp()
        self.d = Digester()

    def test_success(self):
        self.assertEqual(self.d.digest(), _EMPTY_DIGEST)
        self.d.update(b"content")
        self.assertEqual(self.d.digest(), _CONTENT_DIGEST)

    def test_empty_update(self):
        self.d.update(b"")
        self.assertEqual(self.d.digest(), _EMPTY_DIGEST)

    @unittest.skipIf(PY2, "Python2 allows strings")
    def test_string(self):
        with self.assertRaises(TypeError):
            self.d.update("")


class TestBytesDigest(unittest.TestCase):

    def test_success(self):
        self.assertEqual(bytes_digest(b"content"), _CONTENT_DIGEST)

    def test_empty(self):
        self.assertEqual(bytes_digest(b""), _EMPTY_DIGEST)

    @unittest.skipIf(PY2, "Python2 allows strings")
    def test_string(self):
        with self.assertRaises(TypeError):
            bytes_digest("")


class TestPathDigest(FileSystemMixin, unittest.TestCase):

    def setUp(self):
        super(TestPathDigest, self).setUp()
        self.filename = "f"
        self.path = self.get_path(self.filename)

    def test_success(self):
        self.write_file(self.filename, b"content")
        self.assertEqual(path_digest(self.path), _CONTENT_DIGEST)

    def test_empty(self):
        self.write_file(self.filename, b"")
        self.assertEqual(path_digest(self.path), _EMPTY_DIGEST)

    def test_long(self):
        content = b"0" * 1000000
        self.write_file(self.filename, content)
        self.assertEqual(path_digest(self.path), bytes_digest(content))

    @unittest.skipIf(PY2, "Python2 uses IOError")
    def test_not_found(self):
        with self.assertRaises(FileNotFoundError):
            path_digest(self.path)


if __name__ == "__main__":
    unittest.main()
