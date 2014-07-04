#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2013 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""Tests for the initialization routines.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import unittest

from cms import LANGUAGES, DEFAULT_LANGUAGES, LANGUAGE_NAMES, \
    LANGUAGE_TO_SOURCE_EXT_MAP, LANGUAGE_TO_HEADER_EXT_MAP, \
    SOURCE_EXT_TO_LANGUAGE_MAP


class TestCmsInit(unittest.TestCase):

    def test_languages(self):
        # All languages are described.
        for lang in LANGUAGES:
            assert lang in LANGUAGE_NAMES
            assert lang in LANGUAGE_TO_SOURCE_EXT_MAP
            # This isn't true, as not all languages need headers.
            # assert lang in LANGUAGE_TO_HEADER_EXT_MAP
        # All default languages are languages.
        for lang in DEFAULT_LANGUAGES:
            assert lang in LANGUAGES
        # All keys are languages.
        for lang in LANGUAGE_TO_SOURCE_EXT_MAP.iterkeys():
            assert lang in LANGUAGES
        for lang in LANGUAGE_TO_HEADER_EXT_MAP.iterkeys():
            assert lang in LANGUAGES
        # All values are languages.
        for lang in SOURCE_EXT_TO_LANGUAGE_MAP.itervalues():
            assert lang in LANGUAGES
        # Extensions are sane.
        for lang in LANGUAGES:
            assert LANGUAGE_TO_SOURCE_EXT_MAP[lang][0] == "."
            assert lang == \
                SOURCE_EXT_TO_LANGUAGE_MAP[LANGUAGE_TO_SOURCE_EXT_MAP[lang]]
        for ext in SOURCE_EXT_TO_LANGUAGE_MAP:
            assert ext[0] == "."


if __name__ == "__main__":
    unittest.main()
