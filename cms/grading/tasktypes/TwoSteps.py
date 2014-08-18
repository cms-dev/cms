#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2014 Stefano Maggiolo <s.maggiolo@gmail.com>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import tempfile

from cms import LANGUAGES, LANGUAGE_TO_SOURCE_EXT_MAP, \
    LANGUAGE_TO_HEADER_EXT_MAP, config
from cms.grading.Sandbox import wait_without_std
from cms.grading import get_compilation_commands, compilation_step, \
    evaluation_step_before_run, evaluation_step_after_run, \
    is_evaluation_passed, human_evaluation_message, white_diff_step
from cms.grading.TaskType import TaskType, \
    create_sandbox, delete_sandbox
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

    """
    ALLOW_PARTIAL_SUBMISSION = False

    name = "Two steps"

    def get_compilation_commands(self, submission_format):
        """See TaskType.get_compilation_commands."""
        res = dict()
        for language in LANGUAGES:
            source_ext = LANGUAGE_TO_SOURCE_EXT_MAP[language]
            header_ext = LANGUAGE_TO_HEADER_EXT_MAP[language]
            source_filenames = []
            for filename in submission_format:
                source_filename = filename.replace(".%l", source_ext)
                source_filenames.append(source_filename)
                # Headers.
                header_filename = filename.replace(".%l", header_ext)
                source_filenames.append(header_filename)

            # Manager.
            manager_source_filename = "manager%s" % source_ext
            source_filenames.append(manager_source_filename)
            # Manager's header.
            manager_header_filename = "manager%s" % header_ext
            source_filenames.append(manager_header_filename)

            # Get compilation command and compile.
            executable_filename = "manager"
            commands = get_compilation_commands(language,
                                                source_filenames,
                                                executable_filename)
            res[language] = commands
        return res

    def compile(self, job, file_cacher):
        """See TaskType.compile."""
        # Detect the submission's language. The checks about the
        # formal correctedness of the submission are done in CWS,
        # before accepting it.
        language = job.language
        source_ext = LANGUAGE_TO_SOURCE_EXT_MAP[language]
        header_ext = LANGUAGE_TO_HEADER_EXT_MAP[language]

        # TODO: here we are sure that submission.files are the same as
        # task.submission_format. The following check shouldn't be
        # here, but in the definition of the task, since this actually
        # checks that task's task type and submission format agree.
        if len(job.files) != 2:
            job.success = True
            job.compilation_success = False
            job.text = [N_("Invalid files in submission")]
            logger.error("Submission contains %d files, expecting 2",
                         len(job.files), extra={"operation": job.info})
            return True

        # First and only one compilation.
        sandbox = create_sandbox(file_cacher)
        job.sandboxes.append(sandbox.path)
        files_to_get = {}

        # User's submissions and headers.
        source_filenames = []
        for filename, file_ in job.files.iteritems():
            source_filename = filename.replace(".%l", source_ext)
            source_filenames.append(source_filename)
            files_to_get[source_filename] = file_.digest
            # Headers.
            header_filename = filename.replace(".%l", header_ext)
            source_filenames.append(header_filename)
            files_to_get[header_filename] = \
                job.managers[header_filename].digest

        # Manager.
        manager_filename = "manager%s" % source_ext
        source_filenames.append(manager_filename)
        files_to_get[manager_filename] = \
            job.managers[manager_filename].digest
        # Manager's header.
        manager_filename = "manager%s" % header_ext
        source_filenames.append(manager_filename)
        files_to_get[manager_filename] = \
            job.managers[manager_filename].digest

        for filename, digest in files_to_get.iteritems():
            sandbox.create_file_from_storage(filename, digest)

        # Get compilation command and compile.
        executable_filename = "manager"
        commands = get_compilation_commands(language,
                                            source_filenames,
                                            executable_filename)
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
        delete_sandbox(sandbox)

    def evaluate(self, job, file_cacher):
        """See TaskType.evaluate."""
        # f stand for first, s for second.
        first_sandbox = create_sandbox(file_cacher)
        second_sandbox = create_sandbox(file_cacher)
        fifo_dir = tempfile.mkdtemp(dir=config.temp_dir)
        fifo = os.path.join(fifo_dir, "fifo")
        os.mkfifo(fifo)
        os.chmod(fifo_dir, 0o755)
        os.chmod(fifo, 0o666)

        # First step: we start the first manager.
        first_filename = "manager"
        first_command = ["./%s" % first_filename, "0", fifo]
        first_executables_to_get = {
            first_filename:
            job.executables[first_filename].digest
            }
        first_files_to_get = {
            "input.txt": job.input
            }
        first_allow_path = [fifo_dir]

        # Put the required files into the sandbox
        for filename, digest in first_executables_to_get.iteritems():
            first_sandbox.create_file_from_storage(filename,
                                                   digest,
                                                   executable=True)
        for filename, digest in first_files_to_get.iteritems():
            first_sandbox.create_file_from_storage(filename, digest)

        first = evaluation_step_before_run(
            first_sandbox,
            first_command,
            job.time_limit,
            job.memory_limit,
            first_allow_path,
            stdin_redirect="input.txt",
            wait=False)

        # Second step: we start the second manager.
        second_filename = "manager"
        second_command = ["./%s" % second_filename, "1", fifo]
        second_executables_to_get = {
            second_filename:
            job.executables[second_filename].digest
            }
        second_files_to_get = {}
        second_allow_path = [fifo_dir]

        # Put the required files into the second sandbox
        for filename, digest in second_executables_to_get.iteritems():
            second_sandbox.create_file_from_storage(filename,
                                                    digest,
                                                    executable=True)
        for filename, digest in second_files_to_get.iteritems():
            second_sandbox.create_file_from_storage(filename, digest)

        second = evaluation_step_before_run(
            second_sandbox,
            second_command,
            job.time_limit,
            job.memory_limit,
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

        job.sandboxes = [first_sandbox.path,
                         second_sandbox.path]
        job.plus = second_plus

        success = True
        outcome = None
        text = None

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
            if job.get_output:
                job.user_output = None

        # Otherwise, advance to checking the solution
        else:

            # Check that the output file was created
            if not second_sandbox.file_exists('output.txt'):
                outcome = 0.0
                text = [N_("Evaluation didn't produce file %s"), "output.txt"]
                if job.get_output:
                    job.user_output = None

            else:
                # If asked so, put the output file into the storage
                if job.get_output:
                    job.user_output = second_sandbox.get_file_to_storage(
                        "output.txt",
                        "Output file in job %s" % job.info)

                # If not asked otherwise, evaluate the output file
                if not job.only_execution:
                    # Put the reference solution into the sandbox
                    second_sandbox.create_file_from_storage(
                        "res.txt",
                        job.output)

                    outcome, text = white_diff_step(
                        second_sandbox, "output.txt", "res.txt")

        # Whatever happened, we conclude.
        job.success = success
        job.outcome = str(outcome)
        job.text = text

        delete_sandbox(first_sandbox)
        delete_sandbox(second_sandbox)
