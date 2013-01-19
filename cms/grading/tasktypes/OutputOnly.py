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

"""Task type for output only tasks.

"""

from cms import logger
from cms.grading.TaskType import TaskType, \
     create_sandbox, delete_sandbox
from cms.grading.ParameterTypes import ParameterTypeChoice
from cms.grading import white_diff_step, evaluation_step, \
    extract_outcome_and_text


class OutputOnly(TaskType):
    """Task type class for output only tasks, with submission composed
    of testcase_number text files, to be evaluated diffing or using a
    comparator.

    Parameters are a list of string with one element (for future
    possible expansions), which maybe 'diff' or 'comparator', meaning that
    the evaluation is done via white diff or via a comparator.

    """
    ALLOW_PARTIAL_SUBMISSION = True

    _EVALUATION = ParameterTypeChoice(
        "Output evaluation",
        "output_eval",
        "",
        {"diff": "Outputs compared with white diff",
         "comparator": "Outputs are compared by a comparator"})

    ACCEPTED_PARAMETERS = [_EVALUATION]

    @property
    def name(self):
        """See TaskType.name."""
        # TODO add some details if a comparator is used, etc...
        return "Output only"

    testable = False

    def get_compilation_commands(self, submission_format):
        """See TaskType.get_compilation_commands."""
        return None

    def get_user_managers(self, submission_format):
        """See TaskType.get_user_managers."""
        return []

    def get_auto_managers(self):
        """See TaskType.get_auto_managers."""
        return []

    def compile(self):
        """See TaskType.compile."""
        # No compilation needed.
        self.job.success = True
        self.job.compilation_success = True
        self.job.text = "No compilation needed."

    def evaluate_testcase(self, test_number):
        """See TaskType.evaluate_testcase."""
        sandbox = create_sandbox(self)
        self.job.sandboxes.append(sandbox.path)

        # Immediately prepare the skeleton to return
        self.job.evaluations[test_number] = {'sandboxes': [sandbox.path],
                                             'plus': {}}
        evaluation = self.job.evaluations[test_number]
        outcome = None
        text = None

        # Since we allow partial submission, if the file is not
        # present we report that the outcome is 0.
        if "output_%03d.txt" % test_number not in self.job.files:
            evaluation['success'] = True
            evaluation['outcome'] = 0.0
            evaluation['text'] = "File not submitted."
            return True

        # First and only one step: diffing (manual or with manager).
        output_digest = self.job.files["output_%03d.txt" %
                                       test_number].digest

        # Put the files into the sandbox
        sandbox.create_file_from_storage(
            "res.txt",
            self.job.testcases[test_number].output)
        sandbox.create_file_from_storage(
            "output.txt",
            output_digest)

        if self.job.task_type_parameters[0] == "diff":
            # No manager: I'll do a white_diff between the submission
            # file and the correct output res.txt.
            success = True
            outcome, text = white_diff_step(
                sandbox, "output.txt", "res.txt")

        elif self.job.task_type_parameters[0] == "comparator":
            # Manager present: wonderful, he'll do all the job.
            manager_filename = "checker"
            if not manager_filename in self.job.managers:
                logger.error("Configuration error: missing or "
                             "invalid comparator (it must be "
                             "named `checker')")
                success = False
            else:
                sandbox.create_file_from_storage(
                    manager_filename,
                    self.job.managers[manager_filename].digest,
                    executable=True)
                input_digest = self.job.testcases[test_number].input
                sandbox.create_file_from_storage(
                    "input.txt",
                    input_digest)
                success, _ = evaluation_step(
                    sandbox,
                    ["./%s" % manager_filename,
                     "input.txt", "res.txt", "output.txt"])
                if success:
                    outcome, text = extract_outcome_and_text(sandbox)

        else:
            raise ValueError("Unrecognized first parameter "
                             "`%s' for OutputOnly tasktype. "
                             "Should be `diff' or `comparator'." %
                             self.job.task_type_parameters[0])

        # Whatever happened, we conclude.
        evaluation['success'] = success
        evaluation['outcome'] = str(outcome) if outcome is not None else None
        evaluation['text'] = text
        delete_sandbox(sandbox)
        return success
