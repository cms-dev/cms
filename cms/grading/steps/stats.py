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

import re
from cms.grading.Sandbox import Sandbox
import typing


# TODO: stats grew enough to justify having a proper object representing them.


# is this a proper enough object? :)
class StatsDict(typing.TypedDict):
    execution_time: float | None
    execution_wall_clock_time: float | None
    execution_memory: int | None
    exit_status: str
    signal: typing.NotRequired[int]
    stdout: typing.NotRequired[str]
    stderr: typing.NotRequired[str]


def execution_stats(sandbox: Sandbox, collect_output: bool = False) -> StatsDict:
    """Extract statistics from a sandbox about the last ran command.

    sandbox: the sandbox to inspect.
    collect_output: whether to collect output from the sandbox
        stdout_file and stderr_file.

    return: a dictionary with statistics.

    """
    stats: StatsDict = {
        "execution_time": sandbox.get_execution_time(),
        "execution_wall_clock_time": sandbox.get_execution_wall_clock_time(),
        "execution_memory": sandbox.get_memory_used(),
        "exit_status": sandbox.get_exit_status(),
    }
    if stats["exit_status"] == Sandbox.EXIT_SIGNAL:
        stats["signal"] = sandbox.get_killing_signal()

    if collect_output:
        def safe_get_str(filename: str) -> str:
            s = sandbox.get_file_to_string(filename)
            s = s.decode("utf-8", errors="replace")
            s = re.sub('[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\xbf]', '\ufffd', s)
            s = s.strip()
            return s
        stats["stdout"] = safe_get_str(sandbox.stdout_file)
        stats["stderr"] = safe_get_str(sandbox.stderr_file)

    return stats


def merge_execution_stats(
    first_stats: StatsDict | None, second_stats: StatsDict, concurrent: bool = True
) -> StatsDict:
    """Merge two execution statistics dictionary.

    The first input stats can be None, in which case the second stats is copied
    to the output (useful to treat the first merge of a sequence in the same
    way as the others).

    first_stats: statistics about the first execution; contains
        execution_time, execution_wall_clock_time, execution_memory,
        exit_status, and possibly signal.
    second_stats: same for the second execution.
    concurrent: whether to merge using assuming the executions were
        concurrent or not (see return value).

    return: the merged statistics, using the following algorithm:
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

    Stat = typing.TypeVar('Stat', int, float)

    def safe_sum(x: Stat | None, y: Stat | None) -> Stat | None:
        if x is None:
            return y
        elif y is None:
            return x
        else:
            return x + y

    def safe_max(x: Stat | None, y: Stat | None) -> Stat | None:
        if x is None:
            return y
        elif y is None:
            return x
        else:
            return max(x, y)

    ret = first_stats.copy()
    ret["execution_time"] = safe_sum(ret["execution_time"],
                                     second_stats["execution_time"])

    if concurrent:
        ret["execution_wall_clock_time"] = safe_max(
            ret["execution_wall_clock_time"],
            second_stats["execution_wall_clock_time"])
        ret["execution_memory"] = safe_sum(ret["execution_memory"],
                                           second_stats["execution_memory"])
    else:
        ret["execution_wall_clock_time"] = safe_sum(
            ret["execution_wall_clock_time"],
            second_stats["execution_wall_clock_time"])
        ret["execution_memory"] = safe_max(ret["execution_memory"],
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
