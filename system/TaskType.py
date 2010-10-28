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

def get_task_type_class(submission):
    if submission.task.task_type == Task.TASK_TYPE_BATCH:
        return BatchTaskType(submission)
    else:
        return None

class BatchTaskType:
    def __init__(self, submission):
        self.submission = submission

    def finish_compilation(self, success, compilation_success = False, text = ""):
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
        except Exception as e:
            Utils.log("Couldn't update database, aborting compilation (exception: %s)" % (repr(e)))
            return False

    def compile(self):
        """Tries to compile the specified submission.

        It returns True when the compilation is successful or when the
        submission cannot be compiled successfully, and False when the
        compilation fails because of environment problems (trying
        again to compile the same submission in a sane environment
        should lead to returning True).
        """
        valid, language = self.submission.verify_source()
        if not valid or language == None:
            Utils.log("Invalid submission or couldn't detect language")
            return self.terminate_compilation("Invalid files in submission")
        if len(self.submission.files) != 1:
            Utils.log("Submission %s cointains %d files, expecting 1" % (self.submission.couch_id, len(self.submission.files)))
            return self.terminate_compilation("Invalid files in submission")

        source_filename = self.submission.files.keys()[0]
        executable_filename = source_filename.replace(".%s" % (language), "")

        try:
            sandbox = Sandbox()
        except:
            Utils.log("Couldn't create sandbox when compiling submission %s" % (self.submission.couch_id), Utils.Logger.SEVERITY_IMPORTANT)
            return False
        Utils.log("Created sandbox in %s for compiling submission %s" % (sandbox.path, self.submission.couch_id))

        try:
            sandbox.create_file_from_storage(source_filename, self.submission.files[source_filename])
        except:
            Utils.log("Couldn't copy file %s in sandbox %s when compiling submission %s" % (source_filename, sandbox.path, self.submission.couch_id))
            return False

        if language == "c":
            command = ["/usr/bin/gcc", "-DEVAL", "-static", "-O2", "-lm", "-o", executable_filename, source_filename]
        elif language == "cpp":
            command = ["/usr/bin/g++", "-DEVAL", "-static", "-O2", "-o", executable_filename, source_filename]
        elif language == "pas":
            command = ["/usr/bin/gpc", "-dEVAL", "-XS", "-O2", "-o%s" % (executable_filename), source_filename]
        sandbox.chdir = sandbox.path
        sandbox.preserve_env = True
        sandbox.filter_syscalls = 0
        sandbox.file_check = 9
        sandbox.timeout = 10
        sandbox.address_space = 256 * 1024
        sandbox.stdout_file = sandbox.relative_path("compiler_stdout.txt")
        sandbox.stderr_file = sandbox.relative_path("compiler_stderr.txt")
        Utils.log("Compiling submission %s" % (self.submission.couch_id))
        try:
            sandbox.execute(command)
        except:
            Utils.log("Couldn't spawn sandbox when trying to compile submission %s" % (self.submission.couch_id))
            return False

        executable_present = True
        try:
            sandbox.stat_file(executable_filename)
        except OSError:
            executable_present = False

        exit_status = sandbox.get_exit_status()
        exit_code = sandbox.get_exit_code()
        if exit_status == Sandbox.EXIT_OK and exit_code == 0:
            try:
                self.submission.executables = {}
                self.submission.executables[executable_filename] = sandbox.get_file_to_storage(executable_filename, "Executable %s for submission %s" % (executable_filename, self.submission.couch_id))
                self.submission.compilation_text = "OK %s\n" % (sandbox.get_stats())
                self.submission.compilation_outcome = "ok"
                self.submission.to_couch()
                Utils.log("Compilation for submission %s successfully finished" % (self.submission.couch_id))
                return True
            except (IOError, OSError) as e:
                Utils.log("Compilation for submission %s successfully finished, but coudln't update the database (exception: %s)" % (self.submission.couch_id, repr(e)), Utils.Logger.SEVERITY_IMPORTANT)
                return False

        if exit_status == Sandbox.EXIT_OK and exit_code != 0:
            try:
                error = sandbox.get_file_to_string("compiler_stderr.txt")
                self.submission.compilation_text = "Failed %s\nCompiler output:\n%s" % (sandbox.get_stats(), error)
                self.submission.compilation_outcome = "fail"
                self.submission.to_couch()
                Utils.log("Compilation for submission %s failed" % (self.submission.couch_id))
                return True
            except (IOError, OSError) as e:
                Utils.log("Compilation for submission %s failed, but couldn't update the database (exception: %s)" % (self.submission.couch_id, repr(e)), Utils.Logger.SEVERITY_IMPORTANT)
                return False

        if exit_status == Sandbox.EXIT_SANDBOX_ERROR:
            Utils.log("Sandbox error")

        if exit_status == Sandbox.EXIT_SYSCALL:
            Utils.log("Forbidden syscall")

        if exit_status == Sandbox.EXIT_FILE_ACCESS:
            Utils.log("Forbidden file access")

        if exit_status == Sandbox.EXIT_TIMEOUT:
            Utils.log("Timeout")

        if exit_status == Sandbox.EXIT_SIGNAL:
            Utils.log("Killed with signal")

        #sandbox.delete()
        #Utils.log("Sandbox for compiling submission %s deleted" % (self.submission.couch_id))
        return True

    def execute_single(self, test_number):
        executable_filename = self.submission.executables.keys()[0]
        sandbox = Sandbox()
        sandbox.create_file_from_storage(executable_filename, self.submission.executables[executable_filename], executable = True)
        sandbox.create_file_from_storage("input.txt", self.submission.task.testcases[test_number][0])
        sandbox.chdir = sandbox.path
        # FIXME - The sandbox isn't working as expected when filtering syscalls
        sandbox.filter_syscalls = 0
        sandbox.timeout = self.submission.task.time_limit
        sandbox.address_space = self.submission.task.memory_limit * 1024
        sandbox.file_check = 0
        sandbox.allow_path = [ os.path.join(sandbox.path, "input.txt"), os.path.join(sandbox.path, "output.txt") ]
        # FIXME - Differentiate between compilation errors and popen errors
        # FIXME - Detect sandbox problems (timeout, out of memory, ...)
        execution_return = sandbox.execute([os.path.join(sandbox.path, executable_filename)])
        sandbox.create_file_from_storage("res.txt", self.submission.task.testcases[test_number][1])
        # The diff or the manager are executed with relaxed security constraints
        sandbox.filter_syscalls = 0
        sandbox.timeout = 0
        sandbox.address_space = None
        sandbox.file_check = 3
        sandbox.allow_path = []
        if len(self.submission.task.managers) == 0:
            diff_return = sandbox.execute_without_std(["/usr/bin/diff", "-w",
                                                       os.path.join(sandbox.path, "output.txt"),
                                                       os.path.join(sandbox.path, "res.txt")])
            if diff_return == 0:
                self.submission.evaluation_outcome[test_number] = 1.0
                self.submission.evaluation_text[test_number] = "OK"
            else:
                self.submission.evaluation_outcome[test_number] = 0.0
                self.submission.evaluation_text[test_number] = "Failed"
        else:
            manager_filename = self.submission.task.managers.keys()[0]
            sandbox.create_file_from_storage(manager_filename, self.submission.task.managers[manager_filename], executable = True)
            stdout_filename = os.path.join(sandbox.path, "manager_stdout.txt")
            stderr_filename = os.path.join(sandbox.path, "manager_stderr.txt")
            sandbox.stdout_file = stdout_filename
            sandbox.stderr_file = stderr_filename
            manager_popen = sandbox.execute_without_std(["./%s" % (manager_filename),
                                                         os.path.join(sandbox.path, "input.txt"),
                                                         os.path.join(sandbox.path, "res.txt"), 
                                                         os.path.join(sandbox.path, "output.txt")])
            with open(stdout_filename) as stdout_file:
                with open(stderr_filename) as stderr_file:
                    value = stdout_file.readline()
                    text = Utils.filter_ansi_escape(stderr_file.readline())
            try:
                value = float(value)
            except ValueError:
                Utils.log("Wrong value `%s' from manager when evaluating submission %s" % (value.strip(), self.submission.couch_id))
                value = 0.0
                text = "Error while evaluating"
            self.submission.evaluation_outcome[test_number] = value
            self.submission.evaluation_text[test_number] = text
        self.submission.to_couch()
        #sandbox.delete()

    def execute(self):
        if len(self.submission.executables) != 1:
            Utils.log("Submission %s contains %d executables, expecting 1" % (self.submission.couch_id, len(self.submission.executables)))
            return False
        self.submission.evaluation_outcome = [None] * len(self.submission.task.testcases)
        self.submission.evaluation_text = [None] * len(self.submission.task.testcases)
        self.submission.to_couch()
        for test_number in range(len(self.submission.task.testcases)):
            self.execute_single(test_number)
        return True
