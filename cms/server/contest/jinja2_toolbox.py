#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""Provide a Jinja2 environment tailored to CWS.

Extend the global generic Jinja2 environment to inject tools that are
useful specifically to the use that CWS makes of it.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *
from future.builtins import *

from jinja2 import PackageLoader

from cms.server.jinja2_toolbox import GLOBAL_ENVIRONMENT


CWS_ENVIRONMENT = GLOBAL_ENVIRONMENT.overlay(
    # Allow the use of {% trans %} tags to localize strings.
    extensions=['jinja2.ext.i18n'],
    # Load templates from CWS's package (use package rather than file
    # system as that works even in case of a compressed distribution).
    loader=PackageLoader('cms.server.contest', 'templates'))
# This compresses all leading/trailing whitespace and line breaks of
# internationalized messages when translating and extracting them.
CWS_ENVIRONMENT.policies['ext.i18n.trimmed'] = True
