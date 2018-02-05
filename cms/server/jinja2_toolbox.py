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

"""Provide a generic Jinja2 environment.

Create a Jinja2 environment and instrument it with utilities (globals,
filters, tests, etc. that are useful for generic global usage.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *
from future.builtins import *

from jinja2 import Environment, StrictUndefined


GLOBAL_ENVIRONMENT = Environment(
    # These cause a line that only contains a control block to be
    # suppressed from the output, making it more readable.
    trim_blocks=True, lstrip_blocks=True,
    # This causes an error when we try to render an undefined value.
    undefined=StrictUndefined,
    # Force autoescape of string, always and forever.
    autoescape=True,
    # Cache all templates, no matter how many.
    cache_size=-1,
    # Don't check the disk every time to see whether the templates'
    # files have changed.
    auto_reload=False)
