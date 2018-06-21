#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2016 Masaki Hara <ackie.h.gmai@gmail.com>
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
from functools import reduce

from cms import config, rmtree
from cms.grading.Sandbox import wait_without_std, Sandbox
from cms.grading.steps import compilation_step,  evaluation_step_before_run, \
    evaluation_step_after_run, extract_outcome_and_text, \
    human_evaluation_message, merge_execution_stats, trusted_step
from cms.grading.languagemanager import LANGUAGES, get_language
from cms.grading.ParameterTypes import ParameterTypeInt
from cms.grading.TaskType import TaskType, check_executables_number, \
    check_manager_present, create_sandbox, delete_sandbox, \
    is_manager_for_compilation
from cms.db import Executable


logger = logging.getLogger(__name__)


# Dummy function to mark translatable string.
def N_(message):
    return message


class Communication(TaskType):
    """Task type class for tasks with a fully admin-controlled process.

    The task type will run *manager*, an admin-provided executable, and one or
    more instances of the user solution, compiled together with a
    language-specific stub.

    During the evaluation, the manager and each of the user processes
    communicate via FIFOs. The manager will read the input, send it (possibly
    with some modifications) to the user process(es). The user processes, via
    functions provided by the stub, will communicate with the manager. Finally,
    the manager will decide outcome and text, and print them on stdout and
    stderr.

    The manager reads the input from stdin and writes to stdout and stderr the
    standard manager output (that is, the outcome on stdout and the text on
    stderr, see trusted.py for more information). It receives as argument the
    names of the fifos: first from and to the first user process, then from and
    to the second user process, and so on. It can also print some information
    to a file named "output.txt"; the content of this file will be shown to
    users submitting a user test.

    The stub receives as argument the fifos (from and to the manager) and if
    there are more than one user processes, the 0-based index of the process.

    """
    # Filename of the manager (the stand-alone, admin-provided program).
    MANAGER_FILENAME = "manager"
    # Filename of the input in the manager sandbox. The content will be
    # redirected to stdin, and managers should read from there.
    INPUT_FILENAME = "input.txt"
    # Filename where the manager can write additional output to show to users
    # in case of a user test.
    OUTPUT_FILENAME = "output.txt"

    ALLOW_PARTIAL_SUBMISSION = False

    _NUM_PROCESSES = ParameterTypeInt(
        "Number of Processes",
        "num_processes",
        "")

    ACCEPTED_PARAMETERS = [_NUM_PROCESSES]

    @property
    def name(self):
        """See TaskType.name."""
        return "Communication"

    def __init__(self, parameters):
        super(Communication, self).__init__(parameters)

        self.num_processes = 1
        if len(self.parameters) > 0:
            self.num_processes = self.parameters[0]

    def get_compilation_commands(self, submission_format):
        """See TaskType.get_compilation_commands."""
        res = dict()
        for language in LANGUAGES:
            # Collect source filenames.
            source_ext = language.source_extension
            source_filenames = ["stub%s" % source_ext]
            for codename in submission_format:
                source_filenames.append(codename.replace(".%l", source_ext))
            # Compute executable name.
            executable_filename = self._executable_filename(submission_format)
            # Build the compilation commands.
            commands = language.get_compilation_commands(
                source_filenames, executable_filename)
            res[language.name] = commands
        return res

    def get_user_managers(self):
        """See TaskType.get_user_managers."""
        return ["stub.%l"]

    def get_auto_managers(self):
        """See TaskType.get_auto_managers."""
        return ["manager"]

    @staticmethod
    def _executable_filename(codenames):
        """Return the chosen executable name computed from the codenames.

        codenames ([str]): submission format or codename of submitted files,
            may contain %l.

        return (str): a deterministic executable name.

        """
        return "_".join(sorted(codename.replace(".%l", "")
                               for codename in codenames))

    def compile(self, job, file_cacher):
        """See TaskType.compile."""
        language = get_language(job.language)
        source_ext = language.source_extension

        # Prepare the files to copy in the sandbox and to add to the
        # compilation command.
        files_to_get = {}
        source_filenames = []
        # The stub, that must have been provided (copy and add to compilation).
        stub_filename = "stub%s" % source_ext
        if not check_manager_present(job, stub_filename):
            return
        source_filenames.append(stub_filename)
        files_to_get[stub_filename] = job.managers[stub_filename].digest
        # User's submitted file(s) (copy and add to compilation).
        for codename, file_ in iteritems(job.files):
            source_filename = codename.replace(".%l", source_ext)
            source_filenames.append(source_filename)
            files_to_get[source_filename] = file_.digest
        # Any other useful manager (just copy).
        for filename, manager in iteritems(job.managers):
            if is_manager_for_compilation(filename, language):
                files_to_get[filename] = manager.digest

        # Prepare the compilation command
        executable_filename = self._executable_filename(iterkeys(job.files))
        commands = language.get_compilation_commands(
            source_filenames, executable_filename)

        # Create the sandbox.
        sandbox = create_sandbox(file_cacher, name="compile")
        job.sandboxes.append(sandbox.path)

        # Copy all required files in the sandbox.
        for filename, digest in iteritems(files_to_get):
            sandbox.create_file_from_storage(filename, digest)

        # Run the compilation.
        box_success, compilation_success, text, stats = \
            compilation_step(sandbox, commands)

        # Retrieve the compiled executables.
        job.success = box_success
        job.compilation_success = compilation_success
        job.text = text
        job.plus = stats
        if box_success and compilation_success:
            digest = sandbox.get_file_to_storage(
                executable_filename,
                "Executable %s for %s" % (executable_filename, job.info))
            job.executables[executable_filename] = \
                Executable(executable_filename, digest)

        # Cleanup.
        delete_sandbox(sandbox, job.success)

    def evaluate(self, job, file_cacher):
        """See TaskType.evaluate."""
        if not check_executables_number(job, 1):
            return
        executable_filename = next(iterkeys(job.executables))
        executable_digest = job.executables[executable_filename].digest

        # Make sure the required manager is among the job managers.
        if not check_manager_present(job, Communication.MANAGER_FILENAME):
            return
        manager_digest = job.managers[Communication.MANAGER_FILENAME].digest

        # Indices for the objects related to each user process.
        indices = range(self.num_processes)

        # Create FIFOs.
        fifo_dir = [tempfile.mkdtemp(dir=config.temp_dir) for i in indices]
        fifo_in = [os.path.join(fifo_dir[i], "in%d" % i) for i in indices]
        fifo_out = [os.path.join(fifo_dir[i], "out%d" % i) for i in indices]
        for i in indices:
            os.mkfifo(fifo_in[i])
            os.mkfifo(fifo_out[i])
            os.chmod(fifo_dir[i], 0o755)
            os.chmod(fifo_in[i], 0o666)
            os.chmod(fifo_out[i], 0o666)

        # Create the manager sandbox and copy manager and input.
        sandbox_mgr = create_sandbox(file_cacher, name="manager_evaluate")
        job.sandboxes.append(sandbox_mgr.path)
        sandbox_mgr.create_file_from_storage(
            Communication.MANAGER_FILENAME, manager_digest, executable=True)
        sandbox_mgr.create_file_from_storage(
            Communication.INPUT_FILENAME, job.input)

        # Create the user sandbox(es) and copy the executable.
        sandbox_user = [create_sandbox(file_cacher, name="user_evaluate")
                        for i in indices]
        job.sandboxes.extend(s.path for s in sandbox_user)
        for i in indices:
            sandbox_user[i].create_file_from_storage(
                executable_filename, executable_digest, executable=True)

        # Start the manager. Redirecting to stdin is unnecessary, but for
        # historical reasons the manager can choose to read from there
        # instead than from INPUT_FILENAME.
        manager_command = ["./%s" % Communication.MANAGER_FILENAME]
        for i in indices:
            manager_command += [fifo_in[i], fifo_out[i]]
        # We could use trusted_step for the manager, since it's fully
        # admin-controlled. But trusted_step is only synchronous at the moment.
        # Thus we use evaluation_step, and we set a time limit generous enough
        # to prevent user programs from sending the manager in timeout.
        # This means that:
        # - the manager wall clock timeout must be greater than the sum of all
        #     wall clock timeouts of the user programs;
        # - with the assumption that the work the manager performs is not
        #     greater than the work performed by the user programs, the manager
        #     user timeout must be greater than the maximum allowed total time
        #     of the user programs; in theory, this is the task's time limit,
        #     but in practice is num_processes times that because the
        #     constraint on the total time can only be enforced after all user
        #     programs terminated.
        manager_time_limit = max(self.num_processes * (job.time_limit + 1.0),
                                 config.trusted_sandbox_max_time_s)
        manager = evaluation_step_before_run(
            sandbox_mgr,
            manager_command,
            manager_time_limit,
            config.trusted_sandbox_max_memory_kib // 1024,
            allow_dirs=fifo_dir,
            writable_files=[Communication.OUTPUT_FILENAME],
            stdin_redirect=Communication.INPUT_FILENAME,
            multiprocess=job.multithreaded_sandbox)

        # Start the user submissions compiled with the stub.
        language = get_language(job.language)
        processes = [None for i in indices]
        for i in indices:
            args = [fifo_out[i], fifo_in[i]]
            if self.num_processes != 1:
                args.append(str(i))
            commands = language.get_evaluation_commands(
                executable_filename,
                main="stub",
                args=args)
            # Assumes that the actual execution of the user solution is the
            # last command in commands, and that the previous are "setup"
            # that don't need tight control.
            if len(commands) > 1:
                trusted_step(sandbox_user[i], commands[:-1])
            processes[i] = evaluation_step_before_run(
                sandbox_user[i],
                commands[-1],
                job.time_limit,
                job.memory_limit,
                allow_dirs=[fifo_dir[i]],
                multiprocess=job.multithreaded_sandbox)

        # Wait for the processes to conclude, without blocking them on I/O.
        wait_without_std(processes + [manager])

        # Get the results of the manager sandbox.
        box_success_mgr, evaluation_success_mgr, unused_stats_mgr = \
            evaluation_step_after_run(sandbox_mgr)

        # Coalesce the results of the user sandboxes.
        user_results = [evaluation_step_after_run(s) for s in sandbox_user]
        box_success_user = all(r[0] for r in user_results)
        evaluation_success_user = all(r[1] for r in user_results)
        stats_user = reduce(merge_execution_stats,
                            [r[2] for r in user_results])
        # The actual running time is the sum of every user process, but each
        # sandbox can only check its own; if the sum is greater than the time
        # limit we adjust the result.
        if box_success_user and evaluation_success_user and \
                stats_user["execution_time"] >= job.time_limit:
            evaluation_success_user = False
            stats_user['exit_status'] = Sandbox.EXIT_TIMEOUT

        success = box_success_user \
            and box_success_mgr and evaluation_success_mgr
        outcome = None
        text = None

        # If at least one sandbox had problems, or the manager did not
        # terminate correctly, we report an error (and no need for user stats).
        if not success:
            stats_user = None
            pass

        # If just asked to execute, fill text and set dummy outcome.
        elif job.only_execution:
            outcome = 0.0
            text = [N_("Execution completed successfully")]

        # If the user sandbox detected some problem (timeout, ...),
        # the outcome is 0.0 and the text describes that problem.
        elif not evaluation_success_user:
            outcome = 0.0
            text = human_evaluation_message(stats_user, job.feedback_level)

        # Otherwise, we use the manager to obtain the outcome.
        else:
            outcome, text = extract_outcome_and_text(sandbox_mgr)

        # If asked so, save the output file with additional information,
        # provided that it exists.
        if job.get_output:
            if sandbox_mgr.file_exists(Communication.OUTPUT_FILENAME):
                job.user_output = sandbox_mgr.get_file_to_storage(
                    Communication.OUTPUT_FILENAME,
                    "Output file in job %s" % job.info,
                    trunc_len=100 * 1024)
            else:
                job.user_output = None

        # Fill in the job with the results.
        job.success = success
        job.outcome = "%s" % outcome if outcome is not None else None
        job.text = text
        job.plus = stats_user

        delete_sandbox(sandbox_mgr, job.success)
        for s in sandbox_user:
            delete_sandbox(s, job.success)
        if not config.keep_sandbox:
            for d in fifo_dir:
                rmtree(d)
