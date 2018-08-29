#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

# As this package initialization code is run by all code that imports
# something in cms.* it's the best place to setup the logging handlers.
# By importing the log module we install a handler on stdout. Other
# handlers will be added by services by calling initialize_logging.
import cms.log


# Define what this package will provide.

__all__ = [
    "__version__",
    "SCORE_MODE_MAX", "SCORE_MODE_MAX_TOKENED_LAST",
    # log
    # Nothing intended for external use, no need to advertise anything.
    # util
    "ConfigError", "mkdir", "utf8_decoder", "Address", "ServiceCoord",
    "get_safe_shard", "get_service_address", "get_service_shards",
    "default_argument_parser",
    # conf
    "config",
    # plugin
    "plugin_list", "plugin_lookup",
]


__version__ = '1.3.2'


# Instantiate or import these objects.


# Task score modes.

# Maximum score amongst all submissions.
SCORE_MODE_MAX = "max"
# Maximum score among all tokened submissions and the last submission.
SCORE_MODE_MAX_TOKENED_LAST = "max_tokened_last"

from .util import ConfigError, mkdir, utf8_decoder, Address, ServiceCoord, \
    get_safe_shard, get_service_address, get_service_shards, \
    default_argument_parser
from .conf import config
from .plugin import plugin_list, plugin_lookup
