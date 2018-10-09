#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2012 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2013-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2013-2016 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Luca Versari <veluca93@gmail.com>
# Copyright © 2014 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2016 Peyman Jabbarzade Ganje <peyman.jabarzade@gmail.com>
# Copyright © 2017 Luca Chiodini <luca@chiodini.org>
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

import logging
import subprocess


logger = logging.getLogger(__name__)


# CONFIG is populated by our test script.
CONFIG = {
    'VERBOSITY': 0,
}


class TestException(Exception):
    pass


def sh(cmdline, ignore_failure=False):
    """Execute a simple shell command.

    If cmdline is a string, it is passed to sh -c verbatim.  All escaping must
    be performed by the user. If cmdline is an array, then no escaping is
    required.

    """
    if CONFIG["VERBOSITY"] >= 1:
        # TODO Use shlex.quote in Python 3.3.
        logger.info('$ %s', ' '.join(cmdline))
    kwargs = dict()
    if CONFIG["VERBOSITY"] >= 3:
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.STDOUT
    ret = subprocess.call(cmdline, **kwargs)
    if not ignore_failure and ret != 0:
        raise TestException(
            # TODO Use shlex.quote in Python 3.3.
            "Execution failed with %d/%d. Tried to execute:\n%s\n" %
            (ret & 0xff, ret >> 8, ' '.join(cmdline)))
