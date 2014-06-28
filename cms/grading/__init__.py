#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2014 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2013-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import io
import json
import logging
import os
import six

from collections import namedtuple

from sqlalchemy.orm import joinedload

from cms import LANG_C, LANG_CPP, LANG_PASCAL, LANG_PYTHON, LANG_PHP, LANG_JAVA
from cms.db import Submission
from cms.grading.Sandbox import Sandbox


logger = logging.getLogger(__name__)


SubmissionScoreDelta = namedtuple(
    'SubmissionScoreDelta',
    ['submission', 'old_score', 'new_score',
     'old_public_score', 'new_public_score',
     'old_ranking_score_details', 'new_ranking_score_details'])


# Dummy function to mark translatable string.
def N_(message):
    return message


class JobException(Exception):
    """Exception raised by a worker doing a job.

    """
    def __init__(self, msg=""):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)

    def __repr__(self):
        return "JobException(\"%s\")" % (repr(self.msg))


def get_compilation_commands(language, source_filenames, executable_filename,
                             for_evaluation=True):
    """Return the compilation commands.

    The compilation commands are for the specified language, source
    filenames and executable filename. Each command is a list of
    strings, suitable to be passed to the methods in subprocess
    package.

    language (string): one of the recognized languages.
    source_filenames ([string]): a list of the string that are the
        filenames of the source files to compile; the order is
        relevant: the first file must be the one that contains the
        program entry point (with some langages, e.g. Pascal, only the
        main file must be passed to the compiler).
    executable_filename (string): the output file.
    for_evaluation (bool): if True, define EVAL during the compilation;
        defaults to True.

    return ([[string]]): a list of commands, each a list of strings to
        be passed to subprocess.

    """
    commands = []
    if language == LANG_C:
        command = ["/usr/bin/gcc"]
        if for_evaluation:
            command += ["-DEVAL"]
        command += ["-static", "-O2", "-o", executable_filename]
        command += source_filenames
        command += ["-lm"]
        commands.append(command)
    elif language == LANG_CPP:
        command = ["/usr/bin/g++"]
        if for_evaluation:
            command += ["-DEVAL"]
        command += ["-static", "-O2", "-o", executable_filename]
        command += source_filenames
        commands.append(command)
    elif language == LANG_PASCAL:
        command = ["/usr/bin/fpc"]
        if for_evaluation:
            command += ["-dEVAL"]
        command += ["-XS", "-O2", "-o%s" % executable_filename]
        command += [source_filenames[0]]
        commands.append(command)
    elif language == LANG_PYTHON:
        # The executable name is fixed, and there is no way to specify
        # the name of the pyc, so we need to bundle together two
        # commands (compilation and rename).
        # In order to use Python 3 change them to:
        # /usr/bin/python3 -m py_compile %s
        # mv __pycache__/%s.*.pyc %s
        py_command = ["/usr/bin/python2", "-m", "py_compile",
                      source_filenames[0]]
        mv_command = ["/bin/mv", "%s.pyc" % os.path.splitext(os.path.basename(
                      source_filenames[0]))[0], executable_filename]
        commands.append(py_command)
        commands.append(mv_command)
    elif language == LANG_PHP:
        command = ["/bin/cp", source_filenames[0], executable_filename]
        commands.append(command)
    elif language == LANG_JAVA:
        class_name = os.path.splitext(source_filenames[0])[0]
        command = ["/usr/bin/gcj", "--main=%s" % class_name, "-O3", "-o",
                   executable_filename] + source_filenames
        commands.append(command)
    else:
        raise ValueError("Unknown language %s." % language)
    return commands


def get_evaluation_commands(language, executable_filename):
    """Return the evaluation commands.

    The evaluation commands are for the given language and executable
    filename. Each command is a list of strings, suitable to be passed
    to the methods in subprocess package.

    language (string): one of the recognized languages.
    executable_filename (string): the name of the executable.

    return ([[string]]): a list of string to be passed to subprocess.

    """
    commands = []
    if language in (LANG_C, LANG_CPP, LANG_PASCAL, LANG_JAVA):
        command = [os.path.join(".", executable_filename)]
        commands.append(command)
    elif language == LANG_PYTHON:
        # In order to use Python 3 change it to:
        # /usr/bin/python3 %s
        command = ["/usr/bin/python2", executable_filename]
        commands.append(command)
    elif language == LANG_PHP:
        command = ["/usr/bin/php5", executable_filename]
        commands.append(command)
    else:
        raise ValueError("Unknown language %s." % language)
    return commands


def format_status_text(status, translator=None):
    """Format the given status text in the given locale.

    A status text is the content of SubmissionResult.compilation_text,
    Evaluation.text and UserTestResult.(compilation|evaluation)_text.
    It is a list whose first element is a string with printf-like
    placeholders and whose other elements are the data to use to fill
    them. A JSON-encoded list is also accepted.
    The first element will be translated using the given translator (or
    the identity function, if not given), completed with the data and
    returned.

    status ([unicode]|unicode): a status, as described above.
    translator (function|None): a function expecting a string and
        returning that same string translated in some language, or
        None to apply the identity.

    """
    # Mark strings for localization.
    N_("N/A")

    if translator is None:
        translator = lambda x: x

    try:
        if isinstance(status, six.text_type):
            status = json.loads(status)
        elif not isinstance(status, list):
            raise TypeError("Invalid type: %r" % type(status))

        return translator(status[0]) % tuple(status[1:])
    except:
        logger.error("Unexpected error when formatting status "
                     "text: %r" % status, exc_info=True)
        return translator("N/A")


def compilation_step(sandbox, commands):
    """Execute some compilation commands in the sandbox, setting up the
    sandbox itself with a standard configuration and doing standard
    checks at the end of the compilation.

    Note: this needs a sandbox already created.

    sandbox (Sandbox): the sandbox we consider.
    commands ([[string]]): the actual compilation lines.

    """
    # Set sandbox parameters suitable for compilation.
    sandbox.dirs += [("/etc", None, None)]
    sandbox.preserve_env = True
    sandbox.max_processes = None
    sandbox.timeout = 10
    sandbox.wallclock_timeout = 20
    sandbox.address_space = 512 * 1024
    sandbox.stdout_file = "compiler_stdout.txt"
    sandbox.stderr_file = "compiler_stderr.txt"

    # Actually run the compilation commands.
    logger.debug("Starting compilation step.")
    for command in commands:
        box_success = sandbox.execute_without_std(command, wait=True)
        if not box_success:
            logger.error("Compilation aborted because of "
                         "sandbox error in `%s'." % sandbox.path)
            return False, None, None, None

    # Detect the outcome of the compilation.
    exit_status = sandbox.get_exit_status()
    exit_code = sandbox.get_exit_code()
    stdout = sandbox.get_file_to_string("compiler_stdout.txt")
    stdout = unicode(stdout, 'utf-8', errors='replace')
    stderr = sandbox.get_file_to_string("compiler_stderr.txt")
    stderr = unicode(stderr, 'utf-8', errors='replace')

    # And retrieve some interesting data.
    plus = {
        "execution_time": sandbox.get_execution_time(),
        "execution_wall_clock_time": sandbox.get_execution_wall_clock_time(),
        "execution_memory": sandbox.get_memory_used(),
        "stdout": stdout,
        "stderr": stderr,
        "exit_status": exit_status,
        }

    # From now on, we test for the various possible outcomes and
    # act appropriately.

    # Execution finished successfully and the submission was
    # correctly compiled.
    success = False
    compilation_success = None
    text = None

    if exit_status == Sandbox.EXIT_OK and exit_code == 0:
        logger.debug("Compilation successfully finished.")
        success = True
        compilation_success = True
        text = [N_("Compilation succeeded")]

    # Error in compilation: returning the error to the user.
    elif (exit_status == Sandbox.EXIT_OK and exit_code != 0) or \
            exit_status == Sandbox.EXIT_NONZERO_RETURN:
        logger.debug("Compilation failed.")
        success = True
        compilation_success = False
        text = [N_("Compilation failed")]

    # Timeout: returning the error to the user
    elif exit_status == Sandbox.EXIT_TIMEOUT:
        logger.debug("Compilation timed out.")
        success = True
        compilation_success = False
        text = [N_("Compilation timed out")]

    # Suicide with signal (probably memory limit): returning the error
    # to the user
    elif exit_status == Sandbox.EXIT_SIGNAL:
        signal = sandbox.get_killing_signal()
        logger.debug("Compilation killed with signal %s." % (signal))
        success = True
        compilation_success = False
        plus["signal"] = signal
        text = [N_("Compilation killed with signal %d (could be triggered "
                   "by violating memory limits)"), signal]

    # Sandbox error: this isn't a user error, the administrator needs
    # to check the environment
    elif exit_status == Sandbox.EXIT_SANDBOX_ERROR:
        logger.error("Compilation aborted because of sandbox error.")

    # Forbidden syscall: this shouldn't happen, probably the
    # administrator should relax the syscall constraints
    elif exit_status == Sandbox.EXIT_SYSCALL:
        syscall = sandbox.get_killing_syscall()
        logger.error("Compilation aborted "
                     "because of forbidden syscall `%s'." % syscall)

    # Forbidden file access: this could be triggered by the user
    # including a forbidden file or too strict sandbox contraints; the
    # administrator should have a look at it
    elif exit_status == Sandbox.EXIT_FILE_ACCESS:
        filename = sandbox.get_forbidden_file_error()
        logger.error("Compilation aborted "
                     "because of forbidden access to file `%s'." % filename)

    # Why the exit status hasn't been captured before?
    else:
        logger.error("Shouldn't arrive here, failing.")

    return success, compilation_success, text, plus


def evaluation_step(sandbox, commands,
                    time_limit=0.0, memory_limit=0,
                    allow_dirs=None,
                    stdin_redirect=None, stdout_redirect=None):
    """Execute some evaluation commands in the sandbox. Note that in
    some task types, there may be more than one evaluation commands
    (per testcase) (in others there can be none, of course).

    sandbox (Sandbox): the sandbox we consider.
    commands ([[string]]): the actual evaluation lines.
    time_limit (float): time limit in seconds.
    memory_limit (int): memory limit in MB.

    return ((bool, dict)): True if the evaluation was successful, or
        False; and additional data.

    """
    for command in commands:
        success = evaluation_step_before_run(
            sandbox, command, time_limit, memory_limit, allow_dirs,
            stdin_redirect, stdout_redirect, wait=True)
        if not success:
            logger.debug("Job failed in evaluation_step_before_run.")
            return False, None

    success, plus = evaluation_step_after_run(sandbox)
    if not success:
        logger.debug("Job failed in evaluation_step_after_run: %r" % plus)

    return success, plus


def evaluation_step_before_run(sandbox, command,
                               time_limit=0, memory_limit=0,
                               allow_dirs=None,
                               stdin_redirect=None, stdout_redirect=None,
                               wait=False):
    """First part of an evaluation step, until the running.

    return: exit code already translated if wait is True, the
            process if wait is False.

    """
    # Set sandbox parameters suitable for evaluation.
    if time_limit > 0:
        sandbox.timeout = time_limit
        sandbox.wallclock_timeout = 2 * time_limit + 1
    else:
        sandbox.timeout = 0
        sandbox.wallclock_timeout = 0
    sandbox.address_space = memory_limit * 1024

    if stdin_redirect is not None:
        sandbox.stdin_file = stdin_redirect
    else:
        sandbox.stdin_file = None

    if stdout_redirect is not None:
        sandbox.stdout_file = stdout_redirect
    else:
        sandbox.stdout_file = "stdout.txt"

    sandbox.stderr_file = "stderr.txt"

    if allow_dirs is not None:
        for allow_dir in allow_dirs:
            sandbox.dirs += [(allow_dir, None, "rw")]

    # Actually run the evaluation command.
    logger.debug("Starting execution step.")
    return sandbox.execute_without_std(command, wait=wait)


def evaluation_step_after_run(sandbox):
    """Second part of an evaluation step, after the running.

    """
    # Detect the outcome of the execution.
    exit_status = sandbox.get_exit_status()

    # And retrieve some interesting data.
    plus = {
        "execution_time": sandbox.get_execution_time(),
        "execution_wall_clock_time": sandbox.get_execution_wall_clock_time(),
        "execution_memory": sandbox.get_memory_used(),
        "exit_status": exit_status,
        }

    success = False

    # Timeout: returning the error to the user.
    if exit_status == Sandbox.EXIT_TIMEOUT:
        logger.debug("Execution timed out.")
        success = True

    # Suicide with signal (memory limit, segfault, abort): returning
    # the error to the user.
    elif exit_status == Sandbox.EXIT_SIGNAL:
        signal = sandbox.get_killing_signal()
        logger.debug("Execution killed with signal %d." % signal)
        success = True
        plus["signal"] = signal

    # Sandbox error: this isn't a user error, the administrator needs
    # to check the environment.
    elif exit_status == Sandbox.EXIT_SANDBOX_ERROR:
        logger.error("Evaluation aborted because of sandbox error.")

    # Forbidden syscall: returning the error to the user. Note: this
    # can be triggered also while allocating too much memory
    # dynamically (offensive syscall is mprotect).
    elif exit_status == Sandbox.EXIT_SYSCALL:
        syscall = sandbox.get_killing_syscall()
        logger.debug("Execution killed because of forbidden "
                     "syscall: `%s'." % syscall)
        success = True
        plus["syscall"] = syscall

    # Forbidden file access: returning the error to the user, without
    # disclosing the offending file (can't we?).
    elif exit_status == Sandbox.EXIT_FILE_ACCESS:
        filename = sandbox.get_forbidden_file_error()
        logger.debug("Execution killed because of forbidden "
                     "file access: `%s'." % filename)
        success = True
        plus["filename"] = filename

    # The exit code was nonzero: returning the error to the user.
    elif exit_status == Sandbox.EXIT_NONZERO_RETURN:
        logger.debug("Execution failed because the return code was nonzero.")
        success = True

    # Last check before assuming that evaluation finished
    # successfully; we accept the evaluation even if the exit code
    # isn't 0.
    elif exit_status != Sandbox.EXIT_OK:
        logger.error("Shouldn't arrive here, failing.")

    else:
        success = True

    return success, plus


def human_evaluation_message(plus):
    """Given the plus object returned by evaluation_step, builds a
    human-readable message about what happened.

    None is returned in cases when the contestant musn't receive any
    message (for example, if the execution couldn't be performed) or
    when the message will be computed somewhere else (for example, if
    the execution was successfull, then the comparator is supposed to
    write the message).

    """
    exit_status = plus['exit_status']
    if exit_status == Sandbox.EXIT_TIMEOUT:
        return [N_("Execution timed out")]
    elif exit_status == Sandbox.EXIT_SIGNAL:
        return [N_("Execution killed with signal %d (could be triggered by "
                   "violating memory limits)"), plus['signal']]
    elif exit_status == Sandbox.EXIT_SANDBOX_ERROR:
        return None
    elif exit_status == Sandbox.EXIT_SYSCALL:
        return [N_("Execution killed because of forbidden syscall %s"),
                plus['syscall']]
    elif exit_status == Sandbox.EXIT_FILE_ACCESS:
        # Don't tell which file: would be too much information!
        return [N_("Execution killed because of forbidden file access")]
    elif exit_status == Sandbox.EXIT_NONZERO_RETURN:
        # Don't tell which code: would be too much information!
        return [N_("Execution failed because the return code was nonzero")]
    elif exit_status == Sandbox.EXIT_OK:
        return None
    else:
        return None


def is_evaluation_passed(plus):
    return plus['exit_status'] == Sandbox.EXIT_OK


def filter_ansi_escape(string):
    """Filter out ANSI commands from the given string.

    string (string): string to process.

    return (string): string with ANSI commands stripped.

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
    """Extract the outcome and the text from the two outputs of a
    manager (stdout contains the outcome, and stderr the text).

    stdout (Sandbox): the sandbox whose last execution was a
                      comparator.

    return (float, [string]): outcome and text.

    raise (ValueError): if cannot decode the data.

    """
    stdout = sandbox.relative_path(sandbox.stdout_file)
    stderr = sandbox.relative_path(sandbox.stderr_file)
    with io.open(stdout, "r", encoding="utf-8") as stdout_file:
        with io.open(stderr, "r", encoding="utf-8") as stderr_file:
            try:
                outcome = stdout_file.readline().strip()
            except UnicodeDecodeError as error:
                logger.error("Unable to interpret manager stdout "
                             "(outcome) as unicode. %r" % error)
                raise ValueError("Cannot decode the outcome.")
            try:
                text = filter_ansi_escape(stderr_file.readline())
            except UnicodeDecodeError as error:
                logger.error("Unable to interpret manager stderr "
                             "(text) as unicode. %r" % error)
                raise ValueError("Cannot decode the text.")

    try:
        outcome = float(outcome)
    except ValueError:
        logger.error("Wrong outcome `%s' from manager." % outcome)
        raise ValueError("Outcome is not a float.")

    return outcome, [text]


## Automatic white diff. ##

# We take as definition of whitespaces the intersection between ASCII
# and Unicode White_Space characters (see
# http://www.unicode.org/Public/6.3.0/ucd/PropList.txt)
WHITES = b' \t\n\x0b\x0c\r'


def white_diff_canonicalize(string):
    """Convert the input string to a canonical form for the white diff
    algorithm; that is, the strings a and b are mapped to the same
    string by white_diff_canonicalize() if and only if they have to be
    considered equivalent for the purposes of the white_diff
    algorithm.

    More specifically, this function strips all the leading and
    trailing whitespaces from s and collapse all the runs of
    consecutive whitespaces into just one copy of one specific
    whitespace.

    string (string): the string to canonicalize.
    return (string): the canonicalized string.

    """
    # Replace all the whitespaces with copies of " ", making the rest
    # of the algorithm simpler
    for char in WHITES[1:]:
        string = string.replace(char, WHITES[0])

    # Split the string according to " ", filter out empty tokens and
    # join again the string using just one copy of the first
    # whitespace; this way, runs of more than one whitespaces are
    # collapsed into just one copy.
    string = WHITES[0].join([x for x in string.split(WHITES[0])
                             if x != ''])
    return string


def white_diff(output, res):
    """Compare the two output files. Two files are equal if for every
    integer i, line i of first file is equal to line i of second
    file. Two lines are equal if they differ only by number or type of
    whitespaces.

    Note that trailing lines composed only of whitespaces don't change
    the 'equality' of the two files. Note also that by line we mean
    'sequence of characters ending with \n or EOF and beginning right
    after BOF or \n'. In particular, every line has *at most* one \n.

    output (file): the first file to compare.
    res (file): the second file to compare.
    return (bool): True if the two file are equal as explained above.

    """

    while True:
        lout = output.readline()
        lres = res.readline()

        # Both files finished: comparison succeded
        if lres == '' and lout == '':
            return True

        # Only one file finished: ok if the other contains only blanks
        elif lres == '' or lout == '':
            lout = lout.strip(WHITES)
            lres = lres.strip(WHITES)
            if lout != '' or lres != '':
                return False

        # Both file still have lines to go: ok if they agree except
        # for the number of whitespaces
        else:
            lout = white_diff_canonicalize(lout)
            lres = white_diff_canonicalize(lres)
            if lout != lres:
                return False


def white_diff_step(sandbox, output_filename,
                    correct_output_filename):
    """Assess the correctedness of a solution by doing a simple white
    diff against the reference solution. It gives an outcome 1.0 if
    the output and the reference output are identical (or differ just
    by white spaces) and 0.0 if they don't (or if the output doesn't
    exist).

    sandbox (Sandbox): the sandbox we consider.
    output_filename (string): the filename of user's output in the
        sandbox.
    correct_output_filename (string): the same with reference output.

    return ((float, [unicode])): the outcome as above and a
        description text.

    """
    if sandbox.file_exists(output_filename):
        out_file = sandbox.get_file(output_filename)
        res_file = sandbox.get_file("res.txt")
        if white_diff(out_file, res_file):
            outcome = 1.0
            text = [N_("Output is correct")]
        else:
            outcome = 0.0
            text = [N_("Output isn't correct")]
    else:
        outcome = 0.0
        text = [N_("Evaluation didn't produce file %s"), output_filename]
    return outcome, text


def compute_changes_for_dataset(old_dataset, new_dataset):
    """This function will compute the differences expected when changing from
    one dataset to another.

    old_dataset (Dataset): the original dataset, typically the active one.
    new_dataset (Dataset): the dataset to compare against.

    returns (list): a list of tuples of SubmissionScoreDelta tuples
        where they differ. Those entries that do not differ will have
        None in the pair of respective tuple entries.

    """
    # If we are switching tasks, something has gone seriously wrong.
    if old_dataset.task is not new_dataset.task:
        raise ValueError(
            "Cannot compare datasets referring to different tasks.")

    task = old_dataset.task

    def compare(a, b):
        if a == b:
            return False, (None, None)
        else:
            return True, (a, b)

    # Construct query with all relevant fields to avoid roundtrips to the DB.
    submissions = \
        task.sa_session.query(Submission)\
            .filter(Submission.task == task)\
            .options(joinedload(Submission.user))\
            .options(joinedload(Submission.token))\
            .options(joinedload(Submission.results)).all()

    ret = []
    for s in submissions:
        old = s.get_result(old_dataset)
        new = s.get_result(new_dataset)

        diff1, pair1 = compare(
            old.score if old is not None else None,
            new.score if new is not None else None)
        diff2, pair2 = compare(
            old.public_score if old is not None else None,
            new.public_score if new is not None else None)
        diff3, pair3 = compare(
            old.ranking_score_details if old is not None else None,
            new.ranking_score_details if new is not None else None)

        if diff1 or diff2 or diff3:
            ret.append(SubmissionScoreDelta(*(s,) + pair1 + pair2 + pair3))

    return ret


## Computing global scores (for ranking). ##

def task_score(user, task):
    """Return the score of a user on a task.

    user (User): the user for which to compute the score.
    task (Task): the task for which to compute the score.

    return ((float, bool)): the score of user on task, and True if the
        score could change because of a submission yet to score.

    """
    # As this function is primarily used when generating a rankings table
    # (AWS's RankingHandler), we optimize for the case where we are generating
    # results for all users and all tasks. As such, for the following code to
    # be more efficient, the query that generated task and user should have
    # come from a joinedload with the submissions, tokens and
    # submission_results table.  Doing so means that this function should incur
    # no exta database queries.

    # The score of the last submission (if valid, otherwise 0.0).
    last_score = 0.0
    # The maximum score amongst the tokened submissions (invalid
    # scores count as 0.0).
    max_tokened_score = 0.0
    # If the score could change due to submission still being compiled
    # / evaluated / scored.
    partial = False

    submissions = [s for s in user.submissions if s.task is task]
    submissions.sort(key=lambda s: s.timestamp)

    if submissions == []:
        return 0.0, False

    # Last score: if the last submission is scored we use that,
    # otherwise we use 0.0 (and mark that the score is partial
    # when the last submission could be scored).
    last_s = submissions[-1]
    last_sr = last_s.get_result(task.active_dataset)

    if last_sr is not None and last_sr.scored():
        last_score = last_sr.score
    else:
        partial = True

    for s in submissions:
        sr = s.get_result(task.active_dataset)
        if s.tokened():
            if sr is not None and sr.scored():
                max_tokened_score = max(max_tokened_score, sr.score)
            else:
                partial = True

    return max(last_score, max_tokened_score), partial
