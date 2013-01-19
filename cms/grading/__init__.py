#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
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

import os
import codecs

from cms import logger
from cms.db.SQLAlchemyAll import SessionGen, Submission
from cms.grading.Sandbox import Sandbox


class JobException(Exception):
    """Exception raised by a worker doing a job.

    """
    def __init__(self, msg=""):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)

    def __repr__(self):
        return "JobException(\"%s\")" % (repr(self.msg))


def get_compilation_command(language, source_filenames, executable_filename,
                            for_evaluation=True):
    """Returns the compilation command for the specified language,
    source filenames and executable filename. The command is a list of
    strings, suitable to be passed to the methods in subprocess
    package.

    language (string): one of the recognized languages.
    source_filenames (list): a list of the string that are the
                             filenames of the source files to compile;
                             the order is relevant: the first file
                             must be the one that contains the program
                             entry point (with some langages,
                             e.g. Pascal, only the main file must be
                             passed to the compiler).
    executable_filename (string): the output file.
    for_evaluation (bool): if True, define EVAL during the compilation;
                           defaults to True.
    return (list): a list of string to be passed to subprocess.

    """
    # For compiling in 32-bit mode under 64-bit OS: add "-march=i686",
    # "-m32" for gcc/g++. Don't know about Pascal. Anyway, this will
    # require some better support from the evaluation environment
    # (particularly the sandbox, which has to be compiled in a
    # different way depending on whether it will execute 32- or 64-bit
    # programs).
    if language == "c":
        command = ["/usr/bin/gcc"]
        if for_evaluation:
            command += ["-DEVAL"]
        command += ["-static", "-O2", "-o", executable_filename]
        command += source_filenames
        command += ["-lm"]
    elif language == "cpp":
        command = ["/usr/bin/g++"]
        if for_evaluation:
            command += ["-DEVAL"]
        command += ["-static", "-O2", "-o", executable_filename]
        command += source_filenames
    elif language == "pas":
        command = ["/usr/bin/fpc"]
        if for_evaluation:
            command += ["-dEVAL"]
        command += ["-XS", "-O2", "-o%s" % executable_filename]
        command += [source_filenames[0]]
    return command


def compilation_step(sandbox, command):
    """Execute a compilation command in the sandbox, setting up the
    sandbox itself with a standard configuration and doing standard
    checks at the end of the compilation.

    Note: this needs a sandbox already created.

    sandbox (Sandbox): the sandbox we consider.
    command (string): the actual compilation line.

    """
    # Set sandbox parameters suitable for compilation.
    sandbox.dirs += [("/etc", None, None)]
    path_in_sandbox = "/tmp"
    sandbox.dirs += [(path_in_sandbox, sandbox.path, "rw")]
    sandbox.chdir = path_in_sandbox
    sandbox.chdir = "/tmp"
    sandbox.preserve_env = True
    sandbox.max_processes = None
    # FIXME - File access limits are not enforced on children
    # processes (like ld).
    sandbox.set_env['TMPDIR'] = path_in_sandbox
    sandbox.timeout = 10
    sandbox.wallclock_timeout = 20
    sandbox.address_space = 256 * 1024
    sandbox.stdout_file = os.path.join(path_in_sandbox, "compiler_stdout.txt")
    sandbox.stderr_file = os.path.join(path_in_sandbox, "compiler_stderr.txt")

    # Actually run the compilation command.
    logger.debug("Starting compilation step.")
    box_success = sandbox.execute_without_std(command, wait=True)
    if not box_success:
        logger.error("Compilation aborted because of "
                     "sandbox error in `%s'." % sandbox.path)
        return False, None, None, None

    # Detect the outcome of the compilation.
    exit_status = sandbox.get_exit_status()
    exit_code = sandbox.get_exit_code()
    stdout = sandbox.get_file_to_string("compiler_stdout.txt")
    if stdout.strip() == "":
        stdout = "(empty)\n"
    stdout = unicode(stdout, errors='ignore')
    stderr = sandbox.get_file_to_string("compiler_stderr.txt")
    if stderr.strip() == "":
        stderr = "(empty)\n"
    stderr = unicode(stderr, errors='ignore')
    compiler_output = "Compiler standard output:\n" \
        "%s\n" \
        "Compiler standard error:\n" \
        "%s" % (stdout, stderr)

    # And retrieve some interesting data.
    plus = {
        "execution_time": sandbox.get_execution_time(),
        "execution_wall_clock_time":
            sandbox.get_execution_wall_clock_time(),
        "memory_used": sandbox.get_memory_used(),
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
        text = "OK %s\n%s" % (sandbox.get_stats(), compiler_output)

    # Error in compilation: returning the error to the user.
    elif (exit_status == Sandbox.EXIT_OK and exit_code != 0) or \
             exit_status == Sandbox.EXIT_NONZERO_RETURN:
        logger.debug("Compilation failed.")
        success = True
        compilation_success = False
        text = "Failed %s\n%s" % (sandbox.get_stats(), compiler_output)

    # Timeout: returning the error to the user
    elif exit_status == Sandbox.EXIT_TIMEOUT:
        logger.debug("Compilation timed out.")
        success = True
        compilation_success = False
        text = "Time out %s\n%s" % (sandbox.get_stats(), compiler_output)

    # Suicide with signal (probably memory limit): returning the error
    # to the user
    elif exit_status == Sandbox.EXIT_SIGNAL:
        signal = sandbox.get_killing_signal()
        logger.debug("Compilation killed with signal %s." % (signal))
        success = True
        compilation_success = False
        plus["signal"] = signal
        text = "Killed with signal %d %s.\nThis could be triggered by " \
            "violating memory limits\n%s" % \
            (signal, sandbox.get_stats(), compiler_output)

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


def evaluation_step(sandbox, command,
                    time_limit=0, memory_limit=0,
                    stdin_redirect=None, stdout_redirect=None):
    """Execute an evaluation command in the sandbox. Note that in some
    task types, there may be more than one evaluation commands (per
    testcase) (in others there can be none, of course).

    sandbox (Sandbox): the sandbox we consider.
    command (string): the actual evaluation line.
    time_limit (float): time limit in seconds.
    memory_limit (int): memory limit in MB.

    return (bool, dict): True if the evaluation was successful, or
                         False; and additional data.

    """
    success = evaluation_step_before_run(
        sandbox, command, time_limit, memory_limit,
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
                              stdin_redirect=None, stdout_redirect=None,
                              wait=False):
    """First part of an evaluation step, until the running.

    return: exit code already translated if wait is True, the
            process if wait is False.

    """
    # Set sandbox parameters suitable for evaluation.
    path_in_sandbox = "/tmp"
    sandbox.dirs += [(path_in_sandbox, sandbox.path, "rw")]
    sandbox.chdir = path_in_sandbox
    sandbox.timeout = time_limit
    sandbox.wallclock_timeout = 2 * time_limit
    sandbox.address_space = memory_limit * 1024

    if stdin_redirect is not None:
        sandbox.stdin_file = os.path.join(path_in_sandbox, stdin_redirect)
    else:
        sandbox.stdin_file = None

    if stdout_redirect is not None:
        sandbox.stdout_file = os.path.join(path_in_sandbox, stdout_redirect)
    else:
        sandbox.stdout_file = os.path.join(path_in_sandbox, "stdout.txt")

    sandbox.stderr_file = os.path.join(path_in_sandbox, "stderr.txt")

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
        "execution_wall_clock_time":
            sandbox.get_execution_wall_clock_time(),
        "memory_used": sandbox.get_memory_used(),
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
        msg = "Execution killed because of forbidden syscall %s." % \
            syscall
        logger.debug(msg)
        success = True
        plus["syscall"] = syscall

    # Forbidden file access: returning the error to the user, without
    # disclosing the offending file (can't we?).
    elif exit_status == Sandbox.EXIT_FILE_ACCESS:
        filename = sandbox.get_forbidden_file_error()
        msg = "Execution killed because of forbidden file access."
        logger.debug("%s `%s'." % (msg, filename))
        success = True
        plus["filename"] = filename

    # The exit code was nonzero: returning the error to the user.
    elif exit_status == Sandbox.EXIT_NONZERO_RETURN:
        msg = "Execution failed because the return code was nonzero."
        logger.debug("%s" % msg)
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
        return "Execution timed out."
    elif exit_status == Sandbox.EXIT_SIGNAL:
        return "Execution killed with signal %d." % (plus['signal'])
    elif exit_status == Sandbox.EXIT_SANDBOX_ERROR:
        return None
    elif exit_status == Sandbox.EXIT_SYSCALL:
        return "Execution killed because of forbidden syscall %s." % \
            (plus['syscall'])
    elif exit_status == Sandbox.EXIT_FILE_ACCESS:
        return "Execution killed because of forbidden file access."
    elif exit_status == Sandbox.EXIT_NONZERO_RETURN:
        return "Execution failed because the return code was nonzero."
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

    return (float, string): outcome and text.
    raise: ValueError if cannot decode the data.

    """
    stdout = sandbox.stdout_file
    stderr = sandbox.stderr_file
    with codecs.open(stdout, "r", "utf-8") as stdout_file:
        with codecs.open(stderr, "r", "utf-8") as stderr_file:
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

    return outcome, text


## Automatic white diff. ##

WHITES = " \t\n\r"


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
        """Assess the correctedness of a solution by doing a simple
        white diff against the reference solution. It gives an outcome
        1.0 if the output and the reference output are identical (or
        differ just by white spaces) and 0.0 if they don't (or if the
        output doesn't exist).

        sandbox (Sandbox): the sandbox we consider.
        output_filename (string): the filename of user's output in the
                                  sandbox.
        correct_output_filename (string): the same with reference
                                          output.

        return (float, string): the outcome as above and a description
                                text.

        """
        if sandbox.file_exists(output_filename):
            out_file = sandbox.get_file(output_filename)
            res_file = sandbox.get_file("res.txt")
            if white_diff(out_file, res_file):
                outcome = 1.0
                text = "Output is correct"
            else:
                outcome = 0.0
                text = "Output isn't correct"
        else:
            outcome = 0.0
            text = "Evaluation didn't produce file %s" % (output_filename)
        return outcome, text


## Computing global scores (for ranking). ##

def task_score(user, task):
    """Return the score of a user on a task.

    user (User): the user for which to compute the score.
    task (Task): the task for which to compute the score.

    return (float, bool): the score of user on task, and True if the
                          score could change because of a submission
                          yet to score.

    """
    def waits_for_score(submission):
        """Return if submission could be scored but it currently is
        not.

        submission (Submission): the submission to check.

        """
        return submission.compilation_outcome != "fail" and \
               not submission.scored()

    # The score of the last submission (if valid, otherwise 0.0).
    last_score = 0.0
    # The maximum score amongst the tokened submissions (invalid
    # scores count as 0.0).
    max_tokened_score = 0.0
    # If the score could change due to submission still being compiled
    # / evaluated / scored.
    partial = False

    with SessionGen(commit=False) as session:
        submissions = session.query(Submission).\
            filter(Submission.user == user).\
            filter(Submission.task == task).\
            order_by(Submission.timestamp).all()

        if submissions == []:
            return 0.0, False

        # Last score: if the last submission is scored we use that,
        # otherwise we use 0.0 (and mark that the score is partial
        # when the last submission could be scored).
        if submissions[-1].scored():
            last_score = submissions[-1].score
        elif waits_for_score(submissions[-1]):
            partial = True

        for submission in submissions:
            if submission.token is not None:
                if submission.scored():
                    max_tokened_score = max(max_tokened_score,
                                            submission.score)
                elif waits_for_score(submission):
                    partial = True

    return max(last_score, max_tokened_score), partial
