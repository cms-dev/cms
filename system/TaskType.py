#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright (C) 2010 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright (C) 2010 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright (C) 2010 Matteo Boscariol <boscarim@hotmail.com>
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
import subprocess

import Utils
from Sandbox import Sandbox
from Task import Task
from Worker import JobException

def get_task_type_class(submission):
    if submission.task.task_type == Task.TASK_TYPE_BATCH:
        return BatchTaskType(submission)
    else:
        return None

class BatchTaskType:
    def __init__(self, submission):
        self.submission = submission

    KEEP_SANDBOX = True

    def finish_compilation(self, success, compilation_success = False, text = ""):
        self.safe_delete_sandbox()
        if not success:
            return False
        if compilation_success:
            self.submission.compilation_outcome = "ok"
        else:
            self.submission.compilation_outcome = "fail"
        self.submission.compilation_text = text
        try:
            self.submission.to_couch()
            return True
        except (OSError, IOError) as e:
            Utils.log("Couldn't update database, aborting compilation (exception: %s)" % (repr(e)))
            return False

    def finish_single_evaluation(self, test_number, success, outcome = 0, text = ""):
        self.safe_delete_sandbox()
        if not success:
            return False
        self.submission.evaluation_outcome[test_number] = outcome
        self.submission.evaluation_text[test_number] = text
        return True

    def finish_evaluation(self, success):
        if not success:
            return False
        self.submission.to_couch()
        return True

    def safe_delete_sandbox(self):
        if "sandbox" in self.__dict__ and not self.KEEP_SANDBOX:
            try:
                self.sandbox.delete()
            except (IOError, OSError):
                Utils.log("Couldn't delete sandbox", Utils.Logger.SEVERITY_IMPORTANT)

    def safe_create_sandbox(self):
        try:
            self.sandbox = Sandbox()
        except (OSError, IOError):
            Utils.log("Couldn't create sandbox", Utils.Logger.SEVERITY_IMPORTANT)
            self.safe_delete_sandbox()
            raise JobException()

    def safe_create_file_from_storage(self, name, digest, executable = False):
        try:
            self.sandbox.create_file_from_storage(name, digest, executable)
        except (OSError, IOError):
            Utils.log("Couldn't copy file `%s' in sandbox" % (name), Utils.Logger.SEVERITY_IMPORTANT)
            self.safe_delete_sandbox()
            raise JobException()

    def safe_get_file_to_storage(self, name, msg = ""):
        try:
            return self.sandbox.get_file_to_storage(name, msg)
        except (IOError, OSError) as e:
            Utils.log("Coudln't retrieve file `%s' from storage" % (name), Utils.Logger.SEVERITY_IMPORTANT)
            self.safe_delete_sandbox()
            raise JobException()

    def safe_get_file_to_string(self, name):
        try:
            return self.sandbox.get_file_to_string(name)
        except (IOError, OSError):
            Utils.log("Couldn't retrieve file `%s' from storage" % (name), Utils.Logger.SEVERITY_IMPORTANT)
            self.safe_delete_sandbox()
            raise JobException()

    def safe_sandbox_execute(self, command):
        try:
            self.sandbox.execute(command)
        except (OSError, IOError) as e:
            Utils.log("Couldn't spawn `%s' (exception %s)" % (command[0], repr(e)))
            self.safe_delete_sandbox()
            raise JobException()

    def compile(self):
        """Tries to compile the specified submission.

        It returns True when the compilation is successful or when the
        submission cannot be compiled successfully, and False when the
        compilation fails because of environment problems (trying
        again to compile the same submission in a sane environment
        should lead to returning True).
        """

        # Detect the submission's language and check that it contains
        # exactly one source file
        valid, language = self.submission.verify_source()
        if not valid or language == None:
            Utils.log("Invalid submission or couldn't detect language")
            return self.finish_compilation(True, False, "Invalid files in submission")
        if len(self.submission.files) != 1:
            Utils.log("Submission cointains %d files, expecting 1" % (len(self.submission.files)))
            return self.finish_compilation(True, False, "Invalid files in submission")

        source_filename = self.submission.files.keys()[0]
        executable_filename = source_filename.replace(".%s" % (language), "")

        # Setup the compilation environment
        self.safe_create_sandbox()
        self.safe_create_file_from_storage(source_filename, self.submission.files[source_filename])

        if language == "c":
            command = ["/usr/bin/gcc", "-DEVAL", "-static", "-O2", "-lm", "-o", executable_filename, source_filename]
        elif language == "cpp":
            command = ["/usr/bin/g++", "-DEVAL", "-static", "-O2", "-o", executable_filename, source_filename]
        elif language == "pas":
            command = ["/usr/bin/fpc", "-dEVAL", "-XS", "-O2", "-o%s" % (executable_filename), source_filename]

        # Execute the compilation inside the sandbox
        self.sandbox.chdir = self.sandbox.path
        self.sandbox.preserve_env = True
        self.sandbox.filter_syscalls = 1
        self.sandbox.allow_fork = True
        self.sandbox.file_check = 2
        # FIXME - File access limits are not enforced on children
        # processes (like ld); and these paths are tested only with
        # g++ (I believe gcc to be ok too, but I never tried fpc)
        self.sandbox.set_env['TMPDIR'] = self.sandbox.path
        self.sandbox.allow_path = ['/etc/', '/lib/', '/usr/', '%s/' % (self.sandbox.path)]
        self.sandbox.timeout = 10
        self.sandbox.address_space = 256 * 1024
        self.sandbox.stdout_file = self.sandbox.relative_path("compiler_stdout.txt")
        self.sandbox.stderr_file = self.sandbox.relative_path("compiler_stderr.txt")
        Utils.log("Starting compilation")
        self.safe_sandbox_execute(command)

        # Detect the outcome of the compilation
        exit_status = self.sandbox.get_exit_status()
        exit_code = self.sandbox.get_exit_code()
        stderr = self.safe_get_file_to_string("compiler_stderr.txt")
        if stderr == "":
            stderr = "(empty)\n"

        # Execution finished successfully: the submission was
        # correctly compiled
        if exit_status == Sandbox.EXIT_OK and exit_code == 0:
            self.submission.executables = {executable_filename: self.safe_get_file_to_storage(executable_filename, "Executable %s for submission %s" % (executable_filename, self.submission.couch_id))}
            Utils.log("Compilation successfully finished")
            return self.finish_compilation(True, True, "OK %s\nCompiler output:\n%s" % (self.sandbox.get_stats(), stderr))                

        # Error in compilation: returning the error to the user
        if exit_status == Sandbox.EXIT_OK and exit_code != 0:
            Utils.log("Compilation failed")
            return self.finish_compilation(True, False, "Failed %s\nCompiler output:\n%s" % (self.sandbox.get_stats(), stderr))

        # Timeout: returning the error to the user
        if exit_status == Sandbox.EXIT_TIMEOUT:
            Utils.log("Compilation timed out")
            return self.finish_compilation(True, False, "Time out %s\nCompiler output:\n%s" % (self.sandbox.get_stats(), stderr))

        # Suicide with signale (probably memory limit): returning the
        # error to the user
        if exit_status == Sandbox.EXIT_SIGNAL:
            signal = self.sandbox.get_killing_signal()
            Utils.log("Compilation killed with signal %d" % (signal))
            return self.finish_compilation(True, False, "Killed with signal %d %s\nThis could be triggered by violating memory limits\nCompiler output:\n%s" % (signal, self.sandbox.get_stats(), stderr))

        # Sandbox error: this isn't a user error, the administrator
        # needs to check the environment
        if exit_status == Sandbox.EXIT_SANDBOX_ERROR:
            Utils.log("Compilation aborted because of sandbox error", Utils.Logger.SEVERITY_IMPORTANT)
            return self.finish_compilation(False)

        # Forbidden syscall: this shouldn't happen, probably the
        # administrator should relax the syscall constraints
        if exit_status == Sandbox.EXIT_SYSCALL:
            Utils.log("Compilation aborted because of forbidden syscall", Utils.Logger.SEVERITY_IMPORTANT)
            return self.finish_compilation(False)

        # Forbidden file access: this could be triggered by the user
        # including a forbidden file or too strict sandbox contraints;
        # the administrator should have a look at it
        if exit_status == Sandbox.EXIT_FILE_ACCESS:
            Utils.log("Compilation aborted because of forbidden file access", Utils.Logger.SEVERITY_IMPORTANT)
            return self.finish_compilation(False)

        # Why the exit status hasn't been captured before?
        Utils.log("Shouldn't arrive here, failing", Utils.Logger.SEVERITY_IMPORTANT)
        return self.finish_compilation(False)

    def execute_single(self, test_number):
        self.safe_create_sandbox()
        self.safe_create_file_from_storage(self.executable_filename, self.submission.executables[self.executable_filename], executable = True)
        self.safe_create_file_from_storage("input.txt", self.submission.task.testcases[test_number][0])
            
        self.sandbox.chdir = self.sandbox.path
        self.sandbox.filter_syscalls = 2
        self.sandbox.timeout = self.submission.task.time_limit
        self.sandbox.address_space = self.submission.task.memory_limit * 1024
        self.sandbox.file_check = 1
        self.sandbox.allow_path = ["input.txt", "output.txt"]
        # FIXME - Differentiate between compilation errors and popen errors
        # FIXME - Detect sandbox problems (timeout, out of memory, ...)
        self.safe_sandbox_execute([self.sandbox.relative_path(self.executable_filename)])

        if not self.sandbox.file_exists("output.txt"):
            outcome = 0.0
            text = "Execution didn't produce file output.txt"
            return self.finish_single_evaluation(test_number, True, outcome, text)

        self.safe_create_file_from_storage("res.txt", self.submission.task.testcases[test_number][1])
        self.sandbox.filter_syscalls = 2
        self.sandbox.timeout = 0
        self.sandbox.address_space = None
        self.sandbox.file_check = 1
        self.sandbox.allow_path = ["input.txt", "output.txt", "res.txt"]
        stdout_filename = os.path.join(self.sandbox.path, "manager_stdout.txt")
        stderr_filename = os.path.join(self.sandbox.path, "manager_stderr.txt")
        self.sandbox.stdout_file = stdout_filename
        self.sandbox.stderr_file = stderr_filename
        if len(self.submission.task.managers) == 0:
            # FIXME - Not the correct way to extract exit code
            # FIXME - Security constraints too strict for diff, probably it should be better implementing it in Python
            diff_return = self.safe_sandbox_execute(["/usr/bin/diff", "-w", "output.txt", "res.txt"])
            if diff_return == 0:
                outcome = 1.0
                text = "Output file is correct"
            else:
                outcome = 0.0
                text = "Output file isn't correct"
        else:
            manager_filename = self.submission.task.managers.keys()[0]
            self.safe_create_file_from_storage(manager_filename, self.submission.task.managers[manager_filename], executable = True)
            manager_popen = self.safe_sandbox_execute(["./%s" % (manager_filename), "input.txt", "res.txt", "output.txt"])
            with open(stdout_filename) as stdout_file:
                with open(stderr_filename) as stderr_file:
                    outcome = stdout_file.readline().strip()
                    text = Utils.filter_ansi_escape(stderr_file.readline())
            try:
                outcome = float(outcome)
            except ValueError:
                # FIXME - This should be considered as an error for the administrator
                Utils.log("Wrong outcome `%s' from manager" % (outcome), Utils.Logger.SEVERITY_IMPORTANT)
                return self.finish_single_evaluation(test_number, False)
        return self.finish_single_evaluation(test_number, True, outcome, text)

    def execute(self):
        if len(self.submission.executables) != 1:
            Utils.log("Submission contains %d executables, expecting 1" % (len(self.submission.executables)))
            return self.finish_evaluation(False)

        self.executable_filename = self.submission.executables.keys()[0]
        self.submission.evaluation_outcome = [None] * len(self.submission.task.testcases)
        self.submission.evaluation_text = [None] * len(self.submission.task.testcases)

        for test_number in range(len(self.submission.task.testcases)):
            success = self.execute_single(test_number)
            if not success:
                return self.finish_evaluation(False)
        return self.finish_evaluation(True)
