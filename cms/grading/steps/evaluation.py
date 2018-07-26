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

"""High level functions to perform standardized evaluations."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa

import logging

from .messages import HumanMessage, MessageCollection
from .stats import execution_stats

from cms import FEEDBACK_LEVEL_FULL, FEEDBACK_LEVEL_RESTRICTED, config
from cms.grading.Sandbox import Sandbox


logger = logging.getLogger(__name__)


# Dummy function to mark translatable strings.
def N_(message):
    return message


EVALUATION_MESSAGES = MessageCollection([
    HumanMessage("success",
                 N_("Output is correct"),
                 N_("Your submission ran and gave the correct answer")),
    HumanMessage("partial",
                 N_("Output is partially correct"),
                 N_("Your submission ran and gave the partially correct "
                    "answer")),
    HumanMessage("wrong",
                 N_("Output isn't correct"),
                 N_("Your submission ran, but gave the wrong answer")),
    HumanMessage("nooutput",
                 N_("Evaluation didn't produce file %s"),
                 N_("Your submission ran, but did not write on the "
                    "correct output file")),
    HumanMessage("timeout",
                 N_("Execution timed out"),
                 N_("Your submission used too much CPU time.")),
    HumanMessage("walltimeout",
                 N_("Execution timed out (wall clock limit exceeded)"),
                 N_("Your submission used too much total time. This might "
                    "be triggered by undefined code, or buffer overflow, "
                    "for example. Note that in this case the CPU time "
                    "visible in the submission details might be much smaller "
                    "than the time limit.")),
    HumanMessage("signal",
                 N_("Execution killed with signal %s (could be triggered by "
                    "violating memory limits)"),
                 N_("Your submission was killed with the specified signal. "
                    "Among other things, this might be caused by exceeding "
                    "the memory limit. Note that if this is the reason, "
                    "the memory usage visible in the submission details is "
                    "the usage before the allocation that caused the "
                    "signal.")),
    HumanMessage("signal_restricted",
                 N_("Execution killed (could be triggered by violating memory "
                    "limits)"),
                 N_("The evaluation was killed by a signal."
                    "Among other things, this might be caused by exceeding "
                    "the memory limit Note that if this is the reason, "
                    "the memory usage visible in the submission details is "
                    "the usage before the allocation that caused the "
                    "signal.")),
    HumanMessage("returncode",
                 N_("Execution failed because the return code was nonzero"),
                 N_("Your submission failed because it exited with a return "
                    "code different from 0.")),
])


def evaluation_step(sandbox, commands,
                    time_limit=None, memory_limit=None,
                    allow_dirs=None, writable_files=None,
                    stdin_redirect=None, stdout_redirect=None,
                    multiprocess=False):
    """Execute some evaluation commands in the sandbox.

    Execute the commands sequentially in the (already created) sandbox, after
    setting up an environment suitable for evaluation, tweaked as instructed
    by the arguments.

    Terminate early after a command if the sandbox fails.

    sandbox (Sandbox): the sandbox we consider, already created.
    commands ([[str]]): evaluation commands to execute.
    time_limit (float|None): time limit in seconds (applied to each command);
        if None, no time limit is enforced.
    memory_limit (int|None): memory limit in MiB (applied to each command); if
        None, no memory limit is enforced.
    allow_dirs ([str]|None): if not None, a list of external
        directories to map inside the sandbox
    writable_files ([str]|None): a list of inner file names (relative to
        the inner path) on which the command is allow to write, or None to
        indicate that all files are read-only; if applicable, redirected
        output and the standard error are implicitly added to the files
        allowed.
    stdin_redirect (str|None): the name of the file that will be redirected
        to the standard input of each command; if None, nothing will be
        provided to stdin.
    stdout_redirect (str|None): the name of the file that the standard output
        of each command will be redirected to; if None, "stdout.txt" will be
        used.
    multiprocess (bool): whether to allow multiple thread/processes or not.

    return ((bool, bool|None, dict|None)): a tuple with three items:
        * success: True if the sandbox did not fail, in any command;
        * evaluation_success: True if the solution ran correctly and the output
            can be evaluated, False if it terminated with an error or was
            terminated due to resource limitation; None if success is False;
        * stats: a dictionary with statistics about the evaluation, or None
            if success is False.

    raise (ValueError): if time or memory limit are non-positive.

    """
    for command in commands:
        success = evaluation_step_before_run(
            sandbox, command, time_limit, memory_limit,
            allow_dirs, writable_files, stdin_redirect, stdout_redirect,
            multiprocess, wait=True)
        if not success:
            logger.debug("Job failed in evaluation_step_before_run.")
            return False, None, None

    success, evaluation_success, stats = evaluation_step_after_run(sandbox)
    if not success:
        logger.debug("Job failed in evaluation_step_after_run: %r", stats)

    return success, evaluation_success, stats


def evaluation_step_before_run(sandbox, command,
                               time_limit=None, memory_limit=None,
                               allow_dirs=None, writable_files=None,
                               stdin_redirect=None, stdout_redirect=None,
                               multiprocess=False, wait=False):
    """First part of an evaluation step, up to the execution, included.

    See evaluation_step for the meaning of the common arguments. This version
    only accepts one command, and in addition the argument "wait" to decide
    whether to make the run blocking or not.

    wait (bool): if True, block until the command terminates.

    return (bool|Popen): sandbox success if wait is True, the process if not.

    """
    # Ensure parameters are appropriate.
    if time_limit is not None and time_limit <= 0:
        raise ValueError("Time limit must be positive, is %s" % time_limit)
    if memory_limit is not None and memory_limit <= 0:
        raise ValueError(
            "Memory limit must be positive, is %s" % memory_limit)

    # Default parameters handling.
    if allow_dirs is None:
        allow_dirs = []
    if writable_files is None:
        writable_files = []
    if stdout_redirect is None:
        stdout_redirect = "stdout.txt"

    # Set sandbox parameters suitable for evaluation.
    if time_limit is not None:
        sandbox.timeout = time_limit
        sandbox.wallclock_timeout = 2 * time_limit + 1
    else:
        sandbox.timeout = None
        sandbox.wallclock_timeout = None

    if memory_limit is not None:
        sandbox.address_space = memory_limit * 1024
    else:
        sandbox.address_space = None

    sandbox.fsize = config.max_file_size

    sandbox.stdin_file = stdin_redirect
    sandbox.stdout_file = stdout_redirect
    sandbox.stderr_file = "stderr.txt"

    sandbox.add_mapped_directories(allow_dirs)
    for name in [sandbox.stderr_file, sandbox.stdout_file]:
        if name is not None:
            writable_files.append(name)
    sandbox.allow_writing_only(writable_files)

    sandbox.set_multiprocess(multiprocess)

    # Actually run the evaluation command.
    logger.debug("Starting execution step.")
    return sandbox.execute_without_std(command, wait=wait)


def evaluation_step_after_run(sandbox):
    """Final part of an evaluation step, collecting the results after the run.

    See evaluation_step for the meaning of the argument and the return value.

    """
    stats = execution_stats(sandbox)
    exit_status = stats["exit_status"]

    if exit_status == Sandbox.EXIT_OK:
        # Evaluation succeeded, and user program terminated correctly.
        logger.debug("Evaluation terminated correctly.")
        return True, True, stats

    elif exit_status in [
            Sandbox.EXIT_TIMEOUT,
            Sandbox.EXIT_TIMEOUT_WALL,
            Sandbox.EXIT_NONZERO_RETURN,
            Sandbox.EXIT_SIGNAL]:
        # Evaluation succeeded, and user program was interrupted for some error
        # condition. We report the success, the task type should decide how to
        # grade this evaluation.
        logger.debug("Evaluation ended with exit status '%s'", exit_status)
        return True, False, stats

    # Unexpected errors of various degrees; we report the failure.
    elif exit_status == Sandbox.EXIT_SANDBOX_ERROR:
        logger.error("Evaluation aborted because of sandbox error "
                     "(status '%s').", exit_status)
        return False, None, None

    else:
        logger.error("Unrecognized evaluation exit status '%s'.", exit_status)
        return False, None, None


def human_evaluation_message(
        stats, feedback_level=FEEDBACK_LEVEL_RESTRICTED):
    """Return a human-readable message from the given execution stats.

    Return a message for errors in the command ran in the evaluation, that can
    be passed to contestants. Don't return a message for success conditions
    (as the message will be computed elsewhere) or for sandbox error (since the
    submission will still be "evaluating..." for contestants).

    stats (dict): execution statistics for an evaluation step.
    feedback_level (str): the level of details to show to users.

    return ([str]): a list of strings composing the message (where
        strings from the second to the last are formatting arguments for the
        first); or an empty list if no message should be passed to
        contestants.

    """
    exit_status = stats['exit_status']
    if exit_status == Sandbox.EXIT_TIMEOUT:
        return [EVALUATION_MESSAGES.get("timeout").message]
    elif exit_status == Sandbox.EXIT_TIMEOUT_WALL:
        return [EVALUATION_MESSAGES.get("walltimeout").message]
    elif exit_status == Sandbox.EXIT_SIGNAL:
        if feedback_level == FEEDBACK_LEVEL_RESTRICTED:
            return [EVALUATION_MESSAGES.get("signal_restricted").message]
        elif feedback_level == FEEDBACK_LEVEL_FULL:
            return [EVALUATION_MESSAGES.get("signal").message,
                    str(stats['signal'])]
        else:
            raise ValueError("Unexpected value '%s' for feedback level."
                             % feedback_level)
    elif exit_status == Sandbox.EXIT_SANDBOX_ERROR:
        # Contestants won't see this, the submission will still be evaluating.
        return []
    elif exit_status == Sandbox.EXIT_NONZERO_RETURN:
        # Don't tell which code: would be too much information!
        return [EVALUATION_MESSAGES.get("returncode").message]
    elif exit_status == Sandbox.EXIT_OK:
        return []
    else:
        logger.error("Unrecognized exit status for an evaluation: %s",
                     exit_status)
        return []
