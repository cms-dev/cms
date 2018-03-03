#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Utilities for cmscontrib"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa

import hashlib
import io
import os

from cmscommon.binary import bin_to_hex


def sha1sum(path):
    """Calculates the SHA1 sum of a file, given by its path.

    path (string): path of the file we are interested in.

    return (string): SHA1 sum of the file in path.

    """
    buffer_length = 8192
    with io.open(path, 'rb') as fin:
        hasher = hashlib.new("sha1")
        buf = fin.read(buffer_length)
        while len(buf) > 0:
            hasher.update(buf)
            buf = fin.read(buffer_length)
        return bin_to_hex(hasher.digest())


# Taken from
# http://stackoverflow.com/questions/1158076/implement-touch-using-python
def touch(path):
    """Touch path, which must be regular file.

    This behaves like the UNIX touch utility.

    path (str): the path to be touched.

    """
    with io.open(path, 'ab'):
        os.utime(path, None)
