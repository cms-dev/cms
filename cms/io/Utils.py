#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
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

"""Random utilities and logging facilities.

"""

from __future__ import print_function

import json
import sys

import six


def encode_json(obj):
    """Encode a dictionary as a JSON string; on failure, returns None.

    obj (object): the object to encode
    return (bytes): an encoded string

    """
    try:
        return json.dumps(obj, encoding='utf-8')
    except ValueError:
        print("Can't encode JSON: %r" % obj, file=sys.stderr)
        raise


def decode_json(string):
    """Decode a JSON string to a dictionary; on failure, raises an
    exception.

    string (bytes): the string to decode
    return (object): the decoded object

    """
    if not isinstance(string, six.binary_type):
        raise TypeError("String isn't binary")
    try:
        return json.loads(string, encoding='utf-8')
    except ValueError:
        print("Can't decode JSON: %r" % string, file=sys.stderr)
        raise
