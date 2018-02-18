#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
from future.builtins.disabled import *
from future.builtins import *

import io
import os.path

import xdg.BaseDirectory
import xdg.Mime


__all__ = [
    "get_icon_for_type", "get_name_for_type",
    "get_type_for_file_name",
    ]


_icons = dict()


for d in reversed([xdg.BaseDirectory.xdg_data_home]
                  + xdg.BaseDirectory.xdg_data_dirs):
    try:
        with io.open(os.path.join(d, "mime", "generic-icons"), "rt") as f:
            _icons.update(tuple(l.strip().split(':')) for l in f.readlines())
    except IOError as err:
        if err.errno != errno.ENOENT:
            raise


def get_icon_for_type(typename):
    mimetype = xdg.Mime.lookup(typename).canonical()
    typename = "%s/%s" % (mimetype.media, mimetype.subtype)
    if typename in _icons:
        return _icons[typename]
    return mimetype.media + "-x-generic"


def get_name_for_type(typename):
    mimetype = xdg.Mime.lookup(typename).canonical()
    return mimetype.get_comment()


def get_type_for_file_name(filename):
    mimetype = xdg.Mime.get_type_by_name(filename).canonical()
    if mimetype is None:
        return None
    return "%s/%s" % (mimetype.media, mimetype.subtype)
