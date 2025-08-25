#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2017 Valentin Rosca <rosca.valentin2012@gmail.com>
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

import hmac
import secrets
from string import ascii_lowercase

import bcrypt


__all__ = [
    "get_random_key", "get_hex_random_key",

    "generate_random_password",

    "validate_password", "build_password", "hash_password",
    "parse_authentication",
    ]


# bcrypt difficulty parameter. This is here so that it can be set to a lower
# value when running unit tests. It seems that the lowest accepted value is 4.
BCRYPT_ROUNDS = 12

def get_random_key() -> bytes:
    """Generate 16 random bytes, safe to be used as AES key.

    """
    return secrets.token_bytes(16)


def get_hex_random_key() -> str:
    """Generate 16 random bytes, safe to be used as AES key.
    Return it encoded in hexadecimal.

    """
    return get_random_key().hex()


def generate_random_password() -> str:
    """Utility method to generate a random password.

    return: a random string.

    """
    return "".join((secrets.choice(ascii_lowercase) for _ in range(6)))


def parse_authentication(authentication: str) -> tuple[str, str]:
    """Split the given method:password field into its components.

    authentication: an authentication string as stored in the DB,
        for example "plaintext:password".

    return: the method and the payload

    raise (ValueError): when the authentication string is not valid.

    """
    method, sep, payload = authentication.partition(":")

    if sep != ":":
        raise ValueError("Authentication string not parsable.")

    return method, payload


def validate_password(authentication: str, password: str) -> bool:
    """Validate the given password for the required authentication.

    authentication: an authentication string as stored in the db,
        for example "plaintext:password".
    password: the password provided by the user.

    return: whether password is correct.

    raise (ValueError): when the authentication string is not valid or
        the method is not known.

    """
    method, payload = parse_authentication(authentication)
    password_bytes = password.encode("utf-8")
    payload_bytes = payload.encode("utf-8")
    if method == "bcrypt":
        try:
            return bcrypt.checkpw(password_bytes, payload_bytes)
        except ValueError:
            return False
    elif method == "plaintext":
        return hmac.compare_digest(password_bytes, payload_bytes)
    else:
        raise ValueError("Authentication method not known.")


def build_password(password: str, method: str = "plaintext") -> str:
    """Build an auth string from an already-hashed password.

    password: the hashed password.
    method: the hasing method to use.

    return: the string embedding the method and the password.

    """
    # TODO make sure it's a valid bcrypt hash if method is bcrypt.
    return "%s:%s" % (method, password)


def hash_password(password: str, method: str = "bcrypt") -> str:
    """Hash and build an auth string from a plaintext password.

    password: the password in plaintext.
    method: the hashing method to use.

    return: the auth string containing the hashed password.

    raise (ValueError): if the method is not supported.

    """
    if method == "bcrypt":
        password_bytes = password.encode("utf-8")
        salt = bcrypt.gensalt(BCRYPT_ROUNDS)
        payload = bcrypt.hashpw(password_bytes, salt).decode("ascii")
    elif method == "plaintext":
        payload = password
    else:
        raise ValueError("Authentication method not known.")

    return build_password(payload, method)
