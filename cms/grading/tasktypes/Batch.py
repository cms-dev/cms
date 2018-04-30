#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2015 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2017 Myungwoo Chun <mc.tamaki@gmail.com>
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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa
from six import iterkeys, iteritems

import logging

from cms.grading.steps import compilation_step, \
    evaluation_step, human_evaluation_message, is_evaluation_passed
from cms.grading.languagemanager import LANGUAGES, get_language
from cms.grading.ParameterTypes import ParameterTypeCollection, \
    ParameterTypeChoice, ParameterTypeString
from cms.grading.TaskType import TaskType, \
    create_sandbox, delete_sandbox, is_manager_for_compilation, eval_output
from cms.db import Executable


logger = logging.getLogger(__name__)


# Dummy function to mark translatable string.
def N_(message):
    return message


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
    # Codename of the checker, if it is used.
    CHECKER_CODENAME = "checker"
    # Basename of the grader, used in the manager filename and as the main
    # class in languages that require us to specify it.
    GRADER_BASENAME = "grader"
    # Default input and output filenames when not provided as parameters.
    DEFAULT_INPUT_FILENAME = "input.txt"
    DEFAULT_OUTPUT_FILENAME = "output.txt"

    # Constants used in the parameter definition.
    OUTPUT_EVAL_DIFF = "diff"
    OUTPUT_EVAL_CHECKER = "comparator"
    COMPILATION_ALONE = "alone"
    COMPILATION_GRADER = "grader"

    # Other constants to specify the task type behaviour and parameters.
    ALLOW_PARTIAL_SUBMISSION = False

    _COMPILATION = ParameterTypeChoice(
        "Compilation",
        "compilation",
        "",
        {COMPILATION_ALONE: "Submissions are self-sufficient",
         COMPILATION_GRADER: "Submissions are compiled with a grader"})

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
        {OUTPUT_EVAL_DIFF: "Outputs compared with white diff",
         OUTPUT_EVAL_CHECKER: "Outputs are compared by a comparator"})

    ACCEPTED_PARAMETERS = [_COMPILATION, _USE_FILE, _EVALUATION]

    @property
    def name(self):
        """See TaskType.name."""
        # TODO add some details if a grader/comparator is used, etc...
        return "Batch"

    def __init__(self, parameters):
        super(Batch, self).__init__(parameters)

        # Data in the parameters.
        self.compilation = self.parameters[0]
        self.input_filename, self.output_filename = self.parameters[1]
        self.output_eval = self.parameters[2]

        # Actual input and output are the files used to store input and
        # where the output is checked, regardless of using redirects or not.
        self._actual_input = self.input_filename
        self._actual_output = self.output_filename
        if len(self.input_filename) == 0:
            self._actual_input = Batch.DEFAULT_INPUT_FILENAME
        if len(self.output_filename) == 0:
            self._actual_output = Batch.DEFAULT_OUTPUT_FILENAME

    def get_compilation_commands(self, submission_format):
        """See TaskType.get_compilation_commands."""
        source_filenames = []
        # If a grader is specified, we add to the command line (and to
        # the files to get) the corresponding manager.
        if self._uses_grader():
            source_filenames.append(Batch.GRADER_BASENAME + ".%l")
        source_filenames.append(submission_format[0])
        executable_filename = submission_format[0].replace(".%l", "")
        res = dict()
        for language in LANGUAGES:
            res[language.name] = language.get_compilation_commands(
                [source.replace(".%l", language.source_extension)
                 for source in source_filenames],
                executable_filename)
        return res

    def get_user_managers(self):
        """See TaskType.get_user_managers."""
        return []

    def get_auto_managers(self):
        """See TaskType.get_auto_managers."""
        return []

    def _uses_grader(self):
        return self.compilation == Batch.COMPILATION_GRADER

    def _uses_checker(self):
        return self.output_eval == Batch.OUTPUT_EVAL_CHECKER

    def compile(self, job, file_cacher):
        """See TaskType.compile."""
        # Detect the submission's language. The checks about the
        # formal correctedness of the submission are done in CWS,
        # before accepting it.
        language = get_language(job.language)
        source_ext = language.source_extension

        # TODO: here we are sure that submission.files are the same as
        # task.submission_format. The following check shouldn't be
        # here, but in the definition of the task, since this actually
        # checks that task's task type and submission format agree.
        if len(job.files) != 1:
            job.success = True
            job.compilation_success = False
            job.text = [N_("Invalid files in submission")]
            logger.error("Submission contains %d files, expecting 1",
                         len(job.files), extra={"operation": job.info})
            return

        # Create the sandbox.
        sandbox = create_sandbox(file_cacher, name="compile")
        job.sandboxes.append(sandbox.path)

        user_file_format = next(iterkeys(job.files))
        user_source_filename = user_file_format.replace(".%l", source_ext)
        executable_filename = user_file_format.replace(".%l", "")

        # Copy required files in the sandbox (includes the grader if present).
        sandbox.create_file_from_storage(
            user_source_filename, job.files[user_file_format].digest)
        for filename in iterkeys(job.managers):
            if is_manager_for_compilation(filename, language):
                sandbox.create_file_from_storage(
                    filename, job.managers[filename].digest)

        # Create the list of filenames to be passed to the compiler. If we use
        # a grader, it needs to be in first position in the command line.
        source_filenames = [user_source_filename]
        if self._uses_grader():
            grader_source_filename = Batch.GRADER_BASENAME + source_ext
            source_filenames.insert(0, grader_source_filename)

        # Prepare the compilation command.
        commands = language.get_compilation_commands(
            source_filenames, executable_filename)

        # Run the compilation
        operation_success, compilation_success, text, plus = \
            compilation_step(sandbox, commands)

        # Retrieve the compiled executables
        job.success = operation_success
        job.compilation_success = compilation_success
        job.plus = plus
        job.text = text
        if operation_success and compilation_success:
            digest = sandbox.get_file_to_storage(
                executable_filename,
                "Executable %s for %s" %
                (executable_filename, job.info))
            job.executables[executable_filename] = \
                Executable(executable_filename, digest)

        # Cleanup
        delete_sandbox(sandbox, job.success)

    def evaluate(self, job, file_cacher):
        """See TaskType.evaluate."""
        if len(job.executables) != 1:
            raise ValueError("Unexpected number of executables (%s)" %
                             len(job.executables))

        # Create the sandbox
        sandbox = create_sandbox(file_cacher, name="evaluate")
        job.sandboxes.append(sandbox.path)

        # Prepare the execution
        executable_filename = next(iterkeys(job.executables))
        language = get_language(job.language)
        main = Batch.GRADER_BASENAME \
            if self._uses_grader() else executable_filename
        commands = language.get_evaluation_commands(
            executable_filename, main=main)
        executables_to_get = {
            executable_filename:
                job.executables[executable_filename].digest
        }
        files_to_get = {
            self._actual_input: job.input
        }

        # Check which redirect we need to perform, and in case we don't
        # manage the output via redirect, the submission needs to be able
        # to write on it.
        files_allowing_write = []
        stdin_redirect = None
        stdout_redirect = None
        if len(self.input_filename) == 0:
            stdin_redirect = self._actual_input
        if len(self.output_filename) == 0:
            stdout_redirect = self._actual_output
        else:
            files_allowing_write.append(self._actual_output)

        # Put the required files into the sandbox
        for filename, digest in iteritems(executables_to_get):
            sandbox.create_file_from_storage(filename, digest, executable=True)
        for filename, digest in iteritems(files_to_get):
            sandbox.create_file_from_storage(filename, digest)

        # Actually performs the execution
        success, plus = evaluation_step(
            sandbox,
            commands,
            job.time_limit,
            job.memory_limit,
            writable_files=files_allowing_write,
            stdin_redirect=stdin_redirect,
            stdout_redirect=stdout_redirect,
            multiprocess=job.multithreaded_sandbox)

        job.plus = plus

        outcome = None
        text = []

        # Error in the sandbox: nothing to do!
        if not success:
            pass

        # Contestant's error: the marks won't be good
        elif not is_evaluation_passed(plus):
            outcome = 0.0
            text = human_evaluation_message(plus)
            if job.get_output:
                job.user_output = None

        # Otherwise, advance to checking the solution
        else:

            # Check that the output file was created
            if not sandbox.file_exists(self._actual_output):
                outcome = 0.0
                text = [N_("Evaluation didn't produce file %s"),
                        self._actual_output]
                if job.get_output:
                    job.user_output = None

            else:
                # If asked so, put the output file into the storage.
                if job.get_output:
                    job.user_output = sandbox.get_file_to_storage(
                        self._actual_output,
                        "Output file in job %s" % job.info,
                        trunc_len=100 * 1024)

                # If just asked to execute, fill text and set dummy outcome.
                if job.only_execution:
                    outcome = 0.0
                    text = [N_("Execution completed successfully")]

                # Otherwise evaluate the output file.
                else:
                    checker_success, outcome, text = eval_output(
                        file_cacher, job,
                        Batch.CHECKER_CODENAME
                        if self._uses_checker() else None,
                        user_output_path=sandbox.relative_path(
                            self._actual_output),
                        user_output_filename=self.output_filename)
                    success = success and checker_success

        # Whatever happened, we conclude.
        job.success = success
        job.outcome = str(outcome) if outcome is not None else None
        job.text = text

        delete_sandbox(sandbox, job.success)
