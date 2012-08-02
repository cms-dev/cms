#!/usr/bin/python
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
                             filenames of the source files to compile.
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
        command += ["-static", "-O2", "-lm", "-o", executable_filename]
        command += source_filenames
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
        command += source_filenames
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
    sandbox.chdir = sandbox.path
    sandbox.preserve_env = True
    sandbox.filter_syscalls = 1
    sandbox.allow_syscall = ["waitpid", "prlimit64"]
    sandbox.allow_fork = True
    sandbox.file_check = 2
    # FIXME - File access limits are not enforced on children
    # processes (like ld).
    sandbox.set_env['TMPDIR'] = sandbox.path
    sandbox.allow_path = ['/etc/', '/lib/', '/usr/',
                          '%s/' % (sandbox.path)]
    sandbox.allow_path += ["/proc/self/exe"]
    sandbox.timeout = 10
    sandbox.wallclock_timeout = 20
    sandbox.address_space = 256 * 1024
    sandbox.stdout_file = sandbox.relative_path("compiler_stdout.txt")
    sandbox.stderr_file = sandbox.relative_path("compiler_stderr.txt")

    # Actually run the compilation command.
    logger.info("Starting compilation step.")
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
    stderr = sandbox.get_file_to_string("compiler_stderr.txt")
    if stderr.strip() == "":
        stderr = "(empty)\n"
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
        "stdout": sandbox.get_file_to_string("compiler_stdout.txt"),
        "stderr": sandbox.get_file_to_string("compiler_stderr.txt"),
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
        logger.info("Compilation successfully finished.")
        success = True
        compilation_success = True
        text = "OK %s\n%s" % (sandbox.get_stats(), compiler_output)

    # Error in compilation: returning the error to the user.
    elif exit_status == Sandbox.EXIT_OK and exit_code != 0:
        logger.info("Compilation failed.")
        success = True
        compilation_success = False
        text = "Failed %s\n%s" % (sandbox.get_stats(), compiler_output)

    # Timeout: returning the error to the user
    elif exit_status == Sandbox.EXIT_TIMEOUT:
        logger.info("Compilation timed out.")
        success = True
        compilation_success = False
        text = "Time out %s\n%s" % (sandbox.get_stats(), compiler_output)

    # Suicide with signal (probably memory limit): returning the error
    # to the user
    elif exit_status == Sandbox.EXIT_SIGNAL:
        signal = sandbox.get_killing_signal()
        logger.info("Compilation killed with signal %s." % (signal))
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
                     "because of forbidden syscall '%s'." % syscall)

    # Forbidden file access: this could be triggered by the user
    # including a forbidden file or too strict sandbox contraints; the
    # administrator should have a look at it
    elif exit_status == Sandbox.EXIT_FILE_ACCESS:
        filename = sandbox.get_forbidden_file_error()
        logger.error("Compilation aborted "
                     "because of forbidden access to file '%s'." % filename)

    # Why the exit status hasn't been captured before?
    else:
        logger.error("Shouldn't arrive here, failing.")

    return success, compilation_success, text, plus


def evaluation_step(sandbox, command,
                    time_limit=0, memory_limit=0,
                    allow_path=None,
                    stdin_redirect=None, stdout_redirect=None):
    """Execute an evaluation command in the sandbox. Note that in some
    task types, there may be more than one evaluation commands (per
    testcase) (in others there can be none, of course).

    sandbox (Sandbox): the sandbox we consider.
    command (string): the actual evaluation line.
    time_limit (float): time limit in seconds.
    memory_limit (int): memory limit in MB.
    allow_path (list): list of relative paths accessible in the
                       sandbox.

    return (bool, float, string dict): True if the evaluation was
                                       successfull, or False; and
                                       additional data.

    """
    success = evaluation_step_before_run(
        sandbox, command, time_limit, memory_limit, allow_path,
        stdin_redirect, stdout_redirect, wait=True)
    if not success:
        return False, None
    else:
        return evaluation_step_after_run(sandbox)


def evaluation_step_before_run(sandbox, command,
                              time_limit=0, memory_limit=0,
                              allow_path=None,
                              stdin_redirect=None, stdout_redirect=None,
                              wait=False):
    """First part of an evaluation step, until the running.

    return: exit code already translated if wait is True, the
            process if wait is False.

    """
    # Set sandbox parameters suitable for evaluation.
    sandbox.chdir = sandbox.path
    sandbox.filter_syscalls = 2
    sandbox.timeout = time_limit
    sandbox.wallclock_timeout = 2 * time_limit
    sandbox.address_space = memory_limit * 1024
    sandbox.file_check = 1
    if allow_path is None:
        allow_path = []
    sandbox.allow_path = allow_path
    sandbox.stdin_file = stdin_redirect
    sandbox.stdout_file = stdout_redirect
    stdout_filename = os.path.join(sandbox.path, "stdout.txt")
    stderr_filename = os.path.join(sandbox.path, "stderr.txt")
    if sandbox.stdout_file is None:
        sandbox.stdout_file = stdout_filename
    sandbox.stderr_file = stderr_filename
    # These syscalls and paths are used by executables generated
    # by fpc.
    sandbox.allow_path += ["/proc/self/exe"]
    sandbox.allow_syscall += ["getrlimit",
                              "rt_sigaction",
                              "ugetrlimit"]
    # This one seems to be used for a C++ executable.
    sandbox.allow_path += ["/proc/meminfo"]
    # This is used by freopen in Ubuntu 12.04.
    sandbox.allow_syscall += ["dup3"]

    # Actually run the evaluation command.
    logger.info("Starting execution step.")
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
        logger.info("Execution timed out.")
        success = True

    # Suicide with signal (memory limit, segfault, abort): returning
    # the error to the user.
    elif exit_status == Sandbox.EXIT_SIGNAL:
        signal = sandbox.get_killing_signal()
        logger.info("Execution killed with signal %d." % signal)
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
        logger.info(msg)
        success = True
        plus["syscall"] = syscall

    # Forbidden file access: returning the error to the user, without
    # disclosing the offending file (can't we?).
    elif exit_status == Sandbox.EXIT_FILE_ACCESS:
        filename = sandbox.get_forbidden_file_error()
        msg = "Execution killed because of forbidden file access."
        logger.info("%s `%s'." % (msg, filename))
        success = True
        plus["filename"] = filename

    # Last check before assuming that evaluation finished
    # successfully; we accept the evaluation even if the exit code
    # isn't 0.
    elif exit_status != Sandbox.EXIT_OK:
        logger.error("Shouldn't arrive here, failing.")

    # If this isn't the last step of the evaluation, return that the
    # operation was successful, but neither an outcome nor an
    # explainatory text.
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
