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
import tempfile

from cms import config
from cms.grading.Sandbox import wait_without_std
from cms.grading import get_compilation_command
from cms.grading.TaskType import TaskType, \
     create_sandbox, delete_sandbox


HEADERS_MAP = {
    "c": "h",
    "cpp": "h",
    "pas": "lib.pas",
    }


class TwoSteps(TaskType):
    """Task type class for tasks where the user must submit two files
    with a function each; the first function compute some data, that
    get passed to the second function that must recover some data.

    The admins must provide a manager source file (for each language),
    called manager.%l, that get compiled with both two user sources,
    get the input as stdin, and get two parameters: 0 if it is the
    first instance, 1 if it is the second instance, and the name of
    the pipe.

    Admins must provide also header files, named *.HEADERS_MAP[%l] for
    the three sources (manager and user provided).

    """
    ALLOW_PARTIAL_SUBMISSION = False

    def compile(self):
        """See TaskType.compile."""
        # Detect the submission's language. The checks about the
        # formal correctedness of the submission are done in CWS,
        # before accepting it.
        language = self.submission.language
        header = HEADERS_MAP[language]

        # TODO: here we are sure that submission.files are the same as
        # task.submission_format. The following check shouldn't be
        # here, but in the definition of the task, since this actually
        # checks that task's task type and submission format agree.
        if len(self.submission.files) != 2:
            return self.finish_compilation(
                True, False, "Invalid files in submission",
                to_log="Submission contains %d files, expecting 2" %
                len(self.submission.files))

        # First and only one compilation.
        sandbox = create_sandbox(self)
        files_to_get = {}
        format_filenames = self.submission.files.keys()

        # User's submissions and headers.
        source_filenames = []
        for filename, _file in self.submission.files.iteritems():
            source_filename = filename.replace("%l", language)
            source_filenames.append(source_filename)
            files_to_get[source_filename] = _file.digest
            # Headers.
            header_filename = filename.replace("%l", header)
            source_filenames.append(header_filename)
            files_to_get[header_filename] = \
                self.submission.task.managers[header_filename].digest

        # Manager.
        manager_filename = "manager.%s" % language
        source_filenames.append(manager_filename)
        files_to_get[manager_filename] = \
                self.submission.task.managers[manager_filename].digest
        # Manager's header.
        manager_filename = "manager.%s" % header
        source_filenames.append(manager_filename)
        files_to_get[manager_filename] = \
                self.submission.task.managers[manager_filename].digest

        # Get compilation command and compile.
        executable_filename = "manager"
        command = get_compilation_command(language,
                                          source_filenames,
                                          executable_filename)
        operation_success, compilation_success, text = self.compilation_step(
            sandbox,
            command,
            files_to_get,
            {executable_filename: "Executable %s for submission %s" %
             (executable_filename, self.submission.id)})
        delete_sandbox(sandbox)

        # We had only one compilation, hence we pipe directly its
        # result to the finalization.
        return self.finish_compilation(operation_success, compilation_success,
                                       text)

    def evaluate_testcase(self, test_number):
        """See TaskType.evaluate_testcase."""
        # f stand for first, s for second.
        first_sandbox = create_sandbox(self)
        second_sandbox = create_sandbox(self)
        fifo_dir = tempfile.mkdtemp(dir=config.temp_dir)
        fifo = os.path.join(fifo_dir, "fifo")
        os.mkfifo(fifo)

        # First step: we start the first manager.
        first_filename = "manager"
        first_command = ["./%s" % first_filename, "0", fifo]
        first_executables_to_get = {
            first_filename:
            self.submission.executables[first_filename].digest
            }
        first_files_to_get = {
            "input.txt": self.submission.task.testcases[test_number].input
            }
        first_allow_path = ["input.txt", fifo]
        first = self.evaluation_step_before_run(
            first_sandbox,
            first_command,
            first_executables_to_get,
            first_files_to_get,
            self.submission.task.time_limit,
            0,
            first_allow_path,
            stdin_redirect="input.txt")

        # Second step: we start the second manager.
        second_filename = "manager"
        second_command = ["./%s" % second_filename, "1", fifo]
        second_executables_to_get = {
            second_filename:
            self.submission.executables[second_filename].digest
            }
        second_files_to_get = {
            "input.txt": self.submission.task.testcases[test_number].input
            }
        second_allow_path = [fifo, "input.txt", "output.txt"]
        second = self.evaluation_step_before_run(
            second_sandbox,
            second_command,
            second_executables_to_get,
            second_files_to_get,
            self.submission.task.time_limit,
            self.submission.task.memory_limit,
            second_allow_path,
            stdin_redirect="input.txt")

        # Consume output.
        wait_without_std([second, first])
        # TODO: check exit codes with translate_box_exitcode.

        success_first, outcome_first, text_first, _ = \
                      self.evaluation_step_after_run(first_sandbox, final=False)
        success_second, outcome_second, text_second, plus = \
                     self.evaluation_step_after_run(second_sandbox, final=True)

        # If at least one evaluation had problems, we report the
        # problems.
        if not success_first:
            success, outcome, text = False, outcome_first, text_first
        elif not success_second:
            success, outcome, text = False, outcome_second, text_second
        # Otherwise, we use the second evaluation to obtain the
        # outcome.
        else:
            success, outcome, text = success_second, outcome_second, text_second

        delete_sandbox(first_sandbox)
        delete_sandbox(second_sandbox)
        return self.finish_evaluation_testcase(
            test_number, success, outcome, text, plus)
