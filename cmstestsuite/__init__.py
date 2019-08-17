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

from cmscommon.commands import pretty_print_cmdline


logger = logging.getLogger(__name__)


# CONFIG is populated by our test script.
CONFIG = {
    'VERBOSITY': 0,
}


class TestException(Exception):
    pass


def sh(cmdline, ignore_failure=False):
    """Execute a simple command.

    cmd ([str]): the (unescaped) command to execute.
    ignore_failure (bool): whether to suppress failures.

    raise (TestException): if the command failed and ignore_failure was False.

    """
    if CONFIG["VERBOSITY"] >= 1:
        logger.info('$ %s', pretty_print_cmdline(cmdline))
    kwargs = dict()
    if CONFIG["VERBOSITY"] >= 3:
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.STDOUT
    kwargs["check"] = not ignore_failure
    try:
        subprocess.run(cmdline, **kwargs)
    except subprocess.CalledProcessError as e:
        raise TestException("Execution failed") from e
