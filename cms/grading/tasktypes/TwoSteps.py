#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2016 Petar Veličković <pv273@cam.ac.uk>
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
import os
import tempfile

from cms import config
from cms.grading.Sandbox import wait_without_std
from cms.grading.ParameterTypes import ParameterTypeChoice
from cms.grading.steps import compilation_step, evaluation_step_before_run, \
    evaluation_step_after_run, human_evaluation_message, merge_execution_stats
from cms.grading.languagemanager import LANGUAGES, get_language
from cms.grading.TaskType import TaskType, check_executables_number, \
    check_files_number, check_manager_present, create_sandbox, \
    delete_sandbox, eval_output
from cms.db import Executable


logger = logging.getLogger(__name__)


# Dummy function to mark translatable string.
def N_(message):
    return message


class TwoSteps(TaskType):
    """Task type class for tasks where the user must submit two files
    with a function each; the first function compute some data, that
    get passed to the second function that must recover some data.

    The admins must provide a manager source file (for each language),
    called manager.%l, that get compiled with both two user sources,
    get the input as stdin, and get two parameters: 0 if it is the
    first instance, 1 if it is the second instance, and the name of
    the pipe.

    Admins must provide also header files, named "foo{.h|lib.pas}" for
    the three sources (manager and user provided).

    Parameters are given by a singleton list of strings (for possible
    expansions in the future), which may be 'diff' or 'comparator',
    specifying whether the evaluation is done using white diff or a
    comparator.

    """
    # Codename of the checker, if it is used.
    CHECKER_CODENAME = "checker"
    # Filename of the input and of the contestant's solution.
    INPUT_FILENAME = "input.txt"
    OUTPUT_FILENAME = "output.txt"

    # Constants used in the parameter definition.
    OUTPUT_EVAL_DIFF = "diff"
    OUTPUT_EVAL_CHECKER = "comparator"

    ALLOW_PARTIAL_SUBMISSION = False

    _EVALUATION = ParameterTypeChoice(
        "Output evaluation",
        "output_eval",
        "",
        {OUTPUT_EVAL_DIFF: "Outputs compared with white diff",
         OUTPUT_EVAL_CHECKER: "Outputs are compared by a comparator"})

    ACCEPTED_PARAMETERS = [_EVALUATION]

    @property
    def name(self):
        """See TaskType.name."""
        # TODO add some details if a comparator is used, etc...
        return "Two steps"

    def __init__(self, parameters):
        super(TwoSteps, self).__init__(parameters)
        self.output_eval = self.parameters[0]

    def get_compilation_commands(self, submission_format):
        """See TaskType.get_compilation_commands."""
        res = dict()
        for language in LANGUAGES:
            source_ext = language.source_extension
            header_ext = language.header_extension
            source_filenames = []
            # Manager
            manager_source_filename = "manager%s" % source_ext
            source_filenames.append(manager_source_filename)
            # Manager's header.
            if header_ext is not None:
                manager_header_filename = "manager%s" % header_ext
                source_filenames.append(manager_header_filename)

            for filename in submission_format:
                source_filename = filename.replace(".%l", source_ext)
                source_filenames.append(source_filename)
                # Headers
                if header_ext is not None:
                    header_filename = filename.replace(".%l", header_ext)
                    source_filenames.append(header_filename)

            # Get compilation command and compile.
            executable_filename = "manager"
            commands = language.get_compilation_commands(
                source_filenames, executable_filename)
            res[language.name] = commands
        return res

    def get_user_managers(self):
        """See TaskType.get_user_managers."""
        return ["manager.%l"]

    def get_auto_managers(self):
        """See TaskType.get_auto_managers."""
        return []

    def _uses_checker(self):
        return self.output_eval == TwoSteps.OUTPUT_EVAL_CHECKER

    def compile(self, job, file_cacher):
        """See TaskType.compile."""
        language = get_language(job.language)
        source_ext = language.source_extension
        header_ext = language.header_extension

        if not check_files_number(job, 2):
            return

        files_to_get = {}
        source_filenames = []

        # Manager.
        manager_filename = "manager%s" % source_ext
        if not check_manager_present(job, manager_filename):
            return
        source_filenames.append(manager_filename)
        files_to_get[manager_filename] = \
            job.managers[manager_filename].digest
        # Manager's header.
        if header_ext is not None:
            manager_filename = "manager%s" % header_ext
            if not check_manager_present(job, manager_filename):
                return
            source_filenames.append(manager_filename)
            files_to_get[manager_filename] = \
                job.managers[manager_filename].digest

        # User's submissions and headers.
        for filename, file_ in iteritems(job.files):
            source_filename = filename.replace(".%l", source_ext)
            source_filenames.append(source_filename)
            files_to_get[source_filename] = file_.digest
            # Headers (fixing compile error again here).
            if header_ext is not None:
                header_filename = filename.replace(".%l", header_ext)
                if not check_manager_present(job, header_filename):
                    return
                source_filenames.append(header_filename)
                files_to_get[header_filename] = \
                    job.managers[header_filename].digest

        # Get compilation command.
        executable_filename = "manager"
        commands = language.get_compilation_commands(
            source_filenames, executable_filename)

        # Create the sandbox and put the required files in it.
        sandbox = create_sandbox(file_cacher, name="compile")
        job.sandboxes.append(sandbox.path)

        for filename, digest in iteritems(files_to_get):
            sandbox.create_file_from_storage(filename, digest)

        # Run the compilation.
        box_success, compilation_success, text, stats = \
            compilation_step(sandbox, commands)

        # Retrieve the compiled executables
        job.success = box_success
        job.compilation_success = compilation_success
        job.text = text
        job.plus = stats
        if box_success and compilation_success:
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
        if not check_executables_number(job, 1):
            return

        executable_filename = next(iterkeys(job.executables))
        executable_digest = job.executables[executable_filename].digest

        first_sandbox = create_sandbox(file_cacher, name="first_evaluate")
        second_sandbox = create_sandbox(file_cacher, name="second_evaluate")
        job.sandboxes.append(first_sandbox.path)
        job.sandboxes.append(second_sandbox.path)

        fifo_dir = tempfile.mkdtemp(dir=config.temp_dir)
        fifo = os.path.join(fifo_dir, "fifo")
        os.mkfifo(fifo)
        os.chmod(fifo_dir, 0o755)
        os.chmod(fifo, 0o666)

        # First step: we start the first manager.
        first_command = ["./%s" % executable_filename, "0", fifo]
        first_executables_to_get = {executable_filename: executable_digest}
        first_files_to_get = {
            TwoSteps.INPUT_FILENAME: job.input
            }
        first_allow_path = [fifo_dir]

        # Put the required files into the sandbox
        for filename, digest in iteritems(first_executables_to_get):
            first_sandbox.create_file_from_storage(filename,
                                                   digest,
                                                   executable=True)
        for filename, digest in iteritems(first_files_to_get):
            first_sandbox.create_file_from_storage(filename, digest)

        first = evaluation_step_before_run(
            first_sandbox,
            first_command,
            job.time_limit,
            job.memory_limit,
            first_allow_path,
            stdin_redirect=TwoSteps.INPUT_FILENAME,
            multiprocess=job.multithreaded_sandbox,
            wait=False)

        # Second step: we start the second manager.
        second_command = ["./%s" % executable_filename, "1", fifo]
        second_executables_to_get = {executable_filename: executable_digest}
        second_files_to_get = {}
        second_allow_path = [fifo_dir]

        # Put the required files into the second sandbox
        for filename, digest in iteritems(second_executables_to_get):
            second_sandbox.create_file_from_storage(filename,
                                                    digest,
                                                    executable=True)
        for filename, digest in iteritems(second_files_to_get):
            second_sandbox.create_file_from_storage(filename, digest)

        second = evaluation_step_before_run(
            second_sandbox,
            second_command,
            job.time_limit,
            job.memory_limit,
            second_allow_path,
            stdout_redirect=TwoSteps.OUTPUT_FILENAME,
            multiprocess=job.multithreaded_sandbox,
            wait=False)

        # Consume output.
        wait_without_std([second, first])

        box_success_first, evaluation_success_first, first_stats = \
            evaluation_step_after_run(first_sandbox)
        box_success_second, evaluation_success_second, second_stats = \
            evaluation_step_after_run(second_sandbox)

        box_success = box_success_first and box_success_second
        evaluation_success = \
            evaluation_success_first and evaluation_success_second
        stats = merge_execution_stats(first_stats, second_stats)

        outcome = None
        text = None

        # Error in the sandbox: nothing to do!
        if not box_success:
            pass

        # Contestant's error: the marks won't be good
        elif not evaluation_success:
            outcome = 0.0
            text = human_evaluation_message(stats, job.feedback_level)
            if job.get_output:
                job.user_output = None

        # Otherwise, advance to checking the solution
        else:

            # Check that the output file was created
            if not second_sandbox.file_exists(TwoSteps.OUTPUT_FILENAME):
                outcome = 0.0
                text = [N_("Evaluation didn't produce file %s"),
                        TwoSteps.OUTPUT_FILENAME]
                if job.get_output:
                    job.user_output = None

            else:
                # If asked so, put the output file into the storage
                if job.get_output:
                    job.user_output = second_sandbox.get_file_to_storage(
                        TwoSteps.OUTPUT_FILENAME,
                        "Output file in job %s" % job.info,
                        trunc_len=100 * 1024)

                # If just asked to execute, fill text and set dummy outcome.
                if job.only_execution:
                    outcome = 0.0
                    text = [N_("Execution completed successfully")]

                # Otherwise evaluate the output file.
                else:
                    box_success, outcome, text = eval_output(
                        file_cacher, job,
                        TwoSteps.CHECKER_CODENAME
                        if self._uses_checker() else None,
                        user_output_path=second_sandbox.relative_path(
                            TwoSteps.OUTPUT_FILENAME))

        # Fill in the job with the results.
        job.success = box_success
        job.outcome = str(outcome) if outcome is not None else None
        job.text = text
        job.plus = stats

        delete_sandbox(first_sandbox, job.success)
        delete_sandbox(second_sandbox, job.success)
