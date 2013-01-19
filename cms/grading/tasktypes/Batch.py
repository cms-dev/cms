#!/usr/bin/env python2
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

from cms import logger
from cms.grading import get_compilation_command, compilation_step, \
    evaluation_step, human_evaluation_message, is_evaluation_passed, \
    extract_outcome_and_text, white_diff_step
from cms.grading.ParameterTypes import ParameterTypeCollection, \
     ParameterTypeChoice, ParameterTypeString
from cms.grading.TaskType import TaskType, \
     create_sandbox, delete_sandbox
from cms.db.SQLAlchemyAll import Submission, Executable


class Batch(TaskType):
    """Task type class for a unique standalone submission source, with
    comparator (or not).

    Parameters needs to be a list of three elements.

    The first element is 'grader' or 'alone': in the first
    case, the source file is to be compiled with a provided piece of
    software ('grader'); in the other by itself.

    The second element is a 2-tuple of the input file name and output file
    name. The input file may be '' to denote stdin, and similarly the
    output filename may be '' to denote stdout.

    The third element is 'diff' or 'comparator' and says whether the
    output is compared with a simple diff algorithm or using a
    comparator.

    Note: the first element is used only in the compilation step; the
    others only in the evaluation step.

    A comparator can read argv[1], argv[2], argv[3] (respectively,
    input, correct output and user output) and should write the
    outcome to stdout and the text to stderr.

    """
    ALLOW_PARTIAL_SUBMISSION = False

    _COMPILATION = ParameterTypeChoice(
        "Compilation",
        "compilation",
        "",
        {"alone": "Submissions are self-sufficient",
         "grader": "Submissions are compiled with a grader"})

    _USE_FILE = ParameterTypeCollection(
        "I/O (blank for stdin/stdout)",
        "io",
        "",
        [
            ParameterTypeString("Input file", "inputfile", ""),
            ParameterTypeString("Output file", "outputfile", ""),
        ])

    _EVALUATION = ParameterTypeChoice(
        "Output evaluation",
        "output_eval",
        "",
        {"diff": "Outputs compared with white diff",
         "comparator": "Outputs are compared by a comparator"})

    ACCEPTED_PARAMETERS = [_COMPILATION, _USE_FILE, _EVALUATION]

    @property
    def name(self):
        """See TaskType.name."""
        # TODO add some details if a grader/comparator is used, etc...
        return "Batch"

    def get_compilation_commands(self, submission_format):
        """See TaskType.get_compilation_commands."""
        res = dict()
        for language in Submission.LANGUAGES:
            format_filename = submission_format[0]
            source_filenames = []
            # If a grader is specified, we add to the command line (and to
            # the files to get) the corresponding manager.
            if self.job.task_type_parameters[0] == "grader":
                source_filenames.append("grader.%s" % language)
            source_filenames.append(format_filename.replace("%l", language))
            executable_filename = format_filename.replace(".%l", "")
            command = " ".join(get_compilation_command(language,
                                                       source_filenames,
                                                       executable_filename))
            res[language] = [command]
        return res

    def get_user_managers(self, submission_format):
        """See TaskType.get_user_managers."""
        return []

    def get_auto_managers(self):
        """See TaskType.get_auto_managers."""
        return None

    def compile(self):
        """See TaskType.compile."""
        # Detect the submission's language. The checks about the
        # formal correctedness of the submission are done in CWS,
        # before accepting it.
        language = self.job.language

        # TODO: here we are sure that submission.files are the same as
        # task.submission_format. The following check shouldn't be
        # here, but in the definition of the task, since this actually
        # checks that task's task type and submission format agree.
        if len(self.job.files) != 1:
            self.job.success = True
            self.job.compilation_success = False
            self.job.text = "Invalid files in submission"
            logger.error("Submission contains %d files, expecting 1" %
                         len(self.job.files))
            return True

        # Create the sandbox
        sandbox = create_sandbox(self)
        self.job.sandboxes.append(sandbox.path)

        # Prepare the source files in the sandbox
        files_to_get = {}
        format_filename = self.job.files.keys()[0]
        source_filenames = []
        source_filenames.append(format_filename.replace("%l", language))
        files_to_get[source_filenames[0]] = \
            self.job.files[format_filename].digest
        # If a grader is specified, we add to the command line (and to
        # the files to get) the corresponding manager. The grader must
        # be the first file in source_filenames.
        if self.job.task_type_parameters[0] == "grader":
            source_filenames.insert(0, "grader.%s" % language)
            files_to_get["grader.%s" % language] = \
                self.job.managers["grader.%s" % language].digest

        # Also copy all *.h and *lib.pas graders
        for filename in self.job.managers.iterkeys():
            if filename.endswith('.h') or \
                    filename.endswith('lib.pas'):
                files_to_get[filename] = \
                    self.job.managers[filename].digest

        for filename, digest in files_to_get.iteritems():
            sandbox.create_file_from_storage(filename, digest)

        # Prepare the compilation command
        executable_filename = format_filename.replace(".%l", "")
        command = get_compilation_command(language,
                                          source_filenames,
                                          executable_filename)

        # Run the compilation
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
        # Create the sandbox
        sandbox = create_sandbox(self)

        # Prepare the execution
        executable_filename = self.job.executables.keys()[0]
        command = [os.path.join(".", executable_filename)]
        executables_to_get = {
            executable_filename:
            self.job.executables[executable_filename].digest
            }
        input_filename, output_filename = self.job.task_type_parameters[1]
        stdin_redirect = None
        stdout_redirect = None
        if input_filename == "":
            input_filename = "input.txt"
            stdin_redirect = input_filename
        if output_filename == "":
            output_filename = "output.txt"
            stdout_redirect = output_filename
        files_to_get = {
            input_filename: self.job.testcases[test_number].input
            }

        # Put the required files into the sandbox
        for filename, digest in executables_to_get.iteritems():
            sandbox.create_file_from_storage(filename, digest, executable=True)
        for filename, digest in files_to_get.iteritems():
            sandbox.create_file_from_storage(filename, digest)

        # Actually performs the execution
        success, plus = evaluation_step(
            sandbox,
            command,
            self.job.time_limit,
            self.job.memory_limit,
            stdin_redirect=stdin_redirect,
            stdout_redirect=stdout_redirect)

        self.job.evaluations[test_number] = {'sandboxes': [sandbox.path],
                                             'plus': plus}
        outcome = None
        text = None
        evaluation = self.job.evaluations[test_number]

        # Error in the sandbox: nothing to do!
        if not success:
            pass

        # Contestant's error: the marks won't be good
        elif not is_evaluation_passed(plus):
            outcome = 0.0
            text = human_evaluation_message(plus)
            if self.job.get_output:
                evaluation['output'] = None

        # Otherwise, advance to checking the solution
        else:

            # Check that the output file was created
            if not sandbox.file_exists(output_filename):
                outcome = 0.0
                text = "Execution didn't produce file %s" % \
                    (output_filename)
                if self.job.get_output:
                    evaluation['output'] = None

            else:
                # If asked so, put the output file into the storage
                if self.job.get_output:
                    evaluation['output'] = sandbox.get_file_to_storage(
                        output_filename,
                        "Output file for testcase %d in job %s" %
                        (test_number, self.job.info),
                        trunc_len=100 * 1024)

                # If not asked otherwise, evaluate the output file
                if not self.job.only_execution:

                    # Put the reference solution into the sandbox
                    sandbox.create_file_from_storage(
                        "res.txt",
                        self.job.testcases[test_number].output)

                    # Check the solution with white_diff
                    if self.job.task_type_parameters[2] == "diff":
                        outcome, text = white_diff_step(
                            sandbox, output_filename, "res.txt")

                    # Check the solution with a comparator
                    elif self.job.task_type_parameters[2] == "comparator":
                        manager_filename = "checker"

                        if not manager_filename in self.job.managers:
                            logger.error("Configuration error: missing or "
                                         "invalid comparator (it must be "
                                         "named 'checker')")
                            success = False

                        else:
                            sandbox.create_file_from_storage(
                                manager_filename,
                                self.job.managers[manager_filename].digest,
                                executable=True)
                            success, _ = evaluation_step(
                                sandbox,
                                ["./%s" % manager_filename,
                                 input_filename, "res.txt", output_filename])
                        if success:
                            try:
                                outcome, text = \
                                    extract_outcome_and_text(sandbox)
                            except ValueError, e:
                                logger.error("Invalid output from "
                                             "comparator: %s" % (e.message,))
                                success = False

                    else:
                        raise ValueError("Unrecognized third parameter"
                                         " `%s' for Batch tasktype." %
                                         self.job.task_type_parameters[2])

        # Whatever happened, we conclude.
        evaluation['success'] = success
        evaluation['outcome'] = str(outcome) if outcome is not None else None
        evaluation['text'] = text
        delete_sandbox(sandbox)
        return success
