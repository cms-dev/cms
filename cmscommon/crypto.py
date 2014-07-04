#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2013 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""Utilities dealing with encryption and randomness."""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import base64
import binascii

from Crypto.Cipher import AES


__all__ = [
    "is_random_secure",

    "get_random_key", "get_hex_random_key",

    "encrypt_string", "decrypt_string",
    "encrypt_number", "decrypt_number",
    ]


# Some older versions of pycrypto don't provide a Random module
# If that's the case, fallback to weak standard library PRG
try:
    from Crypto import Random
    _rndfile = Random.new()
    get_random_bits = lambda x: _rndfile.read(x)
    is_random_secure = True
except ImportError:
    import random
    get_random_bits = lambda x: binascii.unhexlify("%032x" %
                                                   random.getrandbits(x * 8))
    is_random_secure = False


def _get_secret_key_unhex():
    # Only import this if we need it. Otherwise, we would prefer to
    # remain independent of the rest of CMS.
    from cms import config
    return binascii.unhexlify(config.secret_key)


def get_random_key():
    """Generate 16 random bytes, safe to be used as AES key.

    """
    return get_random_bits(16)


def get_hex_random_key():
    """Generate 16 random bytes, safe to be used as AES key.
    Return it encoded in hexadecimal.

    """
    return binascii.hexlify(get_random_key())


def encrypt_string(pt, key=None):
    """Encrypt the plaintext (pt) with the 16-bytes key. Moreover, it
    encrypts it using a random IV, so that encrypting repeatedly the
    same string gives different outputs. This way no analisys can made
    when the same number is used in different contexts. The generated
    string uses the alphabet { 'a', ..., 'z', 'A', ..., 'Z', '0', ...,
    '9', '.', '-', '_' }, so it is safe to use in URLs.

    If key is not specified, it is obtained from the configuration.

    """
    if key is None:
        key = _get_secret_key_unhex()
    # Pad the plaintext to make its length become a multiple of the block size
    # (that is, for AES, 16 bytes), using a byte 0x01 followed by as many bytes
    # 0x00 as needed. If the length of the message is already a multiple of 16
    # bytes, add a new block.
    pt_pad = bytes(pt) + b'\01' + b'\00' * (16 - (len(pt) + 1) % 16)
    # The IV is a random block used to differentiate messages encrypted with
    # the same key. An IV should never be used more than once in the lifetime
    # of the key. In this way encrypting the same plaintext twice will produce
    # different ciphertexts.
    iv = get_random_key()
    # Initialize the AES cipher with the given key and IV.
    aes = AES.new(key, AES.MODE_CBC, iv)
    ct = aes.encrypt(pt_pad)
    # Convert the ciphertext in a URL-safe base64 encoding
    ct_b64 = base64.urlsafe_b64encode(iv + ct).replace(b'=', b'.')
    return ct_b64


def decrypt_string(ct_b64, key=None):
    """Decrypt a ciphertext (ct_b64) encrypted with encrypt_string and
    return the corresponding plaintext.

    If key is not specified, it is obtained from the configuration.

    """
    if key is None:
        key = _get_secret_key_unhex()
    try:
        # Convert the ciphertext from a URL-safe base64 encoding to a
        # bytestring, which contains both the IV (the first 16 bytes) as well
        # as the encrypted padded plaintext.
        iv_ct = base64.urlsafe_b64decode(bytes(ct_b64).replace(b'.', b'='))
        aes = AES.new(key, AES.MODE_CBC, iv_ct[:16])
        # Get the padded plaintext.
        pt_pad = aes.decrypt(iv_ct[16:])
        # Remove the padding.
        # TODO check that the padding is correct, i.e. that it contains at most
        # 15 bytes 0x00 preceded by a byte 0x01.
        pt = pt_pad.rstrip(b'\x00')[:-1]
        return pt
    except TypeError:
        raise ValueError('Could not decode from base64.')
    except ValueError:
        raise ValueError('Wrong AES cryptogram length.')


def encrypt_number(num, key=None):
    """Encrypt an integer number, with the same properties as
    encrypt_string().

    If key is not specified, it is obtained from the configuration.

    """
    hexnum = b"%x" % num
    return encrypt_string(hexnum, key)


def decrypt_number(enc, key=None):
    """Decrypt an integer number encrypted with encrypt_number().

    If key is not specified, it is obtained from the configuration.

    """
    return int(decrypt_string(enc, key), 16)
