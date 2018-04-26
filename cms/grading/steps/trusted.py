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

"""High level functions to perform standardized trusted executions.

Some of these function refer to a "standard manager output". This is defined as
having a single line on stdout containing a floating point number (the outcome)
and a single line on stderr containing the text to show to contestants.

In addition, texts only indicating success, partial success or wrong solution
can be translated by writing "translate:x" where x is "success", "partial" or
"wrong".

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa

import logging

from cms import config
from cms.grading.Sandbox import Sandbox
from .evaluation import EVALUATION_MESSAGES
from .utils import generic_step


logger = logging.getLogger(__name__)


def _filter_ansi_escape(string):
    """Filter out ANSI commands from the given string.

    string (str): string to process.

    return (str): string with ANSI commands stripped.

    """
    ansi_mode = False
    res = ''
    for char in string:
        if char == u'\033':
            ansi_mode = True
        if not ansi_mode:
            res += char
        if char == u'm':
            ansi_mode = False
    return res


def extract_outcome_and_text(sandbox):
    """Extract the outcome and the text from the a standard manager output.

    sandbox (Sandbox): the sandbox whose last execution was a manager writing
        a standard manager output.

    return (float, [str]): outcome and text.

    raise (ValueError): if cannot decode the data.

    """
    with sandbox.get_file_text(sandbox.stdout_file) as stdout_file:
        try:
            outcome = stdout_file.readline().strip()
        except UnicodeDecodeError as error:
            logger.error("Manager stdout (outcome) is not valid UTF-8. %r",
                         error)
            raise ValueError("Cannot decode the outcome.")

    with sandbox.get_file_text(sandbox.stderr_file) as stderr_file:
        try:
            text = _filter_ansi_escape(stderr_file.readline().strip())
        except UnicodeDecodeError as error:
            logger.error("Manager stderr (text) is not valid UTF-8. %r", error)
            raise ValueError("Cannot decode the text.")

    try:
        outcome = float(outcome)
    except ValueError:
        logger.error("Wrong outcome `%s' from manager.", outcome)
        raise ValueError("Outcome is not a float.")

    # If the text starts with translate, the manager is asking us to
    # use a stock message, that can be translated.
    if text.startswith("translate:"):
        remaining = text[len("translate:"):].strip()
        if remaining in ["success", "partial", "wrong"]:
            text = EVALUATION_MESSAGES.get(remaining).message
        else:
            remaining = remaining[:15]  # to avoid logging lots of text
            logger.warning("Manager asked to translate text, but string "
                           "'%s' is not recognized." % remaining)

    return outcome, [text]


def trusted_step(sandbox, commands):
    """Execute some trusted commands in the sandbox.

    Even if the commands are trusted, we use the sandbox to limit the resources
    they use to avoid crashing a worker due to some configuration or
    programming error.

    sandbox (Sandbox): the sandbox we consider, already created.
    commands ([[str]]): trusted commands to execute.

    return ((bool, bool|None, dict|None)): a tuple with three items:
        * success: True if the sandbox did not fail, in any command;
        * execution_success: True if all commands terminated correctly,
            without timeouts or other errors; None if success is False;
        * stats: a dictionary with statistics about the execution, or None
            if success is False.

    """
    # Set sandbox parameters suitable for trusted commands.
    sandbox.preserve_env = True
    sandbox.max_processes = config.trusted_sandbox_max_processes
    sandbox.timeout = config.trusted_sandbox_max_time_s
    sandbox.wallclock_timeout = 2 * sandbox.timeout + 1
    sandbox.address_space = config.trusted_sandbox_max_memory_kib

    # Run the trusted commands.
    stats = generic_step(sandbox, commands, "trusted")
    if stats is None:
        logger.error("Sandbox failed during trusted step. "
                     "See previous logs for the reason.")
        return False, None, None

    exit_status = stats["exit_status"]

    if exit_status == Sandbox.EXIT_OK:
        # Sandbox ok, commands ok.
        logger.debug("Trusted step ended successfully.")
        return True, True, stats
    elif exit_status in [
            Sandbox.EXIT_NONZERO_RETURN,
            Sandbox.EXIT_TIMEOUT,
            Sandbox.EXIT_TIMEOUT_WALL,
            Sandbox.EXIT_SIGNAL]:
        # Sandbox ok, commands not ok.
        logger.error("Trusted step ended with status '%s' (usually due to "
                     "programming errors in a manager or configuration "
                     "issues).", exit_status)
        return True, False, stats
    elif exit_status == Sandbox.EXIT_SANDBOX_ERROR:
        # Sandbox not ok.
        logger.error("Unexpected SANDBOX_ERROR exit status in trusted step.")
        return False, None, None
    else:
        # Sandbox interface not ok, something really wrong happened.
        logger.error("Unrecognized sandbox exit status '%s' in trusted step.",
                     exit_status)
        return False, None, None
