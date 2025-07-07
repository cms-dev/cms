#!/usr/bin/env python3

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

import logging

from cms.grading.ParameterTypes import ParameterTypeString
from .Batch import Batch


logger = logging.getLogger(__name__)


# Dummy function to mark translatable string.
def N_(message):
    return message


class BatchAndOutput(Batch):
    """Task type class for a task that is a combination of Batch and
    OutputOnly.

    Parameters needs to be a list of four elements.

    The first element is 'grader' or 'alone': in the first
    case, the source file is to be compiled with a provided piece of
    software ('grader'); in the other by itself.

    The second element is a 2-tuple of the input file name and output file
    name. The input file may be '' to denote stdin, and similarly the
    output filename may be '' to denote stdout.

    The third element is 'diff' or 'comparator' and says whether the
    output is compared with a simple diff algorithm or using a
    comparator.

    The fourth element specifies testcases that *must* be provided as
    output-only. If a testcase is not in this list, and is not provided
    explicitly, then the provided source file will be used to compute
    the output.

    Note: the first element is used only in the compilation step; the
    others only in the evaluation step.

    A comparator can read argv[1], argv[2], argv[3], and argv[4] (respectively,
    input, correct output, user output and 'outputonly' if the testcase was an
    outputonly-only testcase, 'batch' otherwise) and should write the outcome
    to stdout and the text to stderr.

    The submission format for tasks of this task type should contain both
    a single source file and one or more text files named "output_%s.txt",
    where "%s" is the test case index.

    """

    # Template for the filename of the output files provided by the user; %s
    # represent the testcase codename.
    USER_OUTPUT_FILENAME_TEMPLATE = "output_%s.txt"

    # Other constants to specify the task type behaviour and parameters.
    ALLOW_PARTIAL_SUBMISSION = True
    REUSE_PREVIOUS_SUBMISSION = False

    _OUTPUT_ONLY_TESTCASES = ParameterTypeString(
        "Comma-separated list of output only testcases",
        "output_only_testcases",
        "")

    ACCEPTED_PARAMETERS = Batch.ACCEPTED_PARAMETERS + [_OUTPUT_ONLY_TESTCASES]

    @property
    def name(self):
        """See TaskType.name."""
        # TODO add some details if a grader/comparator is used, etc...
        return "BatchAndOutput"

    def __init__(self, parameters):
        super().__init__(parameters)

        # Data in the parameters that is not in Batch.
        self.output_only_testcases: set[str] = set(
            self.parameters[3].split(','))

    @staticmethod
    def _get_user_output_filename(job):
        return BatchAndOutput.USER_OUTPUT_FILENAME_TEMPLATE % \
            job.operation.testcase_codename

    def compile(self, job, file_cacher):
        """See TaskType.compile."""
        num_source_files = 0
        for (codename, _) in job.files.items():
            if codename.endswith(".%l"):
                num_source_files += 1

        if num_source_files == 0:
            # This submission did not have any source files, skip compilation
            job.success = True
            job.compilation_success = True
            job.text = [N_("No compilation needed")]
            job.plus = {}
            return

        self._do_compile(job, file_cacher)

    def evaluate(self, job, file_cacher):
        """See TaskType.evaluate."""

        user_output_filename = self._get_user_output_filename(job)

        output_file_params = None
        sandbox = None
        outcome = None
        text = ""
        stats = {}
        box_success = True

        if user_output_filename in job.files:
            output_file_params = {
                'user_output_digest': job.files[user_output_filename].digest}
        elif job.operation.testcase_codename in self.output_only_testcases:
            pass
        elif job.executables:
            outcome, text, output_file_params, stats, box_success, sandbox = self._execution_step(
                job, file_cacher)

        if output_file_params is None and outcome is None:
            job.success = True
            job.outcome = "0.0"
            job.text = [N_("File not submitted")]
            job.plus = {}
            return

        if job.operation.testcase_codename in self.output_only_testcases:
            extra_args = ['outputonly']
        else:
            extra_args = ['batch']

        self._evaluate_step(job, file_cacher, output_file_params,
                            outcome, text, stats, box_success, sandbox, extra_args)
