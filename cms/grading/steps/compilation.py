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

"""High level functions to perform standardized compilations."""

import logging

from cms import config
from cms.grading.Sandbox import Sandbox
from cms.grading.steps.stats import StatsDict
from .messages import HumanMessage, MessageCollection
from .utils import generic_step


logger = logging.getLogger(__name__)


# Dummy function to mark translatable strings.
def N_(message: str):
    return message


COMPILATION_MESSAGES = MessageCollection("compilation", [
    HumanMessage("success",
                 N_("Compilation succeeded"),
                 N_("Your submission successfully compiled to an "
                    "executable.")),
    HumanMessage("fail",
                 N_("Compilation failed"),
                 N_("Your submission did not compile correctly.")),
    HumanMessage("timeout",
                 N_("Compilation timed out"),
                 N_("Your submission exceeded the time limit while compiling. "
                    "This might be caused by an excessive use of C++ "
                    "templates, for example."),
                 inline_help=True),
    HumanMessage("memorylimit",
                 N_("Compilation memory limit exceeded"),
                 N_("Your submission exceeded the memory limit while compiling. "
                    "This might be caused by an excessive use of C++ "
                    "templates, or too large global variables, for example."),
                 inline_help=True),
    HumanMessage("signal",
                 N_("Compilation killed with signal %s"),
                 N_("Your submission was killed with the specified signal. "
                    "This might be caused by a bug in the compiler, "
                    "for example."),
                 inline_help=True),
])


def compilation_step(
    sandbox: Sandbox, commands: list[list[str]]
) -> tuple[bool, bool | None, list[str] | None, StatsDict | None]:
    """Execute some compilation commands in the sandbox.

    Execute the commands sequentially in the (already created) sandbox, after
    setting up an environment suitable for compilations (additional visible
    directories, appropriate limits).

    Terminate early after a command if the sandbox fails, or the command does
    not terminate normally and with exit code 0.

    sandbox: the sandbox we consider, already created.
    commands: compilation commands to execute.

    return: a tuple with four items:
        * success: True if the sandbox did not fail, in any command;
        * compilation success: True if the compilation resulted in an
            executable, False if not, None if success is False;
        * text: a human readable, localized message to inform contestants
            of the status; it is either an empty list (for no message) or a
            list of strings were the first is a message ID and the rest are
            format arguments for that message, if the message takes any; or
            None if success is False;
        * stats: a dictionary with statistics about the compilation, or None
            if success is False.

    """
    # Set sandbox parameters suitable for compilation.
    sandbox.add_mapped_directory("/etc")
    # Directory required to be visible during a compilation with GHC.
    # GHC looks for the Haskell's package database in
    # "/usr/lib/ghc/package.conf.d" (already visible by isolate's default,
    # but it is a symlink to "/var/lib/ghc/package.conf.d"
    sandbox.maybe_add_mapped_directory("/var/lib/ghc")
    sandbox.preserve_env = True
    sandbox.max_processes = config.sandbox.compilation_sandbox_max_processes
    sandbox.timeout = config.sandbox.compilation_sandbox_max_time_s
    sandbox.wallclock_timeout = 2 * sandbox.timeout + 1
    sandbox.address_space = config.sandbox.compilation_sandbox_max_memory_kib * 1024

    # Run the compilation commands, copying stdout and stderr to stats.
    stats = generic_step(sandbox, commands, "compilation", collect_output=True)
    if stats is None:
        logger.error("Sandbox failed during compilation. "
                     "See previous logs for the reason.")
        return False, None, None, None

    # For each possible exit status we return an appropriate result.
    exit_status = stats["exit_status"]

    if exit_status == Sandbox.EXIT_OK:
        # Execution finished successfully and the executable was generated.
        logger.debug("Compilation successfully finished.")
        text = ["compilation:success"]
        return True, True, text, stats

    elif exit_status == Sandbox.EXIT_NONZERO_RETURN:
        # Error in compilation: no executable was generated, and we return
        # an error to the user.
        logger.debug("Compilation failed.")
        text = ["compilation:fail"]
        return True, False, text, stats

    elif exit_status == Sandbox.EXIT_TIMEOUT or \
            exit_status == Sandbox.EXIT_TIMEOUT_WALL:
        # Timeout: we assume it is the user's fault, and we return the error
        # to them.
        logger.debug("Compilation timed out.")
        text = ["compilation:timeout"]
        return True, False, text, stats

    elif exit_status == Sandbox.EXIT_MEM_LIMIT:
        # Memory limit: we assume it is the user's fault, and we return the
        # error to them.
        logger.debug("Compilation memory limit exceeded.")
        text = ["compilation:memorylimit"]
        return True, False, text, stats

    elif exit_status == Sandbox.EXIT_SIGNAL:
        # Terminated by signal: we assume again it is the user's fault, and
        # we return the error to them.
        signal = stats["signal"]
        logger.debug("Compilation killed with signal %s.", signal)
        text = ["compilation:signal", str(signal)]
        return True, False, text, stats

    elif exit_status == Sandbox.EXIT_SANDBOX_ERROR:
        # We shouldn't arrive here, as we should have gotten a False success
        # from execute_without_std.
        logger.error("Unexpected SANDBOX_ERROR exit status.")
        return False, None, None, None

    else:
        logger.error("Unrecognized sandbox exit status '%s'.", exit_status)
        return False, None, None, None
