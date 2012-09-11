#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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
from cms.grading import get_compilation_command, compilation_step, \
    evaluation_step_before_run, evaluation_step_after_run, is_evaluation_passed, \
    human_evaluation_message, white_diff_step
from cms.grading.TaskType import TaskType, \
     create_sandbox, delete_sandbox
from cms.db.SQLAlchemyAll import Submission, Executable


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

    name = "Two steps"

    def get_compilation_commands(self, submission_format):
        """See TaskType.get_compilation_commands."""
        res = dict()
        for language in Submission.LANGUAGES:
            header = HEADERS_MAP[language]
            source_filenames = []
            for filename in submission_format:
                source_filename = filename.replace("%l", language)
                source_filenames.append(source_filename)
                # Headers.
                header_filename = filename.replace("%l", header)
                source_filenames.append(header_filename)

            # Manager.
            manager_source_filename = "manager.%s" % language
            source_filenames.append(manager_source_filename)
            # Manager's header.
            manager_header_filename = "manager.%s" % header
            source_filenames.append(manager_header_filename)

            # Get compilation command and compile.
            executable_filename = "manager"
            command = " ".join(get_compilation_command(language,
                                                       source_filenames,
                                                       executable_filename))
            res[language] = [command]
        return res

    def compile(self):
        """See TaskType.compile."""
        # Detect the submission's language. The checks about the
        # formal correctedness of the submission are done in CWS,
        # before accepting it.
        language = self.job.language
        header = HEADERS_MAP[language]

        # TODO: here we are sure that submission.files are the same as
        # task.submission_format. The following check shouldn't be
        # here, but in the definition of the task, since this actually
        # checks that task's task type and submission format agree.
        if len(self.job.files) != 2:
            self.job.success = True
            self.job.compilation_success = False
            self.job.text = "Invalid files in submission"
            logger.warning("Submission contains %d files, expecting 2" %
                           len(self.job.files))
            return True

        # First and only one compilation.
        sandbox = create_sandbox(self)
        self.job.sandboxes.append(sandbox.path)
        files_to_get = {}

        # User's submissions and headers.
        source_filenames = []
        for filename, _file in self.job.files.iteritems():
            source_filename = filename.replace("%l", language)
            source_filenames.append(source_filename)
            files_to_get[source_filename] = _file.digest
            # Headers.
            header_filename = filename.replace("%l", header)
            source_filenames.append(header_filename)
            files_to_get[header_filename] = \
                self.job.managers[header_filename].digest

        # Manager.
        manager_filename = "manager.%s" % language
        source_filenames.append(manager_filename)
        files_to_get[manager_filename] = \
                self.job.managers[manager_filename].digest
        # Manager's header.
        manager_filename = "manager.%s" % header
        source_filenames.append(manager_filename)
        files_to_get[manager_filename] = \
                self.job.managers[manager_filename].digest

        for filename, digest in files_to_get.iteritems():
            sandbox.create_file_from_storage(filename, digest)

        # Get compilation command and compile.
        executable_filename = "manager"
        command = get_compilation_command(language,
                                          source_filenames,
                                          executable_filename)
        operation_success, compilation_success, text, plus = \
            compilation_step(sandbox, command)

        # Retrieve the compiled executables
        self.job.success = operation_success
        self.job.compilation_success = compilation_success
        self.job.plus = plus
        self.job.text = text
        if operation_success and compilation_success:
            digest = sandbox.get_file_to_storage(
                executable_filename,
                "Executable %s for %s" %
                (executable_filename, self.job.info))
            self.job.executables[executable_filename] = \
                Executable(digest, executable_filename)

        # Cleanup
        delete_sandbox(sandbox)

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
            self.job.executables[first_filename].digest
            }
        first_files_to_get = {
            "input.txt": self.job.testcases[test_number].input
            }
        first_allow_path = ["input.txt", fifo]

        # Put the required files into the sandbox
        for filename, digest in first_executables_to_get.iteritems():
            first_sandbox.create_file_from_storage(filename, digest, executable=True)
        for filename, digest in first_files_to_get.iteritems():
            first_sandbox.create_file_from_storage(filename, digest)

        first = evaluation_step_before_run(
            first_sandbox,
            first_command,
            self.job.time_limit,
            self.job.memory_limit,
            first_allow_path,
            stdin_redirect="input.txt",
            wait=False)

        # Second step: we start the second manager.
        second_filename = "manager"
        second_command = ["./%s" % second_filename, "1", fifo]
        second_executables_to_get = {
            second_filename:
            self.job.executables[second_filename].digest
            }
        second_files_to_get = {}
        second_allow_path = [fifo, "output.txt"]

        # Put the required files into the second sandbox
        for filename, digest in second_executables_to_get.iteritems():
            second_sandbox.create_file_from_storage(filename, digest, executable=True)
        for filename, digest in second_files_to_get.iteritems():
            second_sandbox.create_file_from_storage(filename, digest)

        second = evaluation_step_before_run(
            second_sandbox,
            second_command,
            self.job.time_limit,
            self.job.memory_limit,
            second_allow_path,
            stdout_redirect="output.txt",
            wait=False)

        # Consume output.
        wait_without_std([second, first])
        # TODO: check exit codes with translate_box_exitcode.

        success_first, first_plus = \
            evaluation_step_after_run(first_sandbox)
        success_second, second_plus = \
            evaluation_step_after_run(second_sandbox)

        self.job.evaluations[test_number] = {'sandboxes': [first_sandbox.path,
                                                           second_sandbox.path],
                                             'plus': second_plus}
        outcome = None
        text = None
        evaluation = self.job.evaluations[test_number]
        success = True

        # Error in the sandbox: report failure!
        if not success_first or not success_second:
            success = False

        # Contestant's error: the marks won't be good
        elif not is_evaluation_passed(first_plus) or \
                not is_evaluation_passed(second_plus):
            outcome = 0.0
            if not is_evaluation_passed(first_plus):
                text = human_evaluation_message(first_plus)
            else:
                text = human_evaluation_message(second_plus)
            if self.job.get_output:
                evaluation['output'] = None

        # Otherwise, advance to checking the solution
        else:

            # Check that the output file was created
            if not second_sandbox.file_exists('output.txt'):
                outcome = 0.0
                text = "Execution didn't produce file output.txt"
                if self.job.get_output:
                    evaluation['output'] = None

            else:
                # If asked so, put the output file into the storage
                if self.job.get_output:
                    evaluation['output'] = second_sandbox.get_file_to_storage(
                        "output.txt",
                        "Output file for testcase %d in job %s" %
                        (test_number, self.job.info))

                # If not asked otherwise, evaluate the output file
                if not self.job.only_execution:
                    # Put the reference solution into the sandbox
                    second_sandbox.create_file_from_storage(
                        "res.txt",
                        self.job.testcases[test_number].output)

                    outcome, text = white_diff_step(
                        second_sandbox, "output.txt", "res.txt")

        # Whatever happened, we conclude.
        evaluation['success'] = success
        evaluation['outcome'] = outcome
        evaluation['text'] = text

        delete_sandbox(first_sandbox)
        delete_sandbox(second_sandbox)

        return success
