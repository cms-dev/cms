#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2015 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2013-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
# Copyright © 2016 Amir Keivan Mohtashami <akmohtashami97@gmail.com>
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

"""Computing and merging statistics about command executions in the sandbox."""

from cms.grading.Sandbox import Sandbox


# TODO: stats grew enough to justify having a proper object representing them.


def execution_stats(sandbox, collect_output=False):
    """Extract statistics from a sandbox about the last ran command.

    sandbox (Sandbox): the sandbox to inspect.
    collect_output (bool): whether to collect output from the sandbox
        stdout_file and stderr_file.

    return (dict): a dictionary with statistics.

    """
    stats = {
        "execution_time": sandbox.get_execution_time(),
        "execution_wall_clock_time": sandbox.get_execution_wall_clock_time(),
        "execution_memory": sandbox.get_memory_used(),
        "exit_status": sandbox.get_exit_status(),
    }
    if stats["exit_status"] == Sandbox.EXIT_SIGNAL:
        stats["signal"] = sandbox.get_killing_signal()

    if collect_output:
        stats["stdout"] = sandbox.get_file_to_string(sandbox.stdout_file)\
            .decode("utf-8", errors="replace").strip()
        stats["stderr"] = sandbox.get_file_to_string(sandbox.stderr_file)\
            .decode("utf-8", errors="replace").strip()

    return stats


def merge_execution_stats(first_stats, second_stats, concurrent=True):
    """Merge two execution statistics dictionary.

    The first input stats can be None, in which case the second stats is copied
    to the output (useful to treat the first merge of a sequence in the same
    way as the others).

    first_stats (dict|None): statistics about the first execution; contains
        execution_time, execution_wall_clock_time, execution_memory,
        exit_status, and possibly signal.
    second_stats (dict): same for the second execution.
    concurrent (bool): whether to merge using assuming the executions were
        concurrent or not (see return value).

    return (dict): the merged statistics, using the following algorithm:
        * execution times are added;
        * memory usages are added (if concurrent) or max'd (if not);
        * wall clock times are max'd (if concurrent) or added (if not);
        * exit_status and related values (signal) are from the first non-OK,
            if present, or OK;
        * stdout and stderr, if present, are joined with a separator line.

    raise (ValueError): if second_stats is None.

    """
    if second_stats is None:
        raise ValueError("The second input stats cannot be None.")
    if first_stats is None:
        return second_stats.copy()

    ret = first_stats.copy()
    ret["execution_time"] += second_stats["execution_time"]

    if concurrent:
        ret["execution_wall_clock_time"] = max(
            ret["execution_wall_clock_time"],
            second_stats["execution_wall_clock_time"])
        ret["execution_memory"] += second_stats["execution_memory"]
    else:
        ret["execution_wall_clock_time"] += \
            second_stats["execution_wall_clock_time"]
        ret["execution_memory"] = max(ret["execution_memory"],
                                      second_stats["execution_memory"])

    if first_stats["exit_status"] == Sandbox.EXIT_OK:
        ret["exit_status"] = second_stats["exit_status"]
        if second_stats["exit_status"] == Sandbox.EXIT_SIGNAL:
            ret["signal"] = second_stats["signal"]

    for f in ["stdout", "stderr"]:
        if f in ret or f in second_stats:
            ret[f] = "\n===\n".join(d[f]
                                    for d in [ret, second_stats]
                                    if f in d)

    return ret
