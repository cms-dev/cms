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

from Sandbox import Sandbox
import FileStorageLib
import Task
import Utils
from Utils import log

def get_task_type_class(task_type):
    if task_type == Task.Task.TASK_TYPE_BATCH:
        return BatchTaskType()
    else:
        return None

class BatchTaskType:
    def compile(self, submission):
        valid, language = submission.verify_source()
        if not valid or language == None:
            log("Invalid files in submission %s, detected language %s" % (submission.couch_id, str(language)))
            return False
        if len(submission.files) != 1:
            log("Submission %s cointains %d files, expecting 1" % (submission.couch_id, len(submission.files)))
            return False
        source_filename = submission.files.keys()[0]
        executable_filename = source_filename.replace(".%s" % (language), "")
        sandbox = Sandbox()
        log("Created sandbox for submission %s in %s" % (submission.couch_id, sandbox.path))
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
        log("Starting compiling submission %s with command line: %s" % (submission.couch_id, command))
        compilation_return = sandbox.execute(command.split(" "))
        if compilation_return == 0:
            submission.executables = {}
            submission.executables[executable_filename] = sandbox.get_file_to_storage(executable_filename)
            submission.compilation_result = "OK"
            log("Compilation for submission %s successfully terminated" % (submission.couch_id))
        else:
            log("Compilation for submission %s failed" % (submission.couch_id))
            submission.compilation_result = "Failed"
        submission.to_couch()
        #sandbox.delete()
        #log("Sandbox deleted")
        return compilation_return == 0

    def execute(self, submission):
        pass
