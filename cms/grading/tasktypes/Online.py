#!/usr/bin/env python3

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

import logging
import os
import tempfile
from functools import reduce

from cms import config, rmtree
from cms.grading.Sandbox import wait_without_std, Sandbox
from cms.grading.languagemanager import get_language
from cms.grading.steps import (
    evaluation_step_before_run,
    evaluation_step_after_run,
    human_evaluation_message,
    merge_execution_stats,
    trusted_step,
)

from . import (
    check_executables_number,
    check_manager_present,
    create_sandbox,
    delete_sandbox,
    eval_output,
)

from Communication import Communication

logger = logging.getLogger(__name__)


# Dummy function to mark translatable string.
def N_(message):
    return message


class Online(Communication):
    """Task type class for tasks with a fully admin-controlled process limiting user input and output

    The task type will run *manager*, an admin-provided executable, and one or
    more instances of the user solution, optionally compiled together with a
    language-specific stub.

    During the evaluation, the manager and each of the user processes
    communicate via FIFOs. The manager will read the input, send it (possibly
    with some modifications) to the user process(es). The user processes, either
    via functions provided by the stub or by themselves, will communicate with
    the manager.

    Compared to the Communication task type, the manager does not decided the
    correctness of the solution. This instead handled in the same way as the
    Batch task type.

    The manager reads the input from stdin and writes to stdout and stderr the
    standard manager output (that is, the outcome on stdout and the text on
    stderr, see trusted.py for more information). It receives as argument the
    names of the fifos: first from and to the first user process, then from and
    to the second user process, and so on. It can also print some information
    to a file named "output.txt"; the content of this file will be shown to
    users submitting a user test.

    The user process receives as argument the fifos (from and to the manager)
    and, if there are more than one user processes, the 0-based index of the
    process. The pipes can also be set up to be redirected to stdin/stdout: in
    that case the names of the pipes are not passed as arguments.

    """

    ANSWER_FILENAME = "answer.txt"

    @property
    def name(self):
        """See TaskType.name."""
        return "Communication"

    def __init__(self, parameters):
        super().__init__(parameters)

    def evaluate(self, job, file_cacher):
        """See TaskType.evaluate."""
        if not check_executables_number(job, 1):
            return
        executable_filename = next(iter(job.executables.keys()))
        executable_digest = job.executables[executable_filename].digest

        # Make sure the required manager is among the job managers.
        if not check_manager_present(job, self.MANAGER_FILENAME):
            return
        manager_digest = job.managers[self.MANAGER_FILENAME].digest

        # Indices for the objects related to each user process.
        indices = range(self.num_processes)

        # Create FIFOs.
        fifo_dir = [tempfile.mkdtemp(dir=config.temp_dir) for i in indices]
        fifo_user_to_manager = [
            os.path.join(fifo_dir[i], "u%d_to_m" % i) for i in indices]
        fifo_manager_to_user = [
            os.path.join(fifo_dir[i], "m_to_u%d" % i) for i in indices]
        for i in indices:
            os.mkfifo(fifo_user_to_manager[i])
            os.mkfifo(fifo_manager_to_user[i])
            os.chmod(fifo_dir[i], 0o755)
            os.chmod(fifo_user_to_manager[i], 0o666)
            os.chmod(fifo_manager_to_user[i], 0o666)
        # Names of the fifos after being mapped inside the sandboxes.
        sandbox_fifo_dir = ["/fifo%d" % i for i in indices]
        sandbox_fifo_user_to_manager = [
            os.path.join(sandbox_fifo_dir[i], "u%d_to_m" % i) for i in indices]
        sandbox_fifo_manager_to_user = [
            os.path.join(sandbox_fifo_dir[i], "m_to_u%d" % i) for i in indices]

        # Create the manager sandbox and copy manager and input.
        sandbox_mgr = create_sandbox(file_cacher, name="manager_evaluate")
        job.sandboxes.append(sandbox_mgr.get_root_path())
        sandbox_mgr.create_file_from_storage(
            self.MANAGER_FILENAME, manager_digest, executable=True)
        sandbox_mgr.create_file_from_storage(
            self.INPUT_FILENAME, job.input)

        # Create the user sandbox(es) and copy the executable.
        sandbox_user = [create_sandbox(file_cacher, name="user_evaluate")
                        for i in indices]
        job.sandboxes.extend(s.get_root_path() for s in sandbox_user)
        for i in indices:
            sandbox_user[i].create_file_from_storage(
                executable_filename, executable_digest, executable=True)

        # Start the manager. Redirecting to stdin is unnecessary, but for
        # historical reasons the manager can choose to read from there
        # instead than from INPUT_FILENAME.
        manager_command = ["./%s" % self.MANAGER_FILENAME]
        for i in indices:
            manager_command += [sandbox_fifo_user_to_manager[i],
                                sandbox_fifo_manager_to_user[i]]
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
            config.trusted_sandbox_max_memory_kib * 1024,
            dirs_map=dict((fifo_dir[i], (sandbox_fifo_dir[i], "rw")) for i in indices),
            writable_files=[self.OUTPUT_FILENAME],
            stdin_redirect=self.INPUT_FILENAME,
            stdout_redirect=self.ANSWER_FILENAME,
            multiprocess=job.multithreaded_sandbox,
        )

        # Start the user submissions compiled with the stub.
        language = get_language(job.language)
        main = self.STUB_BASENAME if self._uses_stub() \
               else os.path.splitext(executable_filename)[0]
        processes = [None for i in indices]
        for i in indices:
            args = []
            stdin_redirect = None
            stdout_redirect = None
            if self._uses_fifos():
                args.extend([sandbox_fifo_manager_to_user[i],
                             sandbox_fifo_user_to_manager[i]])
            else:
                stdin_redirect = sandbox_fifo_manager_to_user[i]
                stdout_redirect = sandbox_fifo_user_to_manager[i]
            if self.num_processes != 1:
                args.append(str(i))
            commands = language.get_evaluation_commands(
                executable_filename,
                main=main,
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
                dirs_map={fifo_dir[i]: (sandbox_fifo_dir[i], "rw")},
                stdin_redirect=stdin_redirect,
                stdout_redirect=stdout_redirect,
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

        # If just asked to execute, fill text and set dummy outcome.
        elif job.only_execution:
            outcome = 0.0
            text = [N_("Execution completed successfully")]

        # If the user sandbox detected some problem (timeout, ...),
        # the outcome is 0.0 and the text describes that problem.
        elif not evaluation_success_user:
            outcome = 0.0
            text = human_evaluation_message(stats_user)

        # Otherwise, advance to checking the solution
        else:
            # Check that the output file was created
            if not manager.file_exists(self.ANSWER_FILENAME):
                outcome = 0.0
                text = [N_("Evaluation didn't produce file %s"), self.ANSWER_FILENAME]
                if job.get_output:
                    job.user_output = None

            else:
                # If asked so, put the output file into the storage.
                if job.get_output:
                    job.user_output = manager.get_file_to_storage(
                        self.ANSWER_FILENAME,
                        "Output file in job %s" % job.info,
                        trunc_len=100 * 1024,
                    )

                # If just asked to execute, fill text and set dummy outcome.
                if job.only_execution:
                    outcome = 0.0
                    text = [N_("Execution completed successfully")]

                # Otherwise evaluate the output file.
                else:
                    # TODO: Add option for checker
                    success, outcome, text = eval_output(
                        file_cacher,
                        job,
                        None,  # self.CHECKER_CODENAME if self._uses_checker() else None,
                        user_output_path=manager.relative_path(self.ANSWER_FILENAME),
                    )

        # If asked so, save the output file with additional information,
        # provided that it exists.
        if job.get_output:
            if sandbox_mgr.file_exists(self.OUTPUT_FILENAME):
                job.user_output = sandbox_mgr.get_file_to_storage(
                    self.OUTPUT_FILENAME,
                    "Output file in job %s" % job.info,
                    trunc_len=100 * 1024)
            else:
                job.user_output = None

        # Fill in the job with the results.
        job.success = success
        job.outcome = "%s" % outcome if outcome is not None else None
        job.text = text
        job.plus = stats_user

        delete_sandbox(sandbox_mgr, job.success, job.keep_sandbox)
        for s in sandbox_user:
            delete_sandbox(s, job.success, job.keep_sandbox)
        if job.success and not config.keep_sandbox and not job.keep_sandbox:
            for d in fifo_dir:
                rmtree(d)
