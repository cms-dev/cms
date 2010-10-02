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

def get_task_type_class(task_type):
    if task_type == Task.TASK_TYPE_BATCH:
        return BatchTaskType()
    else:
        return None

class BatchTaskType:
    def compile(self, submission):
        valid, language = submission.verify_source()
        if not valid or language == None:
            Utils.log("Invalid files in submission %s, detected language %s" % (submission.couch_id, str(language)))
            return False
        if len(submission.files) != 1:
            Utils.log("Submission %s cointains %d files, expecting 1" % (submission.couch_id, len(submission.files)))
            return False
        source_filename = submission.files.keys()[0]
        executable_filename = source_filename.replace(".%s" % (language), "")
        sandbox = Sandbox()
        Utils.log("Created sandbox for compiling submission %s in %s" % (submission.couch_id, sandbox.path))
        sandbox.create_file_from_storage(source_filename, submission.files[source_filename])
        if language == "c":
            command = "/usr/bin/gcc -DEVAL -static -O2 -lm -o %s %s" % (executable_filename, source_filename)
        elif language == "cpp":
            command = "/usr/bin/g++ -DEVAL -static -O2 -o %s %s" % (executable_filename, source_filename)
        elif language == "pas":
            command = "/usr/bin/gpc -dEVAL -XS -O2 -o %s %s" % (executable_filename, source_filename)
        sandbox.chdir = sandbox.path
        sandbox.preserve_env = True
        sandbox.filter_syscalls = 0
        sandbox.timeout = 10
        sandbox.address_space = 256 * 1024
        Utils.log("Starting compiling submission %s with command line: %s" % (submission.couch_id, command))
        # FIXME - Differentiate between compilation errors and popen errors
        try:
            compilation_return = sandbox.execute(command.split(" "))
        except:
            compilation_return = 1
        if compilation_return == 0:
            submission.executables = {}
            submission.executables[executable_filename] = sandbox.get_file_to_storage(executable_filename)
            submission.compilation_result = "OK"
            Utils.log("Compilation for submission %s successfully terminated" % (submission.couch_id))
        else:
            Utils.log("Compilation for submission %s failed" % (submission.couch_id))
            submission.compilation_result = "Failed"
        submission.to_couch()
        sandbox.delete()
        Utils.log("Sandbox for compiling submission %s deleted" % (submission.couch_id))
        return compilation_return == 0

    def execute_single(self, submission, test_number):
        executable_filename = submission.executables.keys()[0]
        sandbox = Sandbox()
        sandbox.create_file_from_storage(executable_filename, submission.executables[executable_filename], executable = True)
        sandbox.create_file_from_storage("input.txt", submission.task.testcases[test_number][0])
        sandbox.chdir = sandbox.path
        # FIXME - The sandbox isn't working as expected when filtering syscalls
        sandbox.filter_syscalls = 0
        sandbox.timeout = submission.task.time_limit
        sandbox.address_space = submission.task.memory_limit * 1024
        sandbox.file_check = 0
        sandbox.allow_path = [ os.path.join(sandbox.path, "input.txt"), os.path.join(sandbox.path, "output.txt") ]
        execution_return = sandbox.execute([os.path.join(sandbox.path, executable_filename)])
        sandbox.create_file_from_storage("res.txt", submission.task.testcases[test_number][1])
        # The diff or the manager are executed with relaxed security constraints
        sandbox.filter_syscalls = 0
        sandbox.timeout = 0
        sandbox.address_space = None
        sandbox.file_check = 3
        sandbox.allow_path = []
        if len(submission.task.managers) == 0:
            diff_return = sandbox.execute_without_std(["/usr/bin/diff", "-w",
                                                       os.path.join(sandbox.path, "output.txt"),
                                                       os.path.join(sandbox.path, "res.txt")])
            if diff_return == 0:
                submission.outcome[test_number] = 1.0
            else:
                submission.outcome[test_number] = 0.0
        else:
            manager_filename = submission.task.managers.keys()[0]
            sandbox.create_file_from_storage(manager_filename, submission.task.managers[manager_filename], executable = True)
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
                    # FIXME - Do someting with text
                    text = stderr_file.readline()
            try:
                value = float(value)
            except ValueError:
                Utils.log("Wrong value `%s' from manager when evaluating submission %s" % (value.strip(), submission.couch_id))
                value = 0.0
            submission.outcome[test_number] = value
        submission.to_couch()
        #sandbox.delete()

    def execute(self, submission):
        if len(submission.executables) != 1:
            Utils.log("Submission %s contains %d executables, expecting 1" % (submission.couch_id, len(submission.executables)))
            return False
        submission.outcome = [None] * len(submission.task.testcases)
        for test_number in range(len(submission.task.testcases)):
            self.execute_single(submission, test_number)
        submission.evaluation_status = "OK"
        submission.to_couch()
        return True
