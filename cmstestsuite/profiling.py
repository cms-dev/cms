#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Profiling utils for the testsuites.

There are several Python profilers out there, but many of them have problems,
are not maintained, or are not greenlet-aware. We selected two that work
reasonably well: yappi (`pip install yappi`,
https://bitbucket.org/sumerc/yappi/) and kernprof (`pip install line_profiler`,
https://github.com/rkern/line_profiler).

Yappi was developed exactly due to the missing multithreading support of the
official profilers, and is designed for long-running applications (as are CMS'
services). After running a test with yappi enabled, .prof files will be
generated for each service, and they can be inspected with pstats or the handy
cprofilev, or with kcachegrind using `pip install pyprof2calltree` and
`pyprof2calltree -i output.prof -k`.

Kernprof offers instead a greenlet-aware line profiler whose output might be
easier to understand than yappi's, but requires @profile annotations on
functions or methods. The output will be in .lprof files, that can be inspected
using `python -m line_profile output.lprof`

"""

from cmstestsuite import CONFIG


PROFILER_NONE = ""
PROFILER_YAPPI = "yappi"
PROFILER_KERNPROF = "kernprof"


_YAPPI_CMDLINE = ["yappi", "-o", "%(output_basename)s.prof"]
_KERNPROF_CMDLINE = [
    "kernprof", "-l", "-o", "%(output_basename)s.lprof"]


def _format_cmdline(profiler_cmdline, cmdline, output_basename):
    return [
        token % {"output_basename": output_basename}
        for token in profiler_cmdline
    ] + cmdline


def profiling_cmdline(cmdline, output_basename):
    """Return a cmdline possibly decorated to record profiling information."""
    profiler = CONFIG.get("PROFILER", PROFILER_NONE)
    if profiler == PROFILER_NONE:
        return cmdline
    elif profiler == PROFILER_YAPPI:
        return _format_cmdline(_YAPPI_CMDLINE, cmdline, output_basename)
    elif profiler == PROFILER_KERNPROF:
        return _format_cmdline(_KERNPROF_CMDLINE, cmdline, output_basename)
    else:
        raise ValueError("Unknown profiler %s" % profiler)
