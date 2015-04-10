#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Task type for Codebreaker tasks, which are very similar to output only tasks.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

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


class Codebreaker(TaskType):
    """Task type class for codebreaker tasks, with submission composed
    of exactly two text files, to be evaluated using a comparator. This
    comparator must validate the student input file for task sanity, then run
    the `correct` program on the student input file and make sure the output is
    the same as the student output file, and finally run the `incorrect` program
    on the student input file and make sure it differs from the student output
    file.

    There are no Parameters provided to this class.

    """
    ALLOW_PARTIAL_SUBMISSION = False

    ACCEPTED_PARAMETERS = []

    @property
    def name(self):
        """See TaskType.name."""
        return "Codebreaker"

    testable = False

    def get_compilation_commands(self, unused_submission_format):
        """See TaskType.get_compilation_commands."""
        return None

    def get_user_managers(self, unused_submission_format):
        """See TaskType.get_user_managers."""
        return []

    def get_auto_managers(self):
        """See TaskType.get_auto_managers."""
        return []

    def compile(self, job, file_cacher):
        """See TaskType.compile."""
        # No compilation needed.
        job.success = True
        job.compilation_success = True
        job.text = [N_("No compilation needed")]
        job.plus = {}

    def evaluate(self, job, file_cacher):
        """See TaskType.evaluate."""
        sandbox = create_sandbox(file_cacher)
        job.sandboxes.append(sandbox.path)

        # Immediately prepare the skeleton to return
        job.sandboxes = [sandbox.path]
        job.plus = {}

        outcome = None
        text = None

        # TODO (bgbn) what the hell does this even do.
        # Since we allow partial submission, if the file is not
        # present we report that the outcome is 0.
        if "output_%s.txt" % job._key not in job.files:
            job.success = True
            job.outcome = "0.0"
            job.text = [N_("File not submitted")]
            return True

        # First and only one step: diffing (manual or with manager).
        output_digest = job.files["output_%s.txt" %
                                  job._key].digest

        # Put the files into the sandbox
        # TODO (bgbn): We don't need res.txt. We need input.txt and output.txt.
        # Need to work out where these files come from.
        sandbox.create_file_from_storage(
            "output.txt",
            output_digest)
        input_digest = job.input
        sandbox.create_file_from_storage(
            "input.txt",
            input_digest)


        # TODO (bgbn): checker has a very well-defined static function. We
        # should have a way to not have to upload it for every task (maybe we
        # can have a python script embedded in this file that's copied into the
        # sandbox)
        manager_filename = "checker"
        sanity_filename = "sanity"
        correct_filename = "correct"
        incorrect_filename = "incorrect"
        if manager_filename not in job.managers:
            logger.error("Configuration error: missing or "
                            "invalid comparator (it must be "
                            "named `checker')", extra={"operation": job.info})
            success = False
        elif sanity_filename not in job.managers:
            logger.error("Configuration error: missing or "
                            "invalid sanity binary (it must be "
                            "named `sanity')", extra={"operation": job.info})
            success = False
        elif correct_filename not in job.managers:
            logger.error("Configuration error: missing or "
                            "invalid correct binary (it must be "
                            "named `correct')", extra={"operation": job.info})
            success = False
        elif incorrect_filename not in job.managers:
            logger.error("Configuration error: missing or "
                            "invalid incorrect binary (it must be "
                            "named `correct')", extra={"operation": job.info})
            success = False
        else:
            sandbox.create_file_from_storage(
                manager_filename,
                job.managers[manager_filename].digest,
                executable=True)
            sandbox.create_file_from_storage(
                sanity_filename,
                job.managers[sanity_filename].digest,
                executable=True)
            sandbox.create_file_from_storage(
                correct_filename,
                job.managers[correct_filename].digest,
                executable=True)
            sandbox.create_file_from_storage(
                incorrect_filename,
                job.managers[incorrect_filename].digest,
                executable=True)
            success, _ = evaluation_step(
                sandbox,
                [["./%s" % manager_filename,
                    "input.txt", "output.txt",
                    "%s" % sanity_filename,
                    "%s" % correct_filename,
                    "%s" % incorrect_filename]])
            if success:
                outcome, text = extract_outcome_and_text(sandbox)

        # Whatever happened, we conclude.
        job.success = success
        job.outcome = "%s" % outcome if outcome is not None else None
        job.text = text

        delete_sandbox(sandbox)
