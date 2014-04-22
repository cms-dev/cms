#!/usr/bin/env python2
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
from __future__ import print_function
from __future__ import unicode_literals

import io
import os.path
import fnmatch
import mimetypes
from xml import sax
from xml.sax.handler import ContentHandler
from xml.dom import XML_NAMESPACE as _XML_NS


__all__ = [
    "get_icon_for_type", "get_name_for_type",
    "get_type_for_file_name",
    ]


_XDG_NS = "http://www.freedesktop.org/standards/shared-mime-info"

# We need the config to access the shared_mime_info_prefix value. It
# would be better not to depend on cms (i.e. be standalone). The best
# solution would be to get the prefix at installation-time (using
# pkgconfig), like many C libraries/applications do, and store it
# somehow. Yet, I don't know what's the best way to do this in Python...
from cms import config


# FIXME the following code doesn't take comments into account.
# FIXME the specification requires to look in XDG_DATA_HOME and
# XDG_DATA_DIRS instead of the installation dir of shared-mime-info...
# TODO use python-xdg (or similar libraries) instead of doing the
# parsing ourselves. they also provide ways to find the MIME type.

_aliases = dict(tuple(l.strip().split()) for l in
                io.open(os.path.join(config.shared_mime_info_prefix,
                                     "share", "mime", "aliases"),
                        "rt", encoding="utf-8").readlines())

_icons = dict(tuple(l.strip().split(':')) for l in
              io.open(os.path.join(config.shared_mime_info_prefix,
                                   "share", "mime", "generic-icons"),
                      "rt", encoding="utf-8").readlines())

_types = list(l.strip() for l in
              io.open(os.path.join(config.shared_mime_info_prefix,
                                   "share", "mime", "types"),
                      "rt", encoding="utf-8").readlines())

_comments = dict()


class _get_comment (ContentHandler):
    def __init__(self):
        self.inside = False
        self.result = None

    def startElementNS(self, name, qname, attrs):
        if name == (_XDG_NS, "comment") and \
                ((_XML_NS, "lang") not in attrs or
                 attrs[(_XML_NS, "lang")] in ["en", "en_US"]):
            self.inside = True
            self.result = ''

    def endElementNS(self, name, qname):
        self.inside = False

    def characters(self, content):
        if self.inside:
            self.result += content


def get_icon_for_type(name):
    if name in _aliases:
        name = _aliases[name]
    if name not in _types:
        return None

    if name in _icons:
        return _icons[name]
    return name[:name.index('/')] + "-x-generic"


def get_name_for_type(name):
    if name in _aliases:
        name = _aliases[name]
    if name not in _types:
        return None

    if name not in _comments:
        try:
            media, subtype = name.split('/')
            path = os.path.join(config.shared_mime_info_prefix,
                                'share', 'mime', media, "%s.xml" % subtype)

            handler = _get_comment()
            parser = sax.make_parser()
            parser.setContentHandler(handler)
            parser.setFeature(sax.handler.feature_namespaces, 1)
            parser.parse(path)

            _comments[name] = handler.result
        except:
            pass

    if name in _comments:
        return _comments[name]


def get_type_for_file_name(name):
    # Provide support for some commonly used types and fallback on
    # Python's mimetypes module. In the future we could be using a
    # proper library here (i.e. an interface to shared-mime-info).
    for glob, mime in [('*.tar.gz', 'application/x-compressed-tar'),
                       ('*.tar.bz2', 'application/x-bzip-compressed-tar'),
                       ('*.c', 'text/x-csrc'),
                       ('*.h', 'text/x-chdr'),
                       ('*.cpp', 'text/x-c++src'),
                       ('*.hpp', 'text/x-c++hdr'),
                       ('*.pas', 'text/x-pascal')]:
        if fnmatch.fnmatchcase(name, glob):
            return mime
    return mimetypes.guess_type(name)[0]
