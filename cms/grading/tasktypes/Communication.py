#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
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
import os
import tempfile

from cms import LANGUAGES, LANGUAGE_TO_SOURCE_EXT_MAP, \
    LANGUAGE_TO_HEADER_EXT_MAP, LANGUAGE_TO_OBJ_EXT_MAP, config
from cms.grading.Sandbox import wait_without_std
from cms.grading import get_compilation_commands, compilation_step, \
    human_evaluation_message, is_evaluation_passed, \
    extract_outcome_and_text, evaluation_step_before_run, \
    evaluation_step_after_run
from cms.grading.TaskType import TaskType, \
    create_sandbox, delete_sandbox
from cms.db import Executable
from cms.io.GeventUtils import rmtree


logger = logging.getLogger(__name__)


# Dummy function to mark translatable string.
def N_(message):
    return message


class Communication(TaskType):
    """Task type class for tasks that requires:

    - a *manager* that reads the input file, work out the perfect
      solution on its own, and communicate the input (maybe with some
      modifications) on its standard output; it then reads the
      response of the user's solution from the standard input and
      write the outcome;

    - a *stub* that compiles with the user's source, reads from
      standard input what the manager says, and write back the user's
      solution to stdout.

    """
    ALLOW_PARTIAL_SUBMISSION = False

    name = "Communication"

    def get_compilation_commands(self, submission_format):
        """See TaskType.get_compilation_commands."""
        res = dict()
        for language in LANGUAGES:
            format_filename = submission_format[0]
            source_ext = LANGUAGE_TO_SOURCE_EXT_MAP[language]
            source_filenames = []
            source_filenames.append("stub%s" % source_ext)
            source_filenames.append(format_filename.replace(".%l", source_ext))
            executable_filename = format_filename.replace(".%l", "")
            commands = get_compilation_commands(language,
                                                source_filenames,
                                                executable_filename)
            res[language] = commands
        return res

    def get_user_managers(self, unused_submission_format):
        """See TaskType.get_user_managers."""
        return ["stub.%l"]

    def get_auto_managers(self):
        """See TaskType.get_auto_managers."""
        return ["manager"]

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
        # Stub.
        source_filenames.append("stub%s" % source_ext)
        files_to_get[source_filenames[-1]] = \
            job.managers["stub%s" % source_ext].digest
        # User's submission.
        source_filenames.append(format_filename.replace(".%l", source_ext))
        files_to_get[source_filenames[-1]] = \
            job.files[format_filename].digest

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
        # Create sandboxes and FIFOs
        sandbox_mgr = create_sandbox(file_cacher)
        sandbox_user = create_sandbox(file_cacher)
        fifo_dir = tempfile.mkdtemp(dir=config.temp_dir)
        fifo_in = os.path.join(fifo_dir, "in")
        fifo_out = os.path.join(fifo_dir, "out")
        os.mkfifo(fifo_in)
        os.mkfifo(fifo_out)
        os.chmod(fifo_dir, 0o755)
        os.chmod(fifo_in, 0o666)
        os.chmod(fifo_out, 0o666)

        # First step: we start the manager.
        manager_filename = "manager"
        manager_command = ["./%s" % manager_filename, fifo_in, fifo_out]
        manager_executables_to_get = {
            manager_filename:
            job.managers[manager_filename].digest
            }
        manager_files_to_get = {
            "input.txt": job.input
            }
        manager_allow_dirs = [fifo_dir]
        for filename, digest in manager_executables_to_get.iteritems():
            sandbox_mgr.create_file_from_storage(
                filename, digest, executable=True)
        for filename, digest in manager_files_to_get.iteritems():
            sandbox_mgr.create_file_from_storage(filename, digest)
        manager = evaluation_step_before_run(
            sandbox_mgr,
            manager_command,
            job.time_limit,
            0,
            allow_dirs=manager_allow_dirs,
            writable_files=["output.txt"],
            stdin_redirect="input.txt")

        # Second step: we start the user submission compiled with the
        # stub.
        executable_filename = job.executables.keys()[0]
        command = ["./%s" % executable_filename, fifo_out, fifo_in]
        executables_to_get = {
            executable_filename:
            job.executables[executable_filename].digest
            }
        user_allow_dirs = [fifo_dir]
        for filename, digest in executables_to_get.iteritems():
            sandbox_user.create_file_from_storage(
                filename, digest, executable=True)
        process = evaluation_step_before_run(
            sandbox_user,
            command,
            job.time_limit,
            job.memory_limit,
            allow_dirs=user_allow_dirs)

        # Consume output.
        wait_without_std([process, manager])
        # TODO: check exit codes with translate_box_exitcode.

        success_user, plus_user = \
            evaluation_step_after_run(sandbox_user)
        success_mgr, unused_plus_mgr = \
            evaluation_step_after_run(sandbox_mgr)

        job.sandboxes = [sandbox_user.path,
                         sandbox_mgr.path]
        job.plus = plus_user

        # If at least one evaluation had problems, we report the
        # problems.
        if not success_user or not success_mgr:
            success, outcome, text = False, None, None
        # If the user sandbox detected some problem (timeout, ...),
        # the outcome is 0.0 and the text describes that problem.
        elif not is_evaluation_passed(plus_user):
            success = True
            outcome, text = 0.0, human_evaluation_message(plus_user)
        # Otherwise, we use the manager to obtain the outcome.
        else:
            success = True
            outcome, text = extract_outcome_and_text(sandbox_mgr)

        # If asked so, save the output file, provided that it exists
        if job.get_output:
            if sandbox_mgr.file_exists("output.txt"):
                job.user_output = sandbox_mgr.get_file_to_storage(
                    "output.txt",
                    "Output file in job %s" % job.info)
            else:
                job.user_output = None

        # Whatever happened, we conclude.
        job.success = success
        job.outcome = "%s" % outcome if outcome is not None else None
        job.text = text

        delete_sandbox(sandbox_mgr)
        delete_sandbox(sandbox_user)
        if not config.keep_sandbox:
            rmtree(fifo_dir)
