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

"""Tests for the crypto module"""

import re
import unittest

from cmscommon.binary import bin_to_b64
from cmscommon.crypto import build_password, \
    decrypt_binary, decrypt_number, encrypt_binary, encrypt_number, \
    generate_random_password, get_hex_random_key, get_random_key, \
    hash_password, parse_authentication, validate_password


class TestGetRandomKey(unittest.TestCase):
    """Tests for the function get_random_key."""

    def test_length(self):
        # Should be 16 bytes.
        self.assertEqual(len(get_random_key()), 16)


class TestGetHexRandomKey(unittest.TestCase):
    """Tests for the function get_hex_random_key."""

    def test_valid(self):
        self.assertRegex(get_hex_random_key(), r"^[0-9a-f]*$")

    def test_length(self):
        # Should be 16 bytes.
        self.assertEqual(len(get_hex_random_key()), 32)


class TestEncryptAndDecryptBinary(unittest.TestCase):
    """Tests for the functions encrypt_binary and decrypt_binary."""

    def setUp(self):
        super().setUp()
        self.key = get_hex_random_key()

    def test_encrypt_and_decrypt(self):
        self.assertEqual(
            decrypt_binary(encrypt_binary(b"stuff", self.key), self.key),
            b"stuff")

    def test_encrypt_and_decrypt_empty(self):
        self.assertEqual(
            decrypt_binary(encrypt_binary(b"", self.key), self.key),
            b"")

    def test_encrypt_and_decrypt_long(self):
        value = b"0" * 1_000_000
        self.assertEqual(
            decrypt_binary(encrypt_binary(value, self.key), self.key),
            value)

    def test_encrypt_chaining(self):
        # Even if the input is repeated, the output should not be.
        encrypted = encrypt_binary(b"0" * 1_000_000, self.key)
        # The output should appear random, so any sequence of 64 bytes is
        # very unlikely to repeat.
        blocks = re.findall(".{64}", encrypted)
        self.assertEqual(len(blocks), len(set(blocks)))

    def test_encrypt_salting(self):
        self.assertNotEqual(encrypt_binary(b"stuff", self.key),
                            encrypt_binary(b"stuff", self.key))

    def test_decrypt_invalid_base64(self):
        encrypted = encrypt_binary(b"stuff", self.key)
        with self.assertRaises(ValueError):
            decrypt_binary(encrypted[1:], self.key)

    def test_decrypt_invalid_encrypted(self):
        # "stuff" is not decryptable.
        encrypted = bin_to_b64(b"stuff")
        with self.assertRaises(ValueError):
            decrypt_binary(encrypted, self.key)


class TestEncryptAndDecryptNumber(unittest.TestCase):
    """Tests for the functions encrypt_number and decrypt_number."""

    def setUp(self):
        super().setUp()
        self.key = get_hex_random_key()

    def test_encrypt_and_decrypt(self):
        self.assertEqual(
            decrypt_number(encrypt_number(123, self.key), self.key),
            123)

    def test_encrypt_and_decrypt_negative(self):
        self.assertEqual(
            decrypt_number(encrypt_number(-123, self.key), self.key),
            -123)

    def test_encrypt_and_decrypt_big(self):
        self.assertEqual(
            decrypt_number(encrypt_number(10 ** 42, self.key), self.key),
            10 ** 42)


class TestGenerateRandomPassword(unittest.TestCase):
    """Tests for the function generate_random_password."""

    def test_alphabet(self):
        self.assertRegex(generate_random_password(), r"^[a-z]*$")

    def test_random(self):
        self.assertNotEqual(generate_random_password(),
                            generate_random_password())


class TestParseAuthentication(unittest.TestCase):
    """Tests for the function parse_authentication."""

    def test_success(self):
        method, payload = parse_authentication("plaintext:42")
        self.assertEqual(method, "plaintext")
        self.assertEqual(payload, "42")

    def test_success_colon(self):
        method, payload = parse_authentication("method:42:24")
        self.assertEqual(method, "method")
        self.assertEqual(payload, "42:24")

    def test_success_nonascii(self):
        method, payload = parse_authentication("method:你好")
        self.assertEqual(method, "method")
        self.assertEqual(payload, "你好")

    def test_fail(self):
        with self.assertRaises(ValueError):
            parse_authentication("no colon")


class TestBuildPassword(unittest.TestCase):
    """Tests for the function build_password."""

    def test_success(self):
        self.assertEqual(build_password("pwd", "method"), "method:pwd")

    def test_non_ascii(self):
        self.assertEqual(build_password("p你好", "m你好"), "m你好:p你好")

    def test_default_plaintext(self):
        self.assertEqual(build_password("plain"), "plaintext:plain")


class TestHashAndValidatePassword(unittest.TestCase):
    """Tests for the functions hash_password and validate_password."""

    def test_plaintext(self):
        self.assertTrue(validate_password(
            hash_password("p你好", method="plaintext"), "p你好"))
        self.assertFalse(validate_password(
            hash_password("p你好", method="plaintext"), "你好"))

    def test_bcrypt(self):
        self.assertTrue(validate_password(
            hash_password("p你好", method="bcrypt"), "p你好"))
        self.assertFalse(validate_password(
            hash_password("p你好", method="bcrypt"), "你好"))

    def test_invalid_method(self):
        with self.assertRaises(ValueError):
            hash_password("test", "pwd")
        with self.assertRaises(ValueError):
            validate_password("test:pwd", "pwd")


if __name__ == "__main__":
    unittest.main()
