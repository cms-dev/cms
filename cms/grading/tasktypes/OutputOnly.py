#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""Task type for output only tasks.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *
from future.builtins import *

import logging

from cms.grading.TaskType import TaskType, \
    create_sandbox, delete_sandbox
from cms.grading.ParameterTypes import ParameterTypeChoice
from cms.grading import white_diff_step, evaluation_step, \
    extract_outcome_and_text


logger = logging.getLogger(__name__)


# Dummy function to mark translatable string.
def N_(message):
    return message


class OutputOnly(TaskType):
    """Task type class for output only tasks, with submission composed
    of testcase_number text files, to be evaluated diffing or using a
    comparator.

    Parameters are a list of string with one element (for future
    possible expansions), which maybe 'diff' or 'comparator', meaning that
    the evaluation is done via white diff or via a comparator.

    """
    # Filename of the reference solution in the sandbox evaluating the output.
    CORRECT_OUTPUT_FILENAME = "res.txt"
    # Filename of the admin-provided comparator.
    CHECKER_FILENAME = "checker"
    # Name of input and user output files.
    INPUT_FILENAME = "input.txt"
    OUTPUT_FILENAME = "output.txt"
    # Template for the filename of the output files provided by the user; %s
    # represent the testcase codename.
    USER_OUTPUT_FILENAME_TEMPLATE = "output_%s.txt"

    # Constants used in the parameter definition.
    OUTPUT_EVAL_DIFF = "diff"
    OUTPUT_EVAL_CHECKER = "comparator"

    # Other constants to specify the task type behaviour and parameters.
    ALLOW_PARTIAL_SUBMISSION = True

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
        return "Output only"

    testable = False

    def __init__(self, parameters):
        super(OutputOnly, self).__init__(parameters)
        self.output_eval = self.parameters[0]

    def get_compilation_commands(self, unused_submission_format):
        """See TaskType.get_compilation_commands."""
        return None

    def get_user_managers(self, unused_submission_format):
        """See TaskType.get_user_managers."""
        return []

    def get_auto_managers(self):
        """See TaskType.get_auto_managers."""
        return []

    def _uses_checker(self):
        return self.output_eval == OutputOnly.OUTPUT_EVAL_CHECKER

    @staticmethod
    def _get_user_output_filename(job):
        return OutputOnly.USER_OUTPUT_FILENAME_TEMPLATE % \
            job.operation["testcase_codename"]

    def compile(self, job, file_cacher):
        """See TaskType.compile."""
        # No compilation needed.
        job.success = True
        job.compilation_success = True
        job.text = [N_("No compilation needed")]
        job.plus = {}

    def evaluate(self, job, file_cacher):
        """See TaskType.evaluate."""
        sandbox = create_sandbox(
            file_cacher,
            multithreaded=job.multithreaded_sandbox,
            name="evaluate")
        job.sandboxes.append(sandbox.path)

        # Immediately prepare the skeleton to return
        job.sandboxes = [sandbox.path]
        job.plus = {}

        outcome = None
        text = []

        user_output_filename = self._get_user_output_filename(job)

        # Since we allow partial submission, if the file is not
        # present we report that the outcome is 0.
        if user_output_filename not in job.files:
            job.success = True
            job.outcome = "0.0"
            job.text = [N_("File not submitted")]
            return

        # First and only one step: diffing (manual or with manager).

        # Put user output and reference solution into the sandbox.
        sandbox.create_file_from_storage(
            OutputOnly.OUTPUT_FILENAME, job.files[user_output_filename].digest)
        sandbox.create_file_from_storage(
            OutputOnly.CORRECT_OUTPUT_FILENAME, job.output)

        if self._uses_checker():
            # Checker also requires the input file.
            sandbox.create_file_from_storage(
                OutputOnly.INPUT_FILENAME, job.input)
            success, outcome, text = OutputOnly._run_checker(sandbox, job)
        else:
            success = True
            outcome, text = white_diff_step(
                sandbox,
                OutputOnly.OUTPUT_FILENAME,
                OutputOnly.CORRECT_OUTPUT_FILENAME)

        # Whatever happened, we conclude.
        job.success = success
        job.outcome = "%s" % outcome if outcome is not None else None
        job.text = text

        delete_sandbox(sandbox, job.success)

    @staticmethod
    def _run_checker(sandbox, job):
        """Run the explicit checker given by the admins

        sandbox (Sandbox): the sandbox to run the checker in; should already
            contain input, correct output, and user output.
        job (Job): the job triggering this checker run.

        return (bool, float|None, [str]): success (true if the checker was able
            to check the solution successfully), outcome and text.

        """
        # Copy the checker in the sandbox, after making sure it was provided.
        if OutputOnly.CHECKER_FILENAME not in job.managers:
            logger.error("Configuration error: missing or invalid comparator "
                         "(it must be named `%s')",
                         OutputOnly.CHECKER_FILENAME,
                         extra={"operation": job.info})
            return False, None, []
        sandbox.create_file_from_storage(
            OutputOnly.CHECKER_FILENAME,
            job.managers[OutputOnly.CHECKER_FILENAME].digest,
            executable=True)

        command = [
            "./%s" % OutputOnly.CHECKER_FILENAME,
            OutputOnly.INPUT_FILENAME,
            OutputOnly.CORRECT_OUTPUT_FILENAME,
            OutputOnly.OUTPUT_FILENAME]
        success, _ = evaluation_step(sandbox, [command])
        if not success:
            return False, None, []

        try:
            outcome, text = extract_outcome_and_text(sandbox)
        except ValueError as e:
            logger.error("Invalid output from comparator: %s", e,
                         extra={"operation": job.info})
            return False, None, []

        return True, outcome, text
