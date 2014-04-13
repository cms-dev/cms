#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2012 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Stefano Maggiolo <s.maggiolo@gmail.com>
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

import os.path
from xml.sax import parse
from xml.sax.handler import ContentHandler


__all__ = [
    "is_language_code", "translate_language_code",
    "is_country_code", "translate_country_code",
    "is_language_country_code", "translate_country_code",
    ]


# We need the config to access the iso_codes_prefix value. It would be
# better not to depend on cms (i.e. be standalone). The best solution
# would be to get the prefix at installation-time (using pkgconfig),
# like many C libraries/applications do, and store it somehow. Yet, I
# don't know what's the best way to do this in Python...
from cms import config


class _make_dict (ContentHandler):
    def __init__(self, path, key, value, result):
        self.path = path
        self.key = key
        self.value = value
        self.index = 0
        self.result = result

    def startElement(self, name, attrs):
        if self.index < len(self.path) and name == self.path[self.index]:
            self.index += 1
        if self.index == len(self.path):
            if self.key in attrs and self.value in attrs:
                self.result[attrs[self.key]] = attrs[self.value]

    def endElement(self, name):
        if self.index > 0 and name == self.path[self.index - 1]:
            self.index -= 1


_language_codes = dict()
_country_codes = dict()

parse(os.path.join(config.iso_codes_prefix,
                   'share', 'xml', 'iso-codes', 'iso_639.xml'),
      _make_dict(["iso_639_entries", "iso_639_entry"],
                 "iso_639_1_code", "name", _language_codes))
parse(os.path.join(config.iso_codes_prefix,
                   'share', 'xml', 'iso-codes', 'iso_3166.xml'),
      _make_dict(["iso_3166_entries", "iso_3166_entry"],
                 "alpha_2_code", "name", _country_codes))


def is_language_code(code):
    return code in _language_codes


def translate_language_code(code, locale):
    if code not in _language_codes:
        raise ValueError("Language code not recognized.")

    return locale.translate(_language_codes[code]).split(';')[0]


def is_country_code(code):
    return code in _country_codes


def translate_country_code(code, locale):
    if code not in _country_codes:
        raise ValueError("Country code not recognized.")

    return locale.translate(_country_codes[code]).split(';')[0]


def is_language_country_code(code):
    tokens = code.split('_')
    if len(tokens) != 2 or \
            tokens[0] not in _language_codes or \
            tokens[1] not in _country_codes:
        return False
    return True


def translate_language_country_code(code, locale):
    tokens = code.split('_')
    if len(tokens) != 2 or \
            tokens[0] not in _language_codes or \
            tokens[1] not in _country_codes:
        raise ValueError("Language and country code not recognized.")

    return "%s (%s)" % (translate_language_code(tokens[0], locale),
                        translate_country_code(tokens[1], locale))
