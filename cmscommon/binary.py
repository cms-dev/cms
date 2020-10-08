#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

import binascii


__all__ = [
    "bin_to_hex", "hex_to_bin", "bin_to_b64", "b64_to_bin",
]


def bin_to_hex(bin):
    return binascii.b2a_hex(bin).decode('ascii')


def hex_to_bin(hex):
    return binascii.a2b_hex(hex.encode('ascii'))


def bin_to_b64(bin):
    return binascii.b2a_base64(bin, newline=False).decode('ascii')


def b64_to_bin(b64):
    return binascii.a2b_base64(b64.encode('ascii'))
