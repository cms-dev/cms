#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2012 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2013-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2013-2016 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Luca Versari <veluca93@gmail.com>
# Copyright © 2014-2022 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2016 Peyman Jabbarzade Ganje <peyman.jabarzade@gmail.com>
# Copyright © 2017 Luca Chiodini <luca@chiodini.org>
# Copyright © 2021 Andrey Vihrov <andrey.vihrov@gmail.com>
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
import sys

from cmstestsuite import CONFIG, sh


logger = logging.getLogger(__name__)


_COVERAGE_DIRECTORIES = [
    "cms",
    "cmscommon",
    "cmscontrib",
    "cmsranking",
    "cmstaskenv",
]
_COVERAGE_CMDLINE = [
    sys.executable, "-m", "coverage", "run", "-p",
    "--source=%s" % ",".join(_COVERAGE_DIRECTORIES)]


def coverage_cmdline(cmdline):
    """Return a cmdline possibly decorated to record coverage."""
    if CONFIG.get('COVERAGE', None):
        return _COVERAGE_CMDLINE + cmdline
    else:
        return cmdline


def clear_coverage():
    """Clear existing coverage reports."""
    if CONFIG.get('COVERAGE', None):
        logging.info("Clearing old coverage data.")
        sh([sys.executable, "-m", "coverage", "erase"])


def combine_coverage():
    """Combine coverage reports from different programs."""
    coverage_file = CONFIG.get('COVERAGE', None)

    if coverage_file:
        logger.info("Combining coverage results.")
        sh([sys.executable, "-m", "coverage", "combine"])
        sh([sys.executable, "-m", "coverage", "xml", "-o", coverage_file])
