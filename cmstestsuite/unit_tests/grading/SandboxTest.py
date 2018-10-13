#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2014 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
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

"""Tests for general utility functions."""

import io
import unittest

from cms.grading.Sandbox import Truncator


class TestTruncator(unittest.TestCase):
    """Test the class Truncator."""
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def perform_truncator_test(self, orig_len, trunc_len, read_chunk_size):
        back_file = io.BytesIO(b'a' * orig_len)
        truncator = Truncator(back_file, trunc_len)
        buf = truncator.read(read_chunk_size)
        read_len = 0
        while buf != "":
            read_len += len(buf)
            buf = truncator.read(read_chunk_size)
        self.assertEqual(read_len, min(trunc_len, orig_len))

    def test_long_file(self):
        """Read a file longer than requested truncation length.

        """
        self.perform_truncator_test(100, 40, 1000)

    def test_short_file(self):
        """Read a file shorter than requested truncation length.

        """
        self.perform_truncator_test(100, 400, 1000)

    def test_chunked_file(self):
        """Read a file in little chunks.

        """
        self.perform_truncator_test(100, 40, 7)


if __name__ == "__main__":
    unittest.main()
