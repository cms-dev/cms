#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

"""High level functions to perform standardized compilations."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa

import logging
import os

from .messages import HumanMessage, MessageCollection
from .stats import execution_stats, merge_execution_stats

from cms.grading.Sandbox import Sandbox


logger = logging.getLogger(__name__)


# Dummy function to mark translatable strings.
def N_(message):
    return message


COMPILATION_MESSAGES = MessageCollection([
    HumanMessage("success",
                 N_("Compilation succeeded"),
                 N_("Your submission successfully compiled to an excutable.")),
    HumanMessage("fail",
                 N_("Compilation failed"),
                 N_("Your submission did not compile correctly.")),
    HumanMessage("timeout",
                 N_("Compilation timed out"),
                 N_("Your submission exceeded the time limit while compiling. "
                    "This might be caused by an excessive use of C++ "
                    "templates, for example.")),
    HumanMessage("signal",
                 N_("Compilation killed with signal %s (could be triggered "
                    "by violating memory limits)"),
                 N_("Your submission was killed with the specified signal. "
                    "Among other things, this might be caused by exceeding "
                    "the memory limit for the compilation, and in turn by an "
                    "excessive use of C++ templates, for example.")),
])


def compilation_step(sandbox, commands):
    """Execute some compilation commands in the sandbox.

    Execute the commands sequentially in the (already created) sandbox, after
    setting up an environment suitable for compilations (additional visible
    directories, appropriate limits).

    Terminate early after a command if the sandbox fails, or the command does
    not terminate normally and with exit code 0.

    sandbox (Sandbox): the sandbox we consider, already created.
    commands ([[str]]): compilation commands to execute.

    return ((bool, bool|None, [str]|None, dict|None)): a tuple with four items:
        * success: True if the sandbox did not fail, in any command;
        * compilation success: True if the compilation resulted in an
            executable, False if not, None if success is False;
        * text: a human readable, localized message to inform contestants
            of the status; it is either an empty list (for no message) or a
            list of strings were the second to the last are formatting
            arguments for the first, or None if success is False;
        * stats: a dictionary with statistics about the compilation, or None
            if success is False.

    """
    # Set sandbox parameters suitable for compilation.
    sandbox.dirs += [("/etc", None, None)]
    # We need to add "/var/lib/ghc" to the unrestricted dirs so GHC can access
    # haskell's package database.
    # GHC looks for it in "/usr/lib/ghc/package.conf.d", which is only a
    # symlink to "/var/lib/ghc/package.conf.d"
    ghc_dir = "/var/lib/ghc"
    if os.path.exists(ghc_dir):
        sandbox.dirs += [("/var/lib/ghc", None, None)]
    sandbox.preserve_env = True
    sandbox.max_processes = None
    sandbox.timeout = 10
    sandbox.wallclock_timeout = 20
    sandbox.address_space = 512 * 1024

    # Actually run the compilation commands, logging stdout and stderr.
    logger.debug("Starting compilation step.")
    stdouts = []
    stderrs = []
    stats = None
    for step, command in enumerate(commands):
        # Keep stdout and stderr of each compilation step
        sandbox.stdout_file = "compiler_stdout_%d.txt" % step
        sandbox.stderr_file = "compiler_stderr_%d.txt" % step

        box_success = sandbox.execute_without_std(command, wait=True)
        if not box_success:
            logger.error("Compilation aborted because of "
                         "sandbox error in `%s'.", sandbox.path)
            return False, None, None, None

        stdout = sandbox.get_file_to_string(sandbox.stdout_file)\
            .decode("utf-8", errors="replace").strip()
        if len(stdout) > 0:
            stdouts.append(stdout)
        stderr = sandbox.get_file_to_string(sandbox.stderr_file)\
            .decode("utf-8", errors="replace").strip()
        if len(stderr) > 0:
            stderrs.append(stderr)

        this_stats = execution_stats(sandbox)
        if stats is None:
            stats = this_stats
        else:
            stats = merge_execution_stats(stats, this_stats, concurrent=False)

        # If some command in the sequence has failed, we terminate early.
        if stats["exit_status"] != Sandbox.EXIT_OK:
            break

    # Add output to the statistics.
    stats["stdout"] = '\n===\n'.join(stdouts)
    stats["stderr"] = '\n===\n'.join(stderrs)

    # For each possible exit status we return an appropriate result.
    exit_status = stats["exit_status"]

    if exit_status == Sandbox.EXIT_OK:
        # Execution finished successfully and the executable was generated.
        logger.debug("Compilation successfully finished.")
        text = [COMPILATION_MESSAGES.get("success").message]
        return True, True, text, stats

    elif exit_status == Sandbox.EXIT_NONZERO_RETURN:
        # Error in compilation: no executable was generated, and we return
        # an error to the user.
        logger.debug("Compilation failed.")
        text = [COMPILATION_MESSAGES.get("fail").message]
        return True, False, text, stats

    elif exit_status == Sandbox.EXIT_TIMEOUT or \
            exit_status == Sandbox.EXIT_TIMEOUT_WALL:
        # Timeout: we assume it is the user's fault, and we return the error
        # to them.
        logger.debug("Compilation timed out.")
        text = [COMPILATION_MESSAGES.get("timeout").message]
        return True, False, text, stats

    elif exit_status == Sandbox.EXIT_SIGNAL:
        # Terminated by signal: we assume again it is the user's fault, and
        # we return the error to them.
        signal = stats["signal"]
        logger.debug("Compilation killed with signal %s.", signal)
        text = [COMPILATION_MESSAGES.get("signal").message, str(signal)]
        return True, False, text, stats

    elif exit_status == Sandbox.EXIT_SANDBOX_ERROR:
        # We shouldn't arrive here, as we should have gotten a False success
        # from execute_without_std.
        logger.error("Unexpected SANDBOX_ERROR exit status.")
        return False, None, None, None

    else:
        logger.error("Unrecognized sandbox exit status '%s'.", exit_status)
        return False, None, None, None
