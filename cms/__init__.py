#!/usr/bin/env python3

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

# As this package initialization code is run by all code that imports
# something in cms.* it's the best place to setup the logging handlers.
# By importing the log module we install a handler on stdout. Other
# handlers will be added by services by calling initialize_logging.
import cms.log


# Define what this package will provide.

__all__ = [
    "__version__",
    "TOKEN_MODE_DISABLED", "TOKEN_MODE_FINITE", "TOKEN_MODE_INFINITE",
    "TOKEN_MODE_MIXED",
    "FEEDBACK_LEVEL_FULL", "FEEDBACK_LEVEL_RESTRICTED",
    # log
    # Nothing intended for external use, no need to advertise anything.
    # conf
    "Address", "ServiceCoord", "ConfigError", "async_config", "config",
    # util
    "mkdir", "rmtree", "utf8_decoder", "get_safe_shard", "get_service_address",
    "get_service_shards", "contest_id_from_args", "default_argument_parser",
    # plugin
    "plugin_list",
]


__version__ = "1.5.0"


# Instantiate or import these objects.


# Token modes.

TOKEN_MODE_DISABLED = "disabled"
TOKEN_MODE_FINITE = "finite"
TOKEN_MODE_INFINITE = "infinite"
# Only used when aggregating modes (e.g., for all tasks of a contest).
# Acts as a "none of the above".
TOKEN_MODE_MIXED = "mixed"

# Feedback level.

# Full information (killing signals, time and memory, status for all
# testcases).
FEEDBACK_LEVEL_FULL = "full"
# Restricted set of information (no killing signal, time or memory, testcases
# can be omitted).
FEEDBACK_LEVEL_RESTRICTED = "restricted"


from .conf import Address, ServiceCoord, ConfigError, async_config, config
from .util import mkdir, rmtree, utf8_decoder, get_safe_shard, \
    get_service_address, get_service_shards, contest_id_from_args, \
    default_argument_parser
from .plugin import plugin_list
