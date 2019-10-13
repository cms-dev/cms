#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Tests for the Communication task type."""

import os
import unittest
from unittest.mock import MagicMock, call, ANY, patch

from cms import config
from cms.db import File, Manager, Executable
from cms.grading.Job import CompilationJob, EvaluationJob
from cms.grading.steps import merge_execution_stats
from cms.grading.tasktypes.Communication import Communication
from cmstestsuite.unit_tests.filesystemmixin import FileSystemMixin
from cmstestsuite.unit_tests.grading.tasktypes.tasktypetestutils import \
    COMPILATION_COMMAND_1, COMPILATION_COMMAND_2, LANG_1, LANG_2, OUTCOME, \
    STATS_OK, STATS_RE, TEXT, TaskTypeTestMixin, fake_compilation_commands


FILE_FOO_L1 = File(digest="digest of foo.l1", filename="foo.%l")
FILE_BAR_L1 = File(digest="digest of bar.l1", filename="bar.%l")
MANAGER = Manager(digest="digest of manager", filename="manager")
STUB_L1 = Manager(digest="digest of stub.l1", filename="stub.l1")
EXE_FOO = Executable(digest="digest of foo", filename="foo")


class TestGetCompilationCommands(TaskTypeTestMixin, unittest.TestCase):
    """Tests for get_compilation_commands()."""

    def setUp(self):
        super().setUp()
        self.setUpMocks("Communication")
        self.languages.update({LANG_1, LANG_2})

    def test_single_process(self):
        tt = Communication([1, "stub", "fifo_io"])
        cc = tt.get_compilation_commands(["foo.%l"])
        self.assertEqual(cc, {
            "L1": fake_compilation_commands(
                COMPILATION_COMMAND_1, ["stub.l1", "foo.l1"], "foo"),
            "L2": fake_compilation_commands(
                COMPILATION_COMMAND_2, ["stub.l2", "foo.l2"], "foo.ext"),
        })

    def test_two_processes(self):
        # Compilation commands are the same regardless of the number of
        # processes.
        tt = Communication([2, "stub", "fifo_io"])
        cc = tt.get_compilation_commands(["foo.%l"])
        self.assertEqual(cc, {
            "L1": fake_compilation_commands(
                COMPILATION_COMMAND_1, ["stub.l1", "foo.l1"], "foo"),
            "L2": fake_compilation_commands(
                COMPILATION_COMMAND_2, ["stub.l2", "foo.l2"], "foo.ext"),
        })

    def test_many_files(self):
        # Communication supports multiple files in the submission format, that
        # are just compiled together.
        tt = Communication([1, "stub", "fifo_io"])
        cc = tt.get_compilation_commands(["foo.%l", "bar.%l"])
        self.assertEqual(cc, {
            "L1": fake_compilation_commands(
                COMPILATION_COMMAND_1, ["stub.l1", "foo.l1", "bar.l1"],
                "bar_foo"),
            "L2": fake_compilation_commands(
                COMPILATION_COMMAND_2, ["stub.l2", "foo.l2", "bar.l2"],
                "bar_foo.ext"),
        })

    def test_no_stub(self):
        # Submissions can be compiled as stand-alone programs, with no
        # stubs.
        tt = Communication([1, "alone", "fifo_io"])
        cc = tt.get_compilation_commands(["foo.%l"])
        self.assertEqual(cc, {
            "L1": fake_compilation_commands(
                COMPILATION_COMMAND_1, ["foo.l1"], "foo"),
            "L2": fake_compilation_commands(
                COMPILATION_COMMAND_2, ["foo.l2"], "foo.ext"),
        })

    def test_std_io(self):
        # Compilation commands are the same regardless of whether we use
        # stdin/stdout or pipes.
        tt = Communication([1, "stub", "std_io"])
        cc = tt.get_compilation_commands(["foo.%l"])
        self.assertEqual(cc, {
            "L1": fake_compilation_commands(
                COMPILATION_COMMAND_1, ["stub.l1", "foo.l1"], "foo"),
            "L2": fake_compilation_commands(
                COMPILATION_COMMAND_2, ["stub.l2", "foo.l2"], "foo.ext"),
        })


class TestCompile(TaskTypeTestMixin, unittest.TestCase):
    """Tests for compile().

    prepare() creates a task type and a job with the given arguments, including
    the return value of compilation_step(), which is by default a success.

    compile() doesn't depend on any parameter, but depends on the number of
    source files passed by the user (that is, declared in the submission
    format), since Communication doesn't enforce a particular submission
    format.

    """

    def setUp(self):
        super().setUp()
        self.setUpMocks("Communication")
        self.languages.update({LANG_1})
        self.file_cacher = MagicMock()

    @staticmethod
    def job(files=None, managers=None):
        files = files if files is not None else {}
        managers = managers if managers is not None else {}
        return CompilationJob(language="L1", files=files, managers=managers)

    def prepare(self, parameters, files=None, managers=None,
                compilation_step_return_value=(True, True, TEXT, STATS_OK)):
        tt = Communication(parameters)
        job = self.job(files, managers)
        self.compilation_step.return_value = compilation_step_return_value
        return tt, job

    def assertResultsInJob(
            self, job, success, compilation_success, text, stats):
        self.assertEqual(job.success, success)
        self.assertEqual(job.compilation_success, compilation_success)
        self.assertEqual(job.text, text)
        self.assertEqual(job.plus, stats)

    def test_one_file_success(self):
        tt, job = self.prepare(
            [1, "stub", "fifo_io"],
            {"foo.%l": FILE_FOO_L1}, {"stub.l1": STUB_L1})
        sandbox = self.expect_sandbox()
        sandbox.get_file_to_storage.return_value = "exe_digest"

        tt.compile(job, self.file_cacher)

        # Sandbox created with the correct file cacher and name.
        self.Sandbox.assert_called_once_with(self.file_cacher, name="compile")
        # We need all user source files, and the stub for the same language.
        sandbox.create_file_from_storage.assert_has_calls(
            [call("foo.l1", "digest of foo.l1"),
             call("stub.l1", "digest of stub.l1")], any_order=True)
        self.assertEqual(sandbox.create_file_from_storage.call_count, 2)
        # Compilation step called correctly.
        self.compilation_step.assert_called_once_with(
            sandbox, fake_compilation_commands(
                COMPILATION_COMMAND_1, ["stub.l1", "foo.l1"], "foo"))
        # Results put in job, executable stored and sandbox deleted.
        self.assertResultsInJob(job, True, True, TEXT, STATS_OK)
        sandbox.get_file_to_storage.assert_called_once_with("foo", ANY)
        sandbox.cleanup.assert_called_once_with(delete=True)

    def test_one_file_compilation_failure(self):
        tt, job = self.prepare(
            [1, "stub", "fifo_io"],
            {"foo.%l": FILE_FOO_L1}, {"stub.l1": STUB_L1})
        self.compilation_step.return_value = True, False, TEXT, STATS_RE
        sandbox = self.expect_sandbox()

        tt.compile(job, self.file_cacher)

        # If the compilation failed, we want to return the reason to the user.
        self.assertResultsInJob(job, True, False, TEXT, STATS_RE)
        # But no executable stored.
        sandbox.get_file_to_storage.assert_not_called()
        # Still, we delete the sandbox, since it's not an error.
        sandbox.cleanup.assert_called_once_with(delete=True)

    def test_one_file_sandbox_failure(self):
        # Sandbox (or CMS) failure. It's the admins' fault.
        tt, job = self.prepare(
            [1, "stub", "fifo_io"],
            {"foo.%l": FILE_FOO_L1}, {"stub.l1": STUB_L1})
        self.compilation_step.return_value = False, None, None, None
        sandbox = self.expect_sandbox()

        tt.compile(job, self.file_cacher)

        self.assertResultsInJob(job, False, None, None, None)
        sandbox.get_file_to_storage.assert_not_called()
        # We preserve the sandbox to let admins check the problem.
        sandbox.cleanup.assert_called_once_with(delete=False)

    def test_many_files_success(self):
        tt, job = self.prepare(
            [1, "stub", "fifo_io"],
            {"foo.%l": FILE_FOO_L1, "bar.%l": FILE_BAR_L1},
            {"stub.l1": STUB_L1})
        sandbox = self.expect_sandbox()
        sandbox.get_file_to_storage.return_value = "exe_digest"

        tt.compile(job, self.file_cacher)

        # Sandbox created with the correct file cacher and name.
        self.Sandbox.assert_called_once_with(self.file_cacher,
                                             name="compile")
        # We need all user source files in addition to the stub.
        sandbox.create_file_from_storage.assert_has_calls(
            [call("foo.l1", "digest of foo.l1"),
             call("bar.l1", "digest of bar.l1"),
             call("stub.l1", "digest of stub.l1")], any_order=True)
        self.assertEqual(sandbox.create_file_from_storage.call_count, 3)
        # Compilation step called correctly.
        self.compilation_step.assert_called_once_with(
            sandbox, fake_compilation_commands(
                COMPILATION_COMMAND_1, ["stub.l1", "foo.l1", "bar.l1"],
                "bar_foo"))
        # Results put in job, executable stored and sandbox deleted.
        self.assertResultsInJob(job, True, True, TEXT, STATS_OK)
        sandbox.get_file_to_storage.assert_called_once_with("bar_foo", ANY)
        sandbox.cleanup.assert_called_once_with(delete=True)

    def test_no_stub_success(self):
        tt, job = self.prepare(
            [1, "alone", "fifo_io"],
            {"foo.%l": FILE_FOO_L1}, {})
        sandbox = self.expect_sandbox()
        sandbox.get_file_to_storage.return_value = "exe_digest"

        tt.compile(job, self.file_cacher)

        # Sandbox created with the correct file cacher and name.
        self.Sandbox.assert_called_once_with(self.file_cacher,
                                             name="compile")
        sandbox.create_file_from_storage.assert_called_once_with(
            "foo.l1", "digest of foo.l1")
        # Compilation step called correctly, without the stub.
        self.compilation_step.assert_called_once_with(
            sandbox, fake_compilation_commands(
                COMPILATION_COMMAND_1, ["foo.l1"], "foo"))
        # Results put in job, executable stored and sandbox deleted.
        self.assertResultsInJob(job, True, True, TEXT, STATS_OK)
        sandbox.get_file_to_storage.assert_called_once_with("foo", ANY)
        sandbox.cleanup.assert_called_once_with(delete=True)

    def test_no_stub_but_stub_given_success(self):
        # A stub is given but should be ignored.
        tt, job = self.prepare(
            [1, "alone", "fifo_io"],
            {"foo.%l": FILE_FOO_L1}, {"stub.l1": STUB_L1})
        sandbox = self.expect_sandbox()
        sandbox.get_file_to_storage.return_value = "exe_digest"

        tt.compile(job, self.file_cacher)

        # Sandbox created with the correct file cacher and name.
        self.Sandbox.assert_called_once_with(self.file_cacher,
                                             name="compile")
        # The stub is put in the sandbox because it is a manager with an
        # extension that hints that it could be useful for compilations.
        sandbox.create_file_from_storage.assert_has_calls(
            [call("foo.l1", "digest of foo.l1"),
             call("stub.l1", "digest of stub.l1")], any_order=True)
        self.assertEqual(sandbox.create_file_from_storage.call_count, 2)
        # Compilation step called correctly, without the stub.
        self.compilation_step.assert_called_once_with(
            sandbox, fake_compilation_commands(
                COMPILATION_COMMAND_1, ["foo.l1"], "foo"))
        # Results put in job, executable stored and sandbox deleted.
        self.assertResultsInJob(job, True, True, TEXT, STATS_OK)
        sandbox.get_file_to_storage.assert_called_once_with("foo", ANY)
        sandbox.cleanup.assert_called_once_with(delete=True)


class TestEvaluate(TaskTypeTestMixin, FileSystemMixin, unittest.TestCase):
    """Tests for evaluate().

    prepare() creates a task type and a job with the given arguments, and in
    addition sets up successful return values for the two steps
    (evaluation_step(_after_run) and extract_outcome_and_text).

    evaluate() depends on the only parameter (number of user processes). We
    test both, but shared failure cases only in the single process case.

    """

    def setUp(self):
        super().setUp()
        self.setUpMocks("Communication")
        self.languages.update({LANG_1})
        self.file_cacher = MagicMock()
        # Write temp files (the fifos) in a subpath of the fsmixin directory.
        self._mkdtemp_idx = 0
        patcher = patch("cms.grading.tasktypes.Communication.tempfile.mkdtemp",
                        MagicMock(side_effect=self._mock_mkdtemp))
        self.addCleanup(patcher.stop)
        self.mkdtemp = patcher.start()

    def _mock_mkdtemp(self, dir=None):
        p = self.makedirs(str(self._mkdtemp_idx))
        self._mkdtemp_idx += 1
        return p

    @staticmethod
    def job(executables, managers):
        return EvaluationJob(language="L1",
                             input="digest of input",
                             output="digest of correct output",
                             time_limit=2.5,
                             memory_limit=123 * 1024 * 1024,
                             executables=executables,
                             managers=managers,
                             multithreaded_sandbox=True)

    def prepare(self, parameters, executables, managers):
        tt = Communication(parameters)
        job = self.job(executables, managers)
        self.evaluation_step_after_run.return_value = (True, True, STATS_OK)
        self.extract_outcome_and_text.return_value = (OUTCOME, TEXT)
        return tt, job

    def assertResultsInJob(self, job, success, outcome, text, stats):
        self.assertEqual(job.success, success)
        self.assertEqual(job.outcome, outcome)
        self.assertEqual(job.text, text)
        self.assertEqual(job.plus, stats)

    def _set_evaluation_step_return_values(self, sandbox_to_return_value):
        """Set the return value of evaluation_step_after_run for each sandbox.

        sandbox_to_return_value ({Sandbox|MagicMock: object}): map from the
            sandbox to the return value of evaluation_step_after_run when
            called with that sandbox as first argument.

        """
        self.evaluation_step_after_run.side_effect = \
            lambda sandbox, *args, **kwargs: sandbox_to_return_value[sandbox]

    @patch.object(config, "trusted_sandbox_max_time_s", 4321)
    @patch.object(config, "trusted_sandbox_max_memory_kib", 1234 * 1024)
    def test_single_process_success(self):
        tt, job = self.prepare(
            [1, "stub", "fifo_io"],
            {"foo": EXE_FOO}, {"manager": MANAGER})
        sandbox_mgr = self.expect_sandbox()
        sandbox_usr = self.expect_sandbox()

        tt.evaluate(job, self.file_cacher)

        # Sandboxes created with the correct file cacher and names.
        self.Sandbox.assert_has_calls([
            call(self.file_cacher, name="manager_evaluate"),
            call(self.file_cacher, name="user_evaluate"),
        ], any_order=False)
        self.assertEqual(self.Sandbox.call_count, 2)
        # We need input (with the default filename for redirection) and
        # executable copied in the sandbox.
        sandbox_mgr.create_file_from_storage.assert_has_calls([
            call("manager", "digest of manager", executable=True),
            call("input.txt", "digest of input"),
        ], any_order=True)
        self.assertEqual(sandbox_mgr.create_file_from_storage.call_count, 2)
        sandbox_usr.create_file_from_storage.assert_has_calls([
            call("foo", "digest of foo", executable=True),
        ], any_order=True)
        self.assertEqual(sandbox_usr.create_file_from_storage.call_count, 1)
        # Evaluation step called with the right arguments, in particular
        # redirects, and no (other) writable files. For the user's command,
        # see fake_evaluation_commands in the mixin.
        cmdline_mgr = ["./manager",
                       "/fifo0/u0_to_m", "/fifo0/m_to_u0"]
        cmdline_usr = ["run1", "foo", "stub",
                       "/fifo0/m_to_u0", "/fifo0/u0_to_m"]
        self.evaluation_step_before_run.assert_has_calls([
            call(sandbox_mgr, cmdline_mgr, 4321, 1234 * 1024 * 1024,
                 dirs_map={os.path.join(self.base_dir, "0"): ("/fifo0", "rw")},
                 writable_files=["output.txt"],
                 stdin_redirect="input.txt", multiprocess=True),
            call(sandbox_usr, cmdline_usr, 2.5, 123 * 1024 * 1024,
                 dirs_map={os.path.join(self.base_dir, "0"): ("/fifo0", "rw")},
                 stdin_redirect=None,
                 stdout_redirect=None,
                 multiprocess=True),
        ], any_order=True)
        self.assertEqual(self.evaluation_step_before_run.call_count, 2)
        self.assertEqual(self.evaluation_step_after_run.call_count, 2)
        # Results put in job and sandbox deleted.
        self.assertResultsInJob(job, True, str(OUTCOME), TEXT, STATS_OK)
        sandbox_mgr.cleanup.assert_called_once_with(delete=True)
        sandbox_usr.cleanup.assert_called_once_with(delete=True)

    @patch.object(config, "trusted_sandbox_max_time_s", 1)
    def test_single_process_success_long_time_limit(self):
        # If the time limit is longer than trusted step default time limit,
        # the manager run should use the task time limit.
        tt, job = self.prepare(
            [1, "stub", "fifo_io"],
            {"foo": EXE_FOO}, {"manager": MANAGER})
        sandbox_mgr = self.expect_sandbox()
        self.expect_sandbox()

        tt.evaluate(job, self.file_cacher)

        self.evaluation_step_before_run.assert_has_calls([
            call(sandbox_mgr, ANY, 2.5 + 1, ANY, dirs_map=ANY,
                 writable_files=ANY, stdin_redirect=ANY, multiprocess=ANY)])

    def test_single_process_missing_manager(self):
        # Manager is missing, should terminate without creating sandboxes.
        tt, job = self.prepare(
            [1, "stub", "fifo_io"], {"foo": EXE_FOO}, {})

        tt.evaluate(job, self.file_cacher)

        self.assertResultsInJob(job, False, None, None, None)

    def test_single_process_zero_executables(self):
        # For some reason, no user executables. Should terminate without
        # creating sandboxes.
        tt, job = self.prepare(
            [1, "stub", "fifo_io"], {}, {"manager": MANAGER})

        tt.evaluate(job, self.file_cacher)

        self.assertResultsInJob(job, False, None, None, None)

    def test_single_process_many_executables(self):
        # For some reason, two user executables. Should terminate without
        # creating sandboxes.
        tt, job = self.prepare(
            [1, "stub", "fifo_io"],
            {"foo": EXE_FOO, "bar": EXE_FOO}, {"manager": MANAGER})

        tt.evaluate(job, self.file_cacher)

        self.assertResultsInJob(job, False, None, None, None)

    def test_single_process_manager_failure(self):
        # Manager had problems, it's not the user's fault.
        tt, job = self.prepare(
            [1, "stub", "fifo_io"],
            {"foo": EXE_FOO}, {"manager": MANAGER})
        sandbox_mgr = self.expect_sandbox()
        sandbox_usr = self.expect_sandbox()
        self._set_evaluation_step_return_values({
            sandbox_mgr: (True, False, STATS_RE),
            sandbox_usr: (True, True, STATS_OK),
        })

        tt.evaluate(job, self.file_cacher)

        self.assertResultsInJob(job, False, None, None, None)
        sandbox_mgr.cleanup.assert_called_once_with(delete=False)
        sandbox_usr.cleanup.assert_called_once_with(delete=False)

    def test_single_process_manager_sandbox_failure(self):
        # Manager sandbox had problems, it's not the user's fault.
        tt, job = self.prepare(
            [1, "stub", "fifo_io"],
            {"foo": EXE_FOO}, {"manager": MANAGER})
        sandbox_mgr = self.expect_sandbox()
        sandbox_usr = self.expect_sandbox()
        self._set_evaluation_step_return_values({
            sandbox_mgr: (False, None, None),
            sandbox_usr: (True, True, STATS_OK),
        })

        tt.evaluate(job, self.file_cacher)

        self.assertResultsInJob(job, False, None, None, None)
        sandbox_mgr.cleanup.assert_called_once_with(delete=False)
        sandbox_usr.cleanup.assert_called_once_with(delete=False)

    def test_single_process_manager_and_user_failure(self):
        # Manager had problems, it's not the user's fault even if also their
        # submission had problems.
        tt, job = self.prepare(
            [1, "stub", "fifo_io"],
            {"foo": EXE_FOO}, {"manager": MANAGER})
        sandbox_mgr = self.expect_sandbox()
        sandbox_usr = self.expect_sandbox()
        self._set_evaluation_step_return_values({
            sandbox_mgr: (True, False, STATS_RE),
            sandbox_usr: (True, False, STATS_RE),
        })

        tt.evaluate(job, self.file_cacher)

        self.assertResultsInJob(job, False, None, None, None)
        sandbox_mgr.cleanup.assert_called_once_with(delete=False)
        sandbox_usr.cleanup.assert_called_once_with(delete=False)

    def test_single_process_user_sandbox_failure(self):
        # User sandbox had problems, it's not the user's fault.
        tt, job = self.prepare(
            [1, "stub", "fifo_io"],
            {"foo": EXE_FOO}, {"manager": MANAGER})
        sandbox_mgr = self.expect_sandbox()
        sandbox_usr = self.expect_sandbox()
        self._set_evaluation_step_return_values({
            sandbox_mgr: (True, True, STATS_OK),
            sandbox_usr: (False, None, None),
        })

        tt.evaluate(job, self.file_cacher)

        self.assertResultsInJob(job, False, None, None, None)
        sandbox_mgr.cleanup.assert_called_once_with(delete=False)
        sandbox_usr.cleanup.assert_called_once_with(delete=False)

    def test_single_process_user_failure(self):
        # User program had problems, it's the user's fault.
        tt, job = self.prepare(
            [1, "stub", "fifo_io"],
            {"foo": EXE_FOO}, {"manager": MANAGER})
        sandbox_mgr = self.expect_sandbox()
        sandbox_usr = self.expect_sandbox()
        self._set_evaluation_step_return_values({
            sandbox_mgr: (True, True, STATS_OK),
            sandbox_usr: (True, False, STATS_RE),
        })

        tt.evaluate(job, self.file_cacher)

        self.assertResultsInJob(
            job, True, str(0.0), self.human_evaluation_message.return_value,
            STATS_RE)
        sandbox_mgr.cleanup.assert_called_once_with(delete=True)
        sandbox_usr.cleanup.assert_called_once_with(delete=True)

    def test_single_process_get_output_success(self):
        tt, job = self.prepare(
            [1, "stub", "fifo_io"],
            {"foo": EXE_FOO}, {"manager": MANAGER})
        job.get_output = True
        sandbox_mgr = self.expect_sandbox()
        self.expect_sandbox()
        sandbox_mgr.get_file_to_storage.return_value = "digest of output.txt"

        tt.evaluate(job, self.file_cacher)

        # With get_output, submission is run, output is eval'd, and in addition
        # we store (a truncation of) the user output.
        sandbox_mgr.get_file_to_storage.assert_called_once_with(
            "output.txt", ANY, trunc_len=ANY)
        self.assertEqual(job.user_output, "digest of output.txt")
        self.evaluation_step_after_run.assert_called()
        self.extract_outcome_and_text.assert_called_once()
        self.assertEqual(job.success, True)

    def test_single_process_only_execution_success(self):
        tt, job = self.prepare(
            [1, "stub", "fifo_io"],
            {"foo": EXE_FOO}, {"manager": MANAGER})
        job.only_execution = True
        self.expect_sandbox()
        self.expect_sandbox()

        tt.evaluate(job, self.file_cacher)

        # We run the submission but don't evaluate the output.
        self.evaluation_step_after_run.assert_called()
        self.extract_outcome_and_text.assert_not_called()
        self.assertEqual(job.success, True)

    def test_single_process_std_io(self):
        tt, job = self.prepare(
            [1, "stub", "std_io"], {"foo": EXE_FOO}, {"manager": MANAGER})
        self.expect_sandbox()
        sandbox_usr = self.expect_sandbox()

        tt.evaluate(job, self.file_cacher)

        # Evaluation step called with the right arguments, in particular
        # redirects and no command line arguments.
        cmdline_usr = ["run1", "foo", "stub"]
        self.evaluation_step_before_run.assert_has_calls([
            call(sandbox_usr, cmdline_usr, ANY, ANY, dirs_map=ANY,
                 stdin_redirect="/fifo0/m_to_u0",
                 stdout_redirect="/fifo0/u0_to_m",
                 multiprocess=ANY)])

    @patch.object(config, "trusted_sandbox_max_time_s", 4321)
    @patch.object(config, "trusted_sandbox_max_memory_kib", 1234 * 1024)
    def test_many_processes_success(self):
        tt, job = self.prepare(
            [2, "stub", "fifo_io"],
            {"foo": EXE_FOO}, {"manager": MANAGER})
        sandbox_mgr = self.expect_sandbox()
        sandbox_usr0 = self.expect_sandbox()
        sandbox_usr1 = self.expect_sandbox()

        tt.evaluate(job, self.file_cacher)

        # Sandboxes created with the correct file cacher and names.
        self.Sandbox.assert_has_calls([
            call(self.file_cacher, name="manager_evaluate"),
            call(self.file_cacher, name="user_evaluate"),
            call(self.file_cacher, name="user_evaluate"),
        ], any_order=False)
        self.assertEqual(self.Sandbox.call_count, 3)
        # We need input (with the default filename for redirection) and
        # executable copied in the sandbox.
        sandbox_mgr.create_file_from_storage.assert_has_calls([
            call("manager", "digest of manager", executable=True),
            call("input.txt", "digest of input"),
        ], any_order=True)
        self.assertEqual(sandbox_mgr.create_file_from_storage.call_count, 2)
        # Same content in both user sandboxes.
        for s in [sandbox_usr0, sandbox_usr1]:
            s.create_file_from_storage.assert_has_calls([
                call("foo", "digest of foo", executable=True),
            ], any_order=True)
            self.assertEqual(s.create_file_from_storage.call_count, 1)
        # Evaluation step called with the right arguments, in particular
        # redirects, and no (other) writable files. For the user's command,
        # see fake_evaluation_commands in the mixin.
        cmdline_mgr = ["./manager",
                       "/fifo0/u0_to_m", "/fifo0/m_to_u0",
                       "/fifo1/u1_to_m", "/fifo1/m_to_u1"]
        cmdline_usr0 = ["run1", "foo", "stub",
                        "/fifo0/m_to_u0", "/fifo0/u0_to_m", "0"]
        cmdline_usr1 = ["run1", "foo", "stub",
                        "/fifo1/m_to_u1", "/fifo1/u1_to_m", "1"]
        self.evaluation_step_before_run.assert_has_calls([
            call(sandbox_mgr, cmdline_mgr, 4321, 1234 * 1024 * 1024,
                 dirs_map={
                     os.path.join(self.base_dir, "0"): ("/fifo0", "rw"),
                     os.path.join(self.base_dir, "1"): ("/fifo1", "rw"),
                 },
                 writable_files=["output.txt"],
                 stdin_redirect="input.txt", multiprocess=True),
            call(sandbox_usr0, cmdline_usr0, 2.5, 123 * 1024 * 1024,
                 dirs_map={os.path.join(self.base_dir, "0"): ("/fifo0", "rw")},
                 stdin_redirect=None,
                 stdout_redirect=None,
                 multiprocess=True),
            call(sandbox_usr1, cmdline_usr1, 2.5, 123 * 1024 * 1024,
                 dirs_map={os.path.join(self.base_dir, "1"): ("/fifo1", "rw")},
                 stdin_redirect=None,
                 stdout_redirect=None,
                 multiprocess=True),
        ], any_order=True)
        self.assertEqual(self.evaluation_step_before_run.call_count, 3)
        self.assertEqual(self.evaluation_step_after_run.call_count, 3)
        # Results put in job and sandbox deleted.
        self.assertResultsInJob(job, True, str(OUTCOME), TEXT,
                                merge_execution_stats(STATS_OK, STATS_OK))
        sandbox_mgr.cleanup.assert_called_once_with(delete=True)
        sandbox_usr0.cleanup.assert_called_once_with(delete=True)
        sandbox_usr1.cleanup.assert_called_once_with(delete=True)

    @patch.object(config, "trusted_sandbox_max_time_s", 3)
    def test_many_processes_success_long_time_limit(self):
        # If the time limit is longer than trusted step default time limit,
        # the manager run should use the task time limit.
        tt, job = self.prepare(
            [2, "stub", "fifo_io"],
            {"foo": EXE_FOO}, {"manager": MANAGER})
        sandbox_mgr = self.expect_sandbox()
        self.expect_sandbox()
        self.expect_sandbox()

        tt.evaluate(job, self.file_cacher)

        self.evaluation_step_before_run.assert_has_calls([
            call(sandbox_mgr, ANY, 2 * (2.5 + 1), ANY, dirs_map=ANY,
                 writable_files=ANY, stdin_redirect=ANY, multiprocess=ANY)])

    def test_many_processes_first_user_failure(self):
        # One of the user programs had problems, it's the user's fault.
        tt, job = self.prepare(
            [2, "stub", "fifo_io"],
            {"foo": EXE_FOO}, {"manager": MANAGER})
        sandbox_mgr = self.expect_sandbox()
        sandbox_usr0 = self.expect_sandbox()
        sandbox_usr1 = self.expect_sandbox()
        self._set_evaluation_step_return_values({
            sandbox_mgr: (True, True, STATS_OK),
            sandbox_usr0: (True, False, STATS_RE),
            sandbox_usr1: (True, True, STATS_OK),
        })

        tt.evaluate(job, self.file_cacher)

        self.assertResultsInJob(
            job, True, str(0.0), self.human_evaluation_message.return_value,
            merge_execution_stats(STATS_RE, STATS_OK))
        sandbox_mgr.cleanup.assert_called_once_with(delete=True)
        sandbox_usr0.cleanup.assert_called_once_with(delete=True)
        sandbox_usr1.cleanup.assert_called_once_with(delete=True)

    def test_many_processes_last_user_failure(self):
        # One of the user programs had problems, it's the user's fault.
        tt, job = self.prepare(
            [2, "stub", "fifo_io"],
            {"foo": EXE_FOO}, {"manager": MANAGER})
        sandbox_mgr = self.expect_sandbox()
        sandbox_usr0 = self.expect_sandbox()
        sandbox_usr1 = self.expect_sandbox()
        self._set_evaluation_step_return_values({
            sandbox_mgr: (True, True, STATS_OK),
            sandbox_usr0: (True, True, STATS_OK),
            sandbox_usr1: (True, False, STATS_RE),
        })

        tt.evaluate(job, self.file_cacher)

        self.assertResultsInJob(
            job, True, str(0.0), self.human_evaluation_message.return_value,
            merge_execution_stats(STATS_OK, STATS_RE))
        sandbox_mgr.cleanup.assert_called_once_with(delete=True)
        sandbox_usr0.cleanup.assert_called_once_with(delete=True)
        sandbox_usr1.cleanup.assert_called_once_with(delete=True)

    def test_many_processes_merged_timeout(self):
        # Solution was ok, but considering all runtimes, it hit timeout.
        tt, job = self.prepare(
            [2, "stub", "fifo_io"],
            {"foo": EXE_FOO}, {"manager": MANAGER})
        job.time_limit = 2.5
        stats0 = dict(STATS_OK)
        stats0["execution_time"] = 1.0
        stats1 = dict(STATS_OK)
        stats1["execution_time"] = 2.0
        sandbox_mgr = self.expect_sandbox()
        sandbox_usr0 = self.expect_sandbox()
        sandbox_usr1 = self.expect_sandbox()
        self._set_evaluation_step_return_values({
            sandbox_mgr: (True, True, STATS_OK),
            sandbox_usr0: (True, True, stats0),
            sandbox_usr1: (True, True, stats1),
        })

        tt.evaluate(job, self.file_cacher)

        # The stats are the merge of the two, but the status is changed to
        # timeout since the sum of the cpu times is over the time limit.
        stats = merge_execution_stats(stats0, stats1)
        stats["exit_status"] = "timeout"
        self.assertResultsInJob(
            job, True, str(0.0), self.human_evaluation_message.return_value,
            stats)
        sandbox_mgr.cleanup.assert_called_once_with(delete=True)
        sandbox_usr0.cleanup.assert_called_once_with(delete=True)
        sandbox_usr1.cleanup.assert_called_once_with(delete=True)

    def test_many_processes_std_io(self):
        tt, job = self.prepare(
            [2, "stub", "std_io"], {"foo": EXE_FOO}, {"manager": MANAGER})
        self.expect_sandbox()
        sandbox_usr0 = self.expect_sandbox()
        sandbox_usr1 = self.expect_sandbox()

        tt.evaluate(job, self.file_cacher)

        # Evaluation step called with the right arguments, in particular
        # redirects and only the process index as command line argument.
        cmdline_usr0 = ["run1", "foo", "stub", "0"]
        cmdline_usr1 = ["run1", "foo", "stub", "1"]
        self.evaluation_step_before_run.assert_has_calls([
            call(sandbox_usr0, cmdline_usr0, ANY, ANY, dirs_map=ANY,
                 stdin_redirect="/fifo0/m_to_u0",
                 stdout_redirect="/fifo0/u0_to_m",
                 multiprocess=ANY),
            call(sandbox_usr1, cmdline_usr1, ANY, ANY, dirs_map=ANY,
                 stdin_redirect="/fifo1/m_to_u1",
                 stdout_redirect="/fifo1/u1_to_m",
                 multiprocess=ANY)
        ], any_order=True)


if __name__ == "__main__":
    unittest.main()
