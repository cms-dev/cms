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
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa

import io
import os.path

import xdg.BaseDirectory
import xdg.Mime


__all__ = [
    "get_icon_for_type", "get_name_for_type",
    "get_type_for_file_name",
    ]


def _retrieve_icons():
    res = dict()
    for d in reversed([xdg.BaseDirectory.xdg_data_home]
                      + xdg.BaseDirectory.xdg_data_dirs):
        try:
            with io.open(os.path.join(d, "mime", "generic-icons"), "rt") as f:
                res.update(tuple(l.strip().split(':')) for l in f.readlines())
        except IOError as err:
            if err.errno != errno.ENOENT:
                raise
    return res


_icons = _retrieve_icons()


def get_icon_for_type(typename):
    """Get a generic icon name for the given MIME type.

    typename (str): a MIME type, e.g., "application/pdf".

    return (str): the generic icon that best depicts the given MIME
        type, e.g., "x-office-document".

    """
    mimetype = xdg.Mime.lookup(typename).canonical()
    typename = "%s/%s" % (mimetype.media, mimetype.subtype)
    if typename in _icons:
        return _icons[typename]
    return mimetype.media + "-x-generic"


def get_name_for_type(typename):
    """Get the natural language description of the MIME type.

    typename (str): a MIME type, e.g., "application/pdf".

    return (str): the human-readable description (also called comment)
        of the given MIME type, e.g., "PDF document".

    """
    mimetype = xdg.Mime.lookup(typename).canonical()
    return mimetype.get_comment()


def get_type_for_file_name(filename):
    """Guess the MIME type of a file given its name.

    filename (str): the name of a file (just the base name, without the
        directory name), e.g., "statement.pdf".

    return (str|None): a guess of what MIME type that file might have,
        e.g., "application/pdf".

    """
    mimetype = xdg.Mime.get_type_by_name(filename).canonical()
    if mimetype is None:
        return None
    return "%s/%s" % (mimetype.media, mimetype.subtype)
