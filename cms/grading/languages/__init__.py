#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2016 Stefano Maggiolo <s.maggiolo@gmail.com>
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

import logging

from cms import plugin_lookup


logger = logging.getLogger(__name__)


def get_language_class(name):
    """Load the Language subclass given as parameter."""
    return plugin_lookup(name, "cms.grading.languages", "languages")


def get_language(name=None):
    """Construct the Language specified by parameters.

    name (unicode): the name of the Language class.

    return (Language): an instance of the correct Language class.

    raise (ValueError): when there is no such language.

    """
    class_ = get_language_class(name)
    return class_()
