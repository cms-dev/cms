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


class Communication(TaskType):
    """Task type class for tasks that requires:

    - a *manager* that reads the input file, work out the perfect
      solution on its own, and communicate the input (maybe with some
      modifications) on its standard output; it then reads the
      responsed of the users' solutions from the standard input and
      write the outcome on the output file;

    - a *stub* that compiles with the users' solutions, and reads from
      standard input what the manager says, and write back the users'
      solutions to the standard output.

    """
    ALLOW_PARTIAL_SUBMISSION = False

    def compile(self):
        """See TaskType.compile."""
        # Detect the submission's language. The checks about the
        # formal correctedness of the submission are done in CWS,
        # before accepting it.
        language = self.submission.language

        # TODO: here we are sure that submission.files are the same as
        # task.submission_format. The following check shouldn't be
        # here, but in the definition of the task, since this actually
        # checks that task's task type and submission format agree.
        if len(self.submission.files) != 1:
            return self.finish_compilation(
                True, False, "Invalid files in submission",
                to_log="Submission contains %d files, expecting 1" %
                len(self.submission.files))

        # First and only one compilation.
        sandbox = create_sandbox(self)
        files_to_get = {}
        format_filename = self.submission.files.keys()[0]
        # User's submission.
        source_filenames = [format_filename.replace("%l", language)]
        files_to_get[source_filenames[0]] = \
            self.submission.files[format_filename].digest
        # Stub.
        source_filenames.append("stub.%s" % language)
        files_to_get[source_filenames[1]] = \
                self.submission.task.managers["stub.%s" % language].digest
        executable_filename = format_filename.replace(".%l", "")
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
        sandbox_mgr = create_sandbox(self)
        sandbox_user = create_sandbox(self)
        fifo_dir = tempfile.mkdtemp(config.temp_dir)
        fifo_in = os.path.join(fifo_dir, "in")
        fifo_out = os.path.join(fifo_dir, "out")
        os.mkfifo(fifo_in)
        os.mkfifo(fifo_out)

        # First step: we start the manager.
        manager_filename = "manager"
        manager_command = ["./%s" % manager_filename, fifo_in, fifo_out]
        manager_executables_to_get = {
            manager_filename:
            self.submission.task.managers[manager_filename].digest
            }
        manager_files_to_get = {
            "input.txt": self.submission.task.testcases[test_number].input
            }
        manager_allow_path = ["input.txt", "output.txt", fifo_in, fifo_out]
        manager = self.evaluation_step_before_run(
            sandbox_mgr,
            manager_command,
            manager_executables_to_get,
            manager_files_to_get,
            self.submission.task.time_limit,
            0,
            manager_allow_path,
            stdin_redirect="input.txt")

        # First step: we start the user submission compiled with the
        # stub.
        executable_filename = self.submission.executables.keys()[0]
        command = ["./%s" % executable_filename, fifo_out, fifo_in]
        executables_to_get = {
            executable_filename:
            self.submission.executables[executable_filename].digest
            }
        allow_path = [fifo_in, fifo_out]
        process = self.evaluation_step_before_run(
            sandbox_user,
            command,
            executables_to_get,
            {},
            self.submission.task.time_limit,
            self.submission.task.memory_limit,
            allow_path)

        # Consume output.
        wait_without_std([process, manager])
        # TODO: check exit codes with translate_box_exitcode.

        success_user, outcome_user, text_user = \
                      self.evaluation_step_after_run(sandbox_user, final=False)
        success_mgr, outcome_mgr, text_mgr = \
                     self.evaluation_step_after_run(sandbox_mgr, final=True)

        # If at least one evaluation had problems, we report the
        # problems.
        if not success_user or not success_mgr:
            success, outcome, text = False, outcome_user, text_user
        # If outcome_user is not None, it means that there has been
        # some errors in the user solution, and outcome and text are
        # meaningful, so we use them.
        elif outcome_user is not None:
            success, outcome, text = success_user, outcome_user, text_user
        # Otherwise, we use the manager to obtain the outcome.
        else:
            success, outcome, text = success_mgr, outcome_mgr, text_mgr

        delete_sandbox(sandbox_mgr)
        delete_sandbox(sandbox_user)
        return self.finish_evaluation_testcase(test_number,
                                               success, outcome, text)
