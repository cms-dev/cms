#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2015 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2014 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

from cms import LANGUAGES, LANGUAGE_TO_SOURCE_EXT_MAP, \
    LANGUAGE_TO_HEADER_EXT_MAP, LANGUAGE_TO_OBJ_EXT_MAP
from cms.grading import get_compilation_commands, get_evaluation_commands, \
    compilation_step, evaluation_step, human_evaluation_message, \
    is_evaluation_passed, extract_outcome_and_text, white_diff_step
from cms.grading.ParameterTypes import ParameterTypeCollection, \
    ParameterTypeChoice, ParameterTypeString
from cms.grading.TaskType import TaskType, \
    create_sandbox, delete_sandbox
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
        for language in LANGUAGES:
            format_filename = submission_format[0]
            source_ext = LANGUAGE_TO_SOURCE_EXT_MAP[language]
            source_filenames = []
            # If a grader is specified, we add to the command line (and to
            # the files to get) the corresponding manager.
            if self.parameters[0] == "grader":
                source_filenames.append("grader%s" % source_ext)
            source_filenames.append(format_filename.replace(".%l", source_ext))
            executable_filename = format_filename.replace(".%l", "")
            commands = get_compilation_commands(language,
                                                source_filenames,
                                                executable_filename)
            res[language] = commands
        return res

    def get_user_managers(self, unused_submission_format):
        """See TaskType.get_user_managers."""
        return []

    def get_auto_managers(self):
        """See TaskType.get_auto_managers."""
        return None

    def compile(self, job, file_cacher):
        """See TaskType.compile."""
        # Detect the submission's language. The checks about the
        # formal correctedness of the submission are done in CWS,
        # before accepting it.
        language = job.language
        source_ext = LANGUAGE_TO_SOURCE_EXT_MAP[language]

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
            return True

        # Create the sandbox
        sandbox = create_sandbox(file_cacher)
        job.sandboxes.append(sandbox.path)

        # Prepare the source files in the sandbox
        files_to_get = {}
        format_filename = job.files.keys()[0]
        source_filenames = []
        source_filenames.append(format_filename.replace(".%l", source_ext))
        files_to_get[source_filenames[0]] = \
            job.files[format_filename].digest
        # If a grader is specified, we add to the command line (and to
        # the files to get) the corresponding manager. The grader must
        # be the first file in source_filenames.
        if self.parameters[0] == "grader":
            source_filenames.insert(0, "grader%s" % source_ext)
            files_to_get["grader%s" % source_ext] = \
                job.managers["grader%s" % source_ext].digest

        # Also copy all managers that might be useful during compilation.
        for filename in job.managers.iterkeys():
            if any(filename.endswith(header)
                   for header in LANGUAGE_TO_HEADER_EXT_MAP.itervalues()):
                files_to_get[filename] = \
                    job.managers[filename].digest
            elif any(filename.endswith(source)
                     for source in LANGUAGE_TO_SOURCE_EXT_MAP.itervalues()):
                files_to_get[filename] = \
                    job.managers[filename].digest
            elif any(filename.endswith(obj)
                     for obj in LANGUAGE_TO_OBJ_EXT_MAP.itervalues()):
                files_to_get[filename] = \
                    job.managers[filename].digest

        for filename, digest in files_to_get.iteritems():
            sandbox.create_file_from_storage(filename, digest)

        # Prepare the compilation command
        executable_filename = format_filename.replace(".%l", "")
        commands = get_compilation_commands(language,
                                            source_filenames,
                                            executable_filename)

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
        delete_sandbox(sandbox)

    def evaluate(self, job, file_cacher):
        """See TaskType.evaluate."""
        # Create the sandbox
        sandbox = create_sandbox(file_cacher)

        # Prepare the execution
        executable_filename = job.executables.keys()[0]
        language = job.language
        commands = get_evaluation_commands(language, executable_filename)
        executables_to_get = {
            executable_filename:
            job.executables[executable_filename].digest
            }
        input_filename, output_filename = self.parameters[1]
        stdin_redirect = None
        stdout_redirect = None
        files_allowing_write = []
        if input_filename == "":
            input_filename = "input.txt"
            stdin_redirect = input_filename
        if output_filename == "":
            output_filename = "output.txt"
            stdout_redirect = output_filename
        else:
            files_allowing_write.append(output_filename)
        files_to_get = {
            input_filename: job.input
            }

        # Put the required files into the sandbox
        for filename, digest in executables_to_get.iteritems():
            sandbox.create_file_from_storage(filename, digest, executable=True)
        for filename, digest in files_to_get.iteritems():
            sandbox.create_file_from_storage(filename, digest)

        # Actually performs the execution
        success, plus = evaluation_step(
            sandbox,
            commands,
            job.time_limit,
            job.memory_limit,
            writable_files=files_allowing_write,
            stdin_redirect=stdin_redirect,
            stdout_redirect=stdout_redirect)

        job.sandboxes = [sandbox.path]
        job.plus = plus

        outcome = None
        text = None

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
            if not sandbox.file_exists(output_filename):
                outcome = 0.0
                text = [N_("Evaluation didn't produce file %s"),
                        output_filename]
                if job.get_output:
                    job.user_output = None

            else:
                # If asked so, put the output file into the storage
                if job.get_output:
                    job.user_output = sandbox.get_file_to_storage(
                        output_filename,
                        "Output file in job %s" % job.info,
                        trunc_len=100 * 1024)

                # If just asked to execute, fill text and set dummy
                # outcome.
                if job.only_execution:
                    outcome = 0.0
                    text = [N_("Execution completed successfully")]

                # Otherwise evaluate the output file.
                else:

                    # Put the reference solution into the sandbox
                    sandbox.create_file_from_storage(
                        "res.txt",
                        job.output)

                    # Check the solution with white_diff
                    if self.parameters[2] == "diff":
                        outcome, text = white_diff_step(
                            sandbox, output_filename, "res.txt")

                    # Check the solution with a comparator
                    elif self.parameters[2] == "comparator":
                        manager_filename = "checker"

                        if manager_filename not in job.managers:
                            logger.error("Configuration error: missing or "
                                         "invalid comparator (it must be "
                                         "named 'checker')",
                                         extra={"operation": job.info})
                            success = False

                        else:
                            sandbox.create_file_from_storage(
                                manager_filename,
                                job.managers[manager_filename].digest,
                                executable=True)
                            # Rewrite input file. The untrusted
                            # contestant program should not be able to
                            # modify it; however, the grader may
                            # destroy the input file to prevent the
                            # contestant's program from directly
                            # accessing it. Since we cannot create
                            # files already existing in the sandbox,
                            # we try removing the file first.
                            try:
                                sandbox.remove_file(input_filename)
                            except OSError as e:
                                # Let us be extra sure that the file
                                # was actually removed and we did not
                                # mess up with permissions.
                                assert not sandbox.file_exists(input_filename)
                            sandbox.create_file_from_storage(
                                input_filename,
                                job.input)
                            success, _ = evaluation_step(
                                sandbox,
                                [["./%s" % manager_filename,
                                  input_filename, "res.txt", output_filename]])
                        if success:
                            try:
                                outcome, text = \
                                    extract_outcome_and_text(sandbox)
                            except ValueError, e:
                                logger.error("Invalid output from "
                                             "comparator: %s", e.message,
                                             extra={"operation": job.info})
                                success = False

                    else:
                        raise ValueError("Unrecognized third parameter"
                                         " `%s' for Batch tasktype." %
                                         self.parameters[2])

        # Whatever happened, we conclude.
        job.success = success
        job.outcome = "%s" % outcome if outcome is not None else None
        job.text = text

        delete_sandbox(sandbox)
