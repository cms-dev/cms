#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2011 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2011 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2011 Matteo Boscariol <boscarim@hotmail.com>
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

"""In this file there are two things:
- the basic infrastructure from which we can build a task type;
- the implementations of the most common task types.

Basically, a task type is a class that receives a submission and knows
how to compile and evaluate it. A worker creates a task type to work
on a submission, and all low-level details on how to implement the
compilation and the evaluation are contained in the task type class.

"""

import os
import codecs

from cms.async.AsyncLibrary import logger, async_lock
from cms.box.Sandbox import Sandbox
from cms.db.SQLAlchemyAll import Task, Executable, Evaluation
from cms.service import JobException
from cms.util.Utils import get_compilation_command, white_diff, \
     filter_ansi_escape
from cms import Config


def get_task_type_class(submission, session, file_cacher):
    """Given a submission, istanciate the corresponding TaskType
    class.

    submission (Submission): the submission that needs the task type.
    session (SQLSession): the session the submission lives in.
    file_cacher (FileCacher): a file cacher object.

    """
    if submission.task.task_type == Task.TASK_TYPE_BATCH:
        return BatchTaskType(submission, session, file_cacher)
    else:
        return None


class TaskType:
    """Base class with common operation that (more or less) all task
    types must do sometimes.

    """
    def __init__(self, submission, session, file_cacher):
        """
        submission (Submission): the submission to grade.
        session (SQLSession): the SQLAlchemy session the submission
                              lives in.
        file_cacher (FileCacher): a FileCacher object to retrieve
                                  files from FS.

        """
        self.submission = submission
        self.session = session
        self.FC = file_cacher

    def finish_compilation(self, success, compilation_success=False, text=""):
        """Finalize the operation of compilation, deleting the
        sandbox, and writing back in the submission object the
        information (if success is True).

        success (bool): if the operation was successful (i.e., if cms
                        did everything in the right way).
        compilation_success (bool): if success = True, this is whether
                                    the compilation was successful
                                    (i.e., if the submission managed
                                    to compile).
        text (string): if success is True, stdout and stder of the
                       compiler, or a message explaining why it
                       compilation_success is False.
        return (bool): same as success

        """
        self.delete_sandbox()
        if not success:
            return False
        if compilation_success:
            self.submission.compilation_outcome = "ok"
        else:
            self.submission.compilation_outcome = "fail"
        try:
            self.submission.compilation_text = text.decode("utf-8")
        except UnicodeDecodeError:
            self.submission.compilation_text("Cannot decode compilation text.")
            with async_lock:
                logger.error("Unable to decode UTF-8 for string %s." % text)
        return True

    def finish_evaluation_testcase(self, test_number, success,
                                   outcome=0, text=""):
        """Finalize the operation of evaluating the submission on a
        testcase. Fill the information in the submission and delete
        the sandbox.

        test_number (int): number of testcase.
        success (bool): if the operation was successful.
        outcome (float): the outcome obtained by the submission on the
                         testcase.
        text (string): the reason of failure of the submission (if
                       any).
        return (bool): success.

        """
        self.delete_sandbox()
        if not success:
            return False
        self.submission.evaluations[test_number].text = text
        self.submission.evaluations[test_number].outcome = outcome
        return True

    def finish_evaluation(self, success):
        """Finalize the operation of evaluating. Currently there is
        nothing to do.

        success (bool): if the evaluation was successfull.
        return (bool): success.

        """
        if not success:
            return False
        return True

    def delete_sandbox(self):
        """Delete the sandbox created by this class, if the
        configuration allows it to be deleted.

        """
        if "sandbox" in self.__dict__ and not Config.keep_sandbox:
            try:
                self.sandbox.delete()
            except (IOError, OSError):
                with async_lock:
                    logger.warning("Couldn't delete sandbox")

    def create_sandbox(self):
        """Create a sandbox, and put it in self.sandbox. At any given
        time, we have at most one sandbox in an instance of TaskType,
        stored there.

        """
        try:
            self.sandbox = Sandbox(self.FC)
        except (OSError, IOError), e:
            with async_lock:
                logger.error("Couldn't create sandbox (error: %s)" % repr(e))
            self.delete_sandbox()
            raise JobException()

    def sandbox_operation(self, operation, *args, **kwargs):
        """Execute a method of the sandbox.

        operation (string): the method to call in the sandbox.
        args (list): arguments to pass to the sandbox method.
        kwargs (dict): also arguments.
        return (object): the return value of the method, or
                         JobException.

        """
        if self.sandbox == None:
            with async.lock:
                logger.error("Sandbox not present while doing "
                             "sandbox operation %s." % operation)
            raise JobException()

        try:
            return getattr(self.sandbox, operation)(*args, **kwargs)
        except (OSError, IOError) as e:
            with async_lock:
                logger.error("Error in safe sandbox operation %s, "
                             "with arguments %s, %s. Exception: %s" %
                             (operation, str(args), str(kwargs), repr(e)))
            self.delete_sandbox()
            raise JobException()
        except AttributeError:
            with async.lock:
                logger.error("Invalid sandbox operation %s." % operation)
            self.delete_sandbox()
            raise JobException()

    def compile(self):
        """Tries to compile the specified submission.

        It returns True when *our infrastracture* is successful (i.e.,
        the actual compilation may success or fail), and False when
        the compilation fails because of environmental problems
        (trying again to compile the same submission in a sane
        environment should lead to returning True).

        return (bool): success of operation.

        """
        raise NotImplementedError("Please subclass this class.")

    def evaluate(self):
        """Tries to evaluate the specified submission.

        It returns True when *our infrastracture* is successful (i.e.,
        the actual program may score or not), and False when the
        evaluation fails because of environmental problems (trying
        again to compile the same submission in a sane environment
        should lead to returning True).

        return (bool): success of operation.

        """
        raise NotImplementedError("Please subclass this class.")


class BatchTaskType(TaskType):
    """This class defines how to compile, and evaluate submissions for
    tasks of 'batch' type. In particular, we have several kind of
    methods:

    - finish_(compilation, evaluation_testcase, evaluation): these
      finalize the given operation, writing back to the submission the
      new information, and deleting the sandbox if needed;

    - *_sandbox_*: these are utility to create and delete the sandbox,
       and to ask it to do some operation. If the operation fails, the
       sandbox is deleted.

    - compile, evaluate_testcase, evaluate: these actually do the
      operations.

    """
    def compile(self):
        """See TaskType.compile.

        return (bool): success of operation.

        """
        # Detect the submission's language and check that it satisfies
        # the formal requirement for a submission (exact number of
        # files, correct extensions, ...)
        # TODO: this should be done before, no need to arrive to a
        # worker to check.
        valid, language = self.submission.verify_source()
        if not valid or language is None:
            with async_lock:
                logger.info("Invalid submission or couldn't detect language")
            return self.finish_compilation(True, False,
                                           "Invalid files in submission")

        # TODO: up to now we are able to have only one source file.
        if len(self.submission.files) != 1:
            with async_lock:
                logger.info("Submission contains %d files, expecting 1" %
                            len(self.submission.files))
            return self.finish_compilation(True, False,
                                           "Invalid files in submission")

        source_filename = self.submission.files.keys()[0]
        executable_filename = source_filename.replace(".%s" % (language), "")

        # Setup the compilation environment
        self.create_sandbox()
        self.sandbox_operation("create_file_from_storage",
                               source_filename,
                               self.submission.files[source_filename].digest)

        command = get_compilation_command(language,
                                          source_filename,
                                          executable_filename)

        # Execute the compilation inside the sandbox
        self.sandbox.chdir = self.sandbox.path
        self.sandbox.preserve_env = True
        self.sandbox.filter_syscalls = 1
        self.sandbox.allow_syscall = ["waitpid", "prlimit64"]
        self.sandbox.allow_fork = True
        self.sandbox.file_check = 2
        # FIXME - File access limits are not enforced on children
        # processes (like ld)
        self.sandbox.set_env['TMPDIR'] = self.sandbox.path
        self.sandbox.allow_path = ['/etc/', '/lib/', '/usr/',
                                   '%s/' % (self.sandbox.path)]
        self.sandbox.timeout = 8
        self.sandbox.wallclock_timeout = 10
        self.sandbox.address_space = 256 * 1024
        self.sandbox.stdout_file = \
            self.sandbox.relative_path("compiler_stdout.txt")
        self.sandbox.stderr_file = \
            self.sandbox.relative_path("compiler_stderr.txt")
        with async_lock:
            logger.info("Starting compilation")
        self.sandbox_operation("execute_without_std", command)

        # Detect the outcome of the compilation
        exit_status = self.sandbox.get_exit_status()
        exit_code = self.sandbox.get_exit_code()
        stdout = self.sandbox_operation("get_file_to_string",
                                        "compiler_stdout.txt")
        if stdout.strip() == "":
            stdout = "(empty)\n"
        stderr = self.sandbox_operation("get_file_to_string",
                                        "compiler_stderr.txt")
        if stderr.strip() == "":
            stderr = "(empty)\n"

        # Execution finished successfully: the submission was
        # correctly compiled
        if exit_status == Sandbox.EXIT_OK and exit_code == 0:
            digest = self.sandbox_operation(
                "get_file_to_storage",
                executable_filename,
                "Executable %s for submission %s" % \
                (executable_filename, self.submission.id))

            self.session.add(Executable(digest,
                                        executable_filename,
                                        self.submission))

            with async_lock:
                logger.info("Compilation successfully finished")
            return self.finish_compilation(
                True,
                True,
                "OK %s\n"
                "Compiler standard output:\n"
                "%s\n"
                "Compiler standard error:\n"
                "%s" % (self.sandbox.get_stats(), stdout, stderr))

        # Error in compilation: returning the error to the user
        if exit_status == Sandbox.EXIT_OK and exit_code != 0:
            with async_lock:
                logger.info("Compilation failed")
            return self.finish_compilation(
                True,
                False,
                "Failed %s\n"
                "Compiler standard output:\n"
                "%s\n"
                "Compiler standard error:\n"
                "%s" % (self.sandbox.get_stats(), stdout, stderr))

        # Timeout: returning the error to the user
        if exit_status == Sandbox.EXIT_TIMEOUT:
            with async_lock:
                logger.info("Compilation timed out")
            return self.finish_compilation(
                True,
                False,
                "Time out %s\n"
                "Compiler standard output:\n"
                "%s\n"
                "Compiler standard error:\n"
                "%s" % (self.sandbox.get_stats(), stdout, stderr))

        # Suicide with signal (probably memory limit): returning the
        # error to the user
        if exit_status == Sandbox.EXIT_SIGNAL:
            signal = self.sandbox.get_killing_signal()
            with async_lock:
                logger.info("Compilation killed with signal %d" % (signal))
            return self.finish_compilation(
                True,
                False,
                "Killed with signal %d %s\n"
                "This could be triggered by violating memory limits\n"
                "Compiler standard output:\n"
                "%s\n"
                "Compiler standard error:\n"
                "%s" % (signal, self.sandbox.get_stats(), stdout, stderr))

        # Sandbox error: this isn't a user error, the administrator
        # needs to check the environment
        if exit_status == Sandbox.EXIT_SANDBOX_ERROR:
            with async_lock:
                logger.error("Compilation aborted because of sandbox error")
            return self.finish_compilation(False)

        # Forbidden syscall: this shouldn't happen, probably the
        # administrator should relax the syscall constraints
        if exit_status == Sandbox.EXIT_SYSCALL:
            with async_lock:
                logger.error("Compilation aborted "
                             "because of forbidden syscall")
            return self.finish_compilation(False)

        # Forbidden file access: this could be triggered by the user
        # including a forbidden file or too strict sandbox contraints;
        # the administrator should have a look at it
        if exit_status == Sandbox.EXIT_FILE_ACCESS:
            with async_lock:
                logger.error("Compilation aborted "
                             "because of forbidden file access")
            return self.finish_compilation(False)

        # Why the exit status hasn't been captured before?
        with async_lock:
            logger.error("Shouldn't arrive here, failing")
        return self.finish_compilation(False)

    def evaluate_testcase(self, test_number):
        self.create_sandbox()
        self.sandbox_operation(
            "create_file_from_storage",
            self.executable_filename,
            self.submission.executables[self.executable_filename].digest,
            executable=True)
        self.sandbox_operation(
            "create_file_from_storage",
            "input.txt",
            self.submission.task.testcases[test_number].input)

        self.sandbox.chdir = self.sandbox.path
        self.sandbox.filter_syscalls = 2
        self.sandbox.timeout = self.submission.task.time_limit
        self.sandbox.address_space = self.submission.task.memory_limit * 1024
        self.sandbox.file_check = 1
        self.sandbox.allow_path = ["input.txt", "output.txt"]
        stdout_filename = os.path.join(self.sandbox.path,
                                       "submission_stdout.txt")
        stderr_filename = os.path.join(self.sandbox.path,
                                       "submission_stderr.txt")
        self.sandbox.stdout_file = stdout_filename
        self.sandbox.stderr_file = stderr_filename

        # These syscalls and paths are used by executables generated
        # by fpc.
        self.sandbox.allow_path += ["/proc/self/exe"]
        self.sandbox.allow_syscall += ["getrlimit", "rt_sigaction"]

        # This one seems to be used for a C++ executable.
        self.sandbox.allow_path += ["/proc/meminfo"]

        self.sandbox_operation(
            "execute_without_std",
            [self.sandbox.relative_path(self.executable_filename)])

        # Detect the outcome of the execution.
        exit_status = self.sandbox.get_exit_status()

        # Timeout: returning the error to the user
        if exit_status == Sandbox.EXIT_TIMEOUT:
            with async_lock:
                logger.info("Execution timed out")
            return self.finish_evaluation_testcase(test_number, True, 0.0,
                                                   "Execution timed out\n")

        # Suicide with signal (memory limit, segfault, abort):
        # returning the error to the user
        if exit_status == Sandbox.EXIT_SIGNAL:
            signal = self.sandbox.get_killing_signal()
            with async_lock:
                logger.info("Execution killed with signal %d" % (signal))
            return self.finish_evaluation_testcase(
                test_number, True, 0.0,
                "Execution killed with signal %d\n" % signal)

        # Sandbox error: this isn't a user error, the administrator
        # needs to check the environment
        if exit_status == Sandbox.EXIT_SANDBOX_ERROR:
            with async_lock:
                logger.error("Evaluation aborted because of sandbox error")
            return self.finish_evaluation_testcase(test_number, False)

        # Forbidden syscall: returning the error to the user
        # FIXME - Tell which syscall raised this error
        if exit_status == Sandbox.EXIT_SYSCALL:
            with async_lock:
                logger.info("Execution killed because of forbidden syscall")
            return self.finish_evaluation_testcase(
                test_number, True, 0.0,
                "Execution killed because of forbidden syscall")

        # Forbidden file access: returning the error to the user
        # FIXME - Tell which file raised this error
        if exit_status == Sandbox.EXIT_FILE_ACCESS:
            with async_lock:
                logger.info("Execution killed "
                            "because of forbidden file access")
            return self.finish_evaluation_testcase(
                test_number, True, 0.0,
                "Execution killed because of forbidden file access")

        # Last check before assuming that evaluation finished
        # successfully; we accept the evaluation even if the exit code
        # isn't 0
        if exit_status != Sandbox.EXIT_OK:
            with async_lock:
                logger.error("Shouldn't arrive here, failing")
            return self.finish_evaluation_testcase(test_number, False)

        if not self.sandbox.file_exists("output.txt"):
            outcome = 0.0
            text = "Evaluation didn't produce file output.txt"
            return self.finish_evaluation_testcase(test_number, True, outcome,
                                                   text)

        self.sandbox_operation(
            "create_file_from_storage",
            "res.txt",
            self.submission.task.testcases[test_number].output)
        self.sandbox.filter_syscalls = 2
        self.sandbox.timeout = 0
        self.sandbox.address_space = None
        self.sandbox.file_check = 1
        self.sandbox.allow_path = ["input.txt", "output.txt", "res.txt"]
        stdout_filename = os.path.join(self.sandbox.path, "manager_stdout.txt")
        stderr_filename = os.path.join(self.sandbox.path, "manager_stderr.txt")
        self.sandbox.stdout_file = stdout_filename
        self.sandbox.stderr_file = stderr_filename

        # No manager: I'll do a white_diff between output.txt and res.txt
        if len(self.submission.task.managers) == 0:
            out_file = self.sandbox_operation("get_file", "output.txt")
            res_file = self.sandbox_operation("get_file", "res.txt")
            if white_diff(out_file, res_file):
                outcome = 1.0
                text = "Output file is correct"
            else:
                outcome = 0.0
                text = "Output file isn't correct"

        # Manager present: wonderful, he'll do all the job
        else:
            manager_filename = self.submission.task.managers.keys()[0]
            self.sandbox_operation(
                "create_file_from_storage",
                manager_filename,
                self.submission.task.managers[manager_filename].digest,
                executable=True)
            self.sandbox_operation("execute_without_std",
                                   ["./%s" % (manager_filename),
                                    "input.txt", "res.txt", "output.txt"])
            with codecs.open(stdout_filename, "r", "utf-8") as stdout_file:
                with codecs.open(stderr_filename, "r", "utf-8") as stderr_file:
                    try:
                        outcome = stdout_file.readline().strip()
                    except UnicodeDecodeError as e:
                        with async_lock:
                            logger.error("Unable to interpret manager stdout "
                                         "(outcome) as unicode. %s" % repr(e))
                        return self.finish_evaluation_testcase(test_number,
                                                               False)
                    try:
                        text = filter_ansi_escape(stderr_file.readline())
                    except UnicodeDecodeError as e:
                        with async_lock:
                            logger.error("Unable to interpret manager stderr "
                                         "(text) as unicode. %s" % repr(e))
                        return self.finish_evaluation_testcase(test_number,
                                                               False)
            try:
                outcome = float(outcome)
            except ValueError:
                with async_lock:
                    logger.error("Wrong outcome `%s' from manager" % (outcome))
                return self.finish_evaluation_testcase(test_number, False)

        # Finally returns the result
        return self.finish_evaluation_testcase(test_number, True,
                                               outcome, text)

    def evaluate(self):
        """See TaskType.evaluate.

        return (bool): success of operation.

        """
        if len(self.submission.executables) != 1:
            with async_lock:
                logger.info("Submission contains %d executables, "
                            "expecting 1" %
                            len(self.submission.executables))
            return self.finish_evaluation(False)

        self.executable_filename = self.submission.executables.keys()[0]

        for test_number in xrange(len(self.submission.evaluations),
                                  len(self.submission.task.testcases)):
            self.session.add(Evaluation(text=None,
                                        outcome=None,
                                        num=test_number,
                                        submission=self.submission))

        for test_number in xrange(len(self.submission.task.testcases)):
            success = self.evaluate_testcase(test_number)
            if not success:
                return self.finish_evaluation(False)
        return self.finish_evaluation(True)
