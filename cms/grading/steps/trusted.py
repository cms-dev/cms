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

"""High level functions to perform standardized trusted executions.

Some of these function refer to a "standard manager output". This is defined as
having a single line on stdout containing a floating point number (the outcome)
and a single line on stderr containing the text to show to contestants.

In addition, texts only indicating success, partial success or wrong solution
can be translated by writing "translate:x" where x is "success", "partial" or
"wrong".

"""

import logging
import re

from cms import config
from cms.grading.Sandbox import Sandbox
from .evaluation import EVALUATION_MESSAGES
from .utils import generic_step
from .stats import StatsDict


logger = logging.getLogger(__name__)


# Filenames used for input and correct output in the checker sandbox.
CHECKER_INPUT_FILENAME = "input.txt"
CHECKER_CORRECT_OUTPUT_FILENAME = "correct_output.txt"
# Codename of the manager used to compare output (must be an executable), and
# also the filename used in the sandbox.
CHECKER_FILENAME = "checker"


def _sanitize_message(string: str) -> str:
    """Sanitize a message read from manager output.

    Percent signs are escaped (so they are not treated as formatting specifiers
    later). Control characters are rejected.

    string: string to process.

    return: sanitized string.

    raise (ValueError): if invalid characters were found.

    """
    match = re.search('[\x00-\x08\x0a-\x1f\x7f-\xbf]', string)
    if match:
        ch = ord(match[0])
        raise ValueError(f'Invalid character in outcome: 0x{ch:02x}')

    return string.replace('%', '%%')


def extract_outcome_and_text(sandbox: Sandbox) -> tuple[float, list[str]]:
    """Extract the outcome and the text from the a standard manager output.

    sandbox: the sandbox whose last execution was a manager writing
        a standard manager output.

    return: outcome and text.

    raise (ValueError): if cannot decode the data.
    raise (FileNotFoundError): if any of the sandbox stdout or stderr file
        is missing.

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
            text = _sanitize_message(stderr_file.readline().strip())
        except UnicodeDecodeError as error:
            logger.error("Manager stderr (text) is not valid UTF-8. %r", error)
            raise ValueError("Cannot decode the text.")
        except ValueError as error:
            logger.error("Manager stderr (text) is malformed. %r", error)
            raise error

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


def trusted_step(
    sandbox: Sandbox, commands: list[list[str]]
) -> tuple[bool, bool | None, StatsDict | None]:
    """Execute some trusted commands in the sandbox.

    Even if the commands are trusted, we use the sandbox to limit the resources
    they use to avoid crashing a worker due to some configuration or
    programming error.

    sandbox: the sandbox we consider, already created.
    commands: trusted commands to execute.

    return: a tuple with three items:
        * success: True if the sandbox did not fail, in any command;
        * execution_success: True if all commands terminated correctly,
            without timeouts or other errors; None if success is False;
        * stats: a dictionary with statistics about the execution, or None
            if success is False.

    """
    # Set sandbox parameters suitable for trusted commands.
    sandbox.preserve_env = True
    sandbox.max_processes = config.sandbox.trusted_sandbox_max_processes
    sandbox.timeout = config.sandbox.trusted_sandbox_max_time_s
    sandbox.wallclock_timeout = 2 * sandbox.timeout + 1
    sandbox.address_space = config.sandbox.trusted_sandbox_max_memory_kib * 1024

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


def checker_step(
    sandbox: Sandbox,
    checker_digest: str | None,
    input_digest: str,
    correct_output_digest: str,
    output_filename: str,
    extra_args: list[str] | None = None
) -> tuple[bool, float | None, list[str] | None]:
    """Run the explicit checker given by the admins

    sandbox: the sandbox to run the checker in; should already
        contain input, correct output, and user output; the checker is instead
        copied from the managers.
    checker_digest: digest of the checker, will be fetched as
        "checker"; if None, an appropriate error for bad configuration of the
        task will be generated.
    input_digest: digest of the input, will be fetched as "input.txt".
    correct_output_digest: digest of the correct output, will be fetched
        as "correct_output.txt".
    output_filename: inner filename of the user output (already in the
        sandbox).
    extra_args: extra arguments to pass to the checker.

    return: success (true if the checker was able to check the solution
        successfully), outcome and text (both None if success is False).

    """
    # Check that the file we are going to inject in the sandbox are not already
    # present (if so, it is due to a programming error in the task type).
    for filename in [CHECKER_INPUT_FILENAME,
                     CHECKER_CORRECT_OUTPUT_FILENAME,
                     CHECKER_FILENAME]:
        if sandbox.file_exists(filename):
            logger.error("File %s already in the sandbox for the checker.",
                         filename)
            return False, None, None

    # Copy the checker in the sandbox, after making sure it was provided.
    if checker_digest is None:
        logger.error("Configuration error: missing checker in task managers.")
        return False, None, None
    sandbox.create_file_from_storage(CHECKER_FILENAME, checker_digest,
                                     executable=True)

    # Copy input and correct output in the sandbox.
    sandbox.create_file_from_storage(CHECKER_INPUT_FILENAME, input_digest)
    sandbox.create_file_from_storage(CHECKER_CORRECT_OUTPUT_FILENAME,
                                     correct_output_digest)

    # Execute the checker and ensure success, or log an error.
    command = ["./%s" % CHECKER_FILENAME,
               CHECKER_INPUT_FILENAME,
               CHECKER_CORRECT_OUTPUT_FILENAME,
               output_filename] + (extra_args if extra_args is not None else [])
    box_success, success, unused_stats = trusted_step(sandbox, [command])
    if not box_success or not success:
        logger.error("Sandbox failed during checker step. "
                     "See previous logs for the reason.")
        return False, None, None

    # Extract outcome and text assuming a standard manager output.
    try:
        outcome, text = extract_outcome_and_text(sandbox)
    except ValueError as e:
        logger.error("Invalid output from checker: %s", e)
        return False, None, None
    except FileNotFoundError as e:
        # This should not happen, as the redirect is handled by the sandbox.
        logger.error("Missing stdout or stderr file from checker: %s", e)
        return False, None, None

    return True, outcome, text
