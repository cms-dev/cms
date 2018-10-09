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

"""Utilities for standardized runs (steps)."""

import logging

from cms.grading.Sandbox import Sandbox
from .stats import execution_stats, merge_execution_stats


logger = logging.getLogger(__name__)


def _generic_execution(sandbox, command, exec_num, step_name,
                       collect_output=False):
    """A single command execution of a multi-command step.

    sandbox (Sandbox): the sandbox to use, already created and configured.
    command ([str]): command to execute.
    exec_num (int): 0-based index of the execution, to be used not to
        overwrite the output files.
    step_name (str): name of the step, also used as a prefix for the stdout
        and stderr files.
    collect_output (bool): if True, stats will contain stdout and stderr of the
        command (regardless, they are redirected to file inside the sandbox).

    return (dict|None): execution statistics, including standard output and
        error, or None in case of an unexpected sandbox error.

    """
    sandbox.stdout_file = "%s_stdout_%d.txt" % (step_name, exec_num)
    sandbox.stderr_file = "%s_stderr_%d.txt" % (step_name, exec_num)

    box_success = sandbox.execute_without_std(command, wait=True)
    if not box_success:
        logger.error("Step '%s' aborted because of sandbox error in '%s' on "
                     "the %d-th command ('%r').",
                     step_name, sandbox.get_root_path(), exec_num + 1, command)
        return None

    return execution_stats(sandbox, collect_output=collect_output)


def generic_step(sandbox, commands, step_name, collect_output=False):
    """Execute some commands in the sandbox.

    Execute the commands sequentially in the (already created and configured)
    sandbox.

    Terminate early after a command if the sandbox fails, or the command does
    not terminate normally and with exit code 0.

    sandbox (Sandbox): the sandbox we consider, already created.
    commands ([[str]]): compilation commands to execute.
    step_name (str): used for logging and as a prefix to the output files
    collect_output (bool): if True, stats will contain stdout and stderr of the
        commands (regardless, they are redirected to file inside the sandbox).

    return (dict|None): execution statistics, including standard output and
        error, or None in case of an unexpected sandbox error.

    """
    logger.debug("Starting step '%s' in sandbox '%s' (%d commands).",
                 step_name, sandbox.get_root_path(), len(commands))
    stats = None
    for exec_num, command in enumerate(commands):
        this_stats = _generic_execution(sandbox, command, exec_num, step_name,
                                        collect_output=collect_output)
        # Sandbox error, return immediately.
        if this_stats is None:
            return None

        stats = merge_execution_stats(stats, this_stats, concurrent=False)
        # Command error, also return immediately, but returning the stats.
        if stats["exit_status"] != Sandbox.EXIT_OK:
            break

    return stats
