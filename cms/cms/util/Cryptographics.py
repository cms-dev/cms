#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2011 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2011 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2011 Matteo Boscariol <boscarim@hotmail.com>
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

from Crypto.Cipher import AES
from Crypto import Random
import base64
import binascii

from cms.async import Config
secret_key_unhex = binascii.unhexlify(Config.secret_key)

def get_random_key():
    """Generate 16 random bytes, safe to be used as AES key.

    """
    return Random.get_random_bytes(16)

def get_hex_random_key():
    """Generate 16 random bytes, safe to be used as AES key.
    Return it encoded in hexadecimal.

    """
    return binascii.hexlify(get_random_key())

def encrypt_string(s, key=None):
    """Encrypt the string s num with the 16-bytes key, generating a
    cryptogram safe to be used in URLs. Moreover, it encrypts it using
    a random salt, so that encrypting repeatedly the same string gives
    different outputs. This way no analisys can made when the same
    number is used in different contexts.

    This function pads the string s with NULL bytes, so any NULL byte
    at the end of the string will be discarded by decryption function.

    """
    if key is None:
        key = secret_key_unhex
    iv2 = get_random_key()
    dec = iv2 + s
    dec += "\x00" * (16 - ((len(dec)-1) % 16 + 1))
    aes = AES.new(key, mode=AES.MODE_CBC)
    return base64.urlsafe_b64encode(aes.encrypt(dec)).replace('=', '.')

def decrypt_string(enc, key=None):
    """Decrypt a string encrypted with encrypt_string.

    """
    if key is None:
        key = secret_key_unhex
    aes = AES.new(key, mode=AES.MODE_CBC)
    return aes.decrypt(base64.urlsafe_b64decode(enc.replace('.', '=')))[16:].rstrip('\x00')

def encrypt_number(num, key=None):
    """Encrypt an integer number, with the same properties as encrypt_string().

    """
    hexnum = hex(num).replace('0x', '')
    return encrypt_string(hexnum, key)

def decrypt_number(enc, key=None):
    """Decrypt an integer number encrypted with encrypt_number().

    """
    return int(decrypt_string(enc, key), 16)
