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

"""Task type for output only tasks.

"""

from cms.grading.TaskType import TaskType, \
     create_sandbox, delete_sandbox
from cms.grading.ParameterTypes import ParameterTypeChoice


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

    def compile(self):
        """See TaskType.compile."""
        # No compilation needed.
        return self.finish_compilation(True, True, "No compilation needed.")

    def evaluate_testcase(self, test_number):
        """See TaskType.evaluate_testcase."""
        sandbox = create_sandbox(self)

        # Since we allow partial submission, if the file is not
        # present we report that the outcome is 0.
        if "output_%03d.txt" % test_number not in self.submission.files:
            return self.finish_evaluation_testcase(
                test_number,
                True, 0.0, "File not submitted.")
        # First and only one step: diffing (manual or with manager).
        output_digest = self.submission.files["output_%03d.txt" %
                                              test_number].digest

        # TODO: this should check self.parameters, not managers.
        if len(self.submission.task.managers) == 0:
            # No manager: I'll do a white_diff between the submission
            # file and the correct output res.txt.
            success, outcome, text = self.white_diff_step(
                sandbox,
                "output.txt", "res.txt",
                {"res.txt":
                 self.submission.task.testcases[test_number].output,
                 "output.txt": output_digest})
        else:
            # Manager present: wonderful, he'll do all the job.
            manager_filename = self.submission.task.managers.keys()[0]
            success, outcome, text = self.evaluation_step(
                sandbox,
                ["./%s" % manager_filename,
                 "input.txt", "res.txt", "output.txt"],
                {manager_filename:
                 self.submission.task.managers[manager_filename].digest},
                {"output.txt": output_digest,
                 "res.txt": self.submission.task.testcases[test_number].output,
                 "input.txt":
                 self.submission.task.testcases[test_number].input},
                allow_path=["input.txt", "output.txt", "res.txt"],
                final=True)

        # Whatever happened, we conclude.
        delete_sandbox(sandbox)
        return self.finish_evaluation_testcase(test_number,
                                               success, outcome, text)
