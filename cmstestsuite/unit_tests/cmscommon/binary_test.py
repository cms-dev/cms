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

"""Tests for the binary module"""

import binascii
import unittest

from cmscommon.binary import bin_to_hex, hex_to_bin, bin_to_b64, b64_to_bin


class TestBinToHex(unittest.TestCase):

    def test_success(self):
        self.assertEqual(bin_to_hex(b"\x32\x00\xa0"), "3200a0")
        self.assertEqual(bin_to_hex(b"\xFF\xFF\xFF\xFF"), "ffffffff")
        self.assertEqual(bin_to_hex(b"\x00" * 1000), "0" * 2000)

    def test_string(self):
        with self.assertRaises(TypeError):
            bin_to_hex("cms")


class TestHexToBin(unittest.TestCase):

    def setUp(self):
        super().setUp()
        # The exception type depend on Python's version.
        self.error = binascii.Error

    def test_success(self):
        self.assertEqual(hex_to_bin("3200a0"), b"\x32\x00\xa0")
        self.assertEqual(hex_to_bin("ffffffff"), b"\xFF\xFF\xFF\xFF")
        self.assertEqual(hex_to_bin("0" * 2000), b"\x00" * 1000)

    def test_invalid_length(self):
        with self.assertRaises(self.error):
            hex_to_bin("000")

    def test_invalid_alphabet(self):
        with self.assertRaises(self.error):
            hex_to_bin("cmscms")


class TestBinToB64(unittest.TestCase):

    def test_success(self):
        self.assertEqual(bin_to_b64(b"\x32\x00\xa0"), "MgCg")
        self.assertEqual(bin_to_b64(b"\xFF\xFF\xFF\xFF"), "/////w==")
        self.assertEqual(bin_to_b64(b"\x00" * 3000), "A" * (3000 * 4 // 3))

    def test_string(self):
        with self.assertRaises(TypeError):
            bin_to_b64("cms")


class TestB64ToBin(unittest.TestCase):

    def test_success(self):
        self.assertEqual(b64_to_bin("MgCg"), b"\x32\x00\xa0")
        self.assertEqual(b64_to_bin("/////w=="), b"\xFF\xFF\xFF\xFF")
        self.assertEqual(b64_to_bin("A" * (3000 * 4 // 3)), b"\x00" * 3000)

    def test_invalid_length(self):
        with self.assertRaises(binascii.Error):
            b64_to_bin("MgC")

    def test_invalid_alphabet(self):
        # binascii ignores invalid characters
        self.assertEqual(b64_to_bin("M\x00g.C,g\x0a"), b"\x32\x00\xa0")


if __name__ == "__main__":
    unittest.main()
