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

"""Tests for the Batch task type."""

import unittest
from unittest.mock import MagicMock, call, ANY

from cms.db import File, Manager, Executable
from cms.grading.Job import CompilationJob, EvaluationJob
from cms.grading.tasktypes.Batch import Batch
from cmstestsuite.unit_tests.grading.tasktypes.tasktypetestutils import \
    COMPILATION_COMMAND_1, COMPILATION_COMMAND_2, EVALUATION_COMMAND_1, \
    LANG_1, LANG_2, OUTCOME, STATS_OK, STATS_RE, TEXT, \
    TaskTypeTestMixin, fake_compilation_commands, fake_evaluation_commands


FILE_FOO_L1 = File(digest="digest of foo.l1", filename="foo.%l")
FILE_BAR_L1 = File(digest="digest of bar.l1", filename="bar.%l")
GRADER_L1 = Manager(digest="digest of grader.l1", filename="grader.l1")
GRADER_L2 = Manager(digest="digest of grader.l2", filename="grader.l2")
HEADER_L1 = Manager(digest="digest of grader.hl1", filename="graderl.hl1")
EXE_FOO = Executable(digest="digest of foo", filename="foo")


class TestGetCompilationCommands(TaskTypeTestMixin, unittest.TestCase):
    """Tests for get_compilation_commands()."""

    def setUp(self):
        super().setUp()
        self.setUpMocks("Batch")
        self.languages.update({LANG_1, LANG_2})

    def test_alone(self):
        tt = Batch(["alone", ["", ""], "diff"])
        cc = tt.get_compilation_commands(["foo.%l"])
        self.assertEqual(cc, {
            "L1": fake_compilation_commands(
                COMPILATION_COMMAND_1, ["foo.l1"], "foo"),
            "L2": fake_compilation_commands(
                COMPILATION_COMMAND_2, ["foo.l2"], "foo.ext"),
        })

    def test_grader(self):
        tt = Batch(["grader", ["", ""], "diff"])
        cc = tt.get_compilation_commands(["foo.%l"])
        self.assertEqual(cc, {
            "L1": fake_compilation_commands(
                COMPILATION_COMMAND_1, ["foo.l1", "grader.l1"], "foo"),
            "L2": fake_compilation_commands(
                COMPILATION_COMMAND_2, ["foo.l2", "grader.l2"], "foo.ext"),
        })

    def test_alone_two_files(self):
        tt = Batch(["alone", ["", ""], "diff"])
        cc = tt.get_compilation_commands(["foo.%l", "bar.%l"])
        self.assertEqual(cc, {
            "L1": fake_compilation_commands(
                COMPILATION_COMMAND_1, ["foo.l1", "bar.l1"], "bar_foo"),
            "L2": fake_compilation_commands(
                COMPILATION_COMMAND_2, ["foo.l2", "bar.l2"], "bar_foo.ext"),
        })

    def test_grader_two_files(self):
        tt = Batch(["grader", ["", ""], "diff"])
        cc = tt.get_compilation_commands(["foo.%l", "bar.%l"])
        self.assertEqual(cc, {
            "L1": fake_compilation_commands(
                COMPILATION_COMMAND_1,
                ["foo.l1", "bar.l1", "grader.l1"],
                "bar_foo"),
            "L2": fake_compilation_commands(
                COMPILATION_COMMAND_2,
                ["foo.l2", "bar.l2", "grader.l2"],
                "bar_foo.ext"),
        })


class TestCompile(TaskTypeTestMixin, unittest.TestCase):
    """Tests for compile().

    prepare() creates a task type and a job with the given arguments, including
    the return value of compilation_step(), which is by default a success.

    compile() depends only on the first parameter (grader or alone). We test
    failure modes only for alone, apart from one grader-specific failure.

    """

    def setUp(self):
        super().setUp()
        self.setUpMocks("Batch")
        self.languages.update({LANG_1})
        self.file_cacher = MagicMock()

    @staticmethod
    def job(files=None, managers=None):
        files = files if files is not None else {}
        managers = managers if managers is not None else {}
        return CompilationJob(language="L1", files=files, managers=managers)

    def prepare(self, parameters, files=None, managers=None,
                compilation_step_return_value=(True, True, TEXT, STATS_OK)):
        tt = Batch(parameters)
        job = self.job(files, managers)
        if compilation_step_return_value is not None:
            self.compilation_step.return_value = compilation_step_return_value
        return tt, job

    def assertResultsInJob(self, job):
        # Results in the job should be those returned by compilation_step. If
        # compilation_step was not called, there is an error in CMS/sandbox
        # and success is necessary False.
        if self.compilation_step.called:
            success, compilation_success, text, plus = \
                self.compilation_step.return_value
        else:
            success, compilation_success, text, plus = False, None, None, None
        self.assertEqual(job.success, success)
        self.assertEqual(job.compilation_success, compilation_success)
        self.assertEqual(job.text, text)
        self.assertEqual(job.plus, plus)

    def test_alone_success(self):
        tt, job = self.prepare(["alone", ["", ""], "diff"],
                               {"foo.%l": FILE_FOO_L1})
        sandbox = self.expect_sandbox()
        sandbox.get_file_to_storage.return_value = "exe_digest"

        tt.compile(job, self.file_cacher)

        # Sandbox created with the correct file cacher and name.
        self.Sandbox.assert_called_once_with(self.file_cacher, name="compile")
        # For alone, we only need the user source file.
        sandbox.create_file_from_storage.assert_has_calls(
            [call("foo.l1", "digest of foo.l1")], any_order=True)
        self.assertEqual(sandbox.create_file_from_storage.call_count, 1)
        # Compilation step called correctly.
        self.compilation_step.assert_called_once_with(
            sandbox, fake_compilation_commands(
                COMPILATION_COMMAND_1, ["foo.l1"], "foo"))
        # Results put in job, executable stored and sandbox deleted.
        self.assertResultsInJob(job)
        sandbox.get_file_to_storage.assert_called_once_with("foo", ANY)
        sandbox.cleanup.assert_called_once_with(delete=True)

    def test_alone_failure_missing_file(self):
        # For some reason the user submission is missing. This should not
        # happen and is the admin's (or CMS') fault. No sandbox should be
        # created. We test this with alone, but would be the same for grader.
        tt, job = self.prepare(["alone", ["", ""], "diff"], {})

        tt.compile(job, self.file_cacher)

        self.compilation_step.assert_not_called()
        self.assertResultsInJob(job)

    def test_alone_success_two_files(self):
        # Same as for a missing file.
        tt, job = self.prepare(["alone", ["", ""], "diff"],
                               {"foo.%l": FILE_FOO_L1, "bar.%l": FILE_BAR_L1})
        sandbox = self.expect_sandbox()
        sandbox.get_file_to_storage.return_value = "exe_digest"

        tt.compile(job, self.file_cacher)

        # Sandbox created with the correct file cacher and name.
        self.Sandbox.assert_called_once_with(self.file_cacher, name="compile")
        # For alone, we only need the user source file.
        sandbox.create_file_from_storage.assert_has_calls(
            [call("foo.l1", "digest of foo.l1"),
             call("bar.l1", "digest of bar.l1")], any_order=True)
        self.assertEqual(sandbox.create_file_from_storage.call_count, 2)
        # Compilation step called correctly.
        self.compilation_step.assert_called_once_with(
            sandbox, fake_compilation_commands(
                COMPILATION_COMMAND_1, ["foo.l1", "bar.l1"], "bar_foo"))
        # Results put in job, executable stored and sandbox deleted.
        self.assertResultsInJob(job)
        sandbox.get_file_to_storage.assert_called_once_with("bar_foo", ANY)
        sandbox.cleanup.assert_called_once_with(delete=True)

    def test_alone_compilation_failure(self):
        # Compilation failure, but sandbox succeeded. It's the user's fault.
        tt, job = self.prepare(
            ["alone", ["", ""], "diff"],
            {"foo.%l": FILE_FOO_L1},
            compilation_step_return_value=(True, False, TEXT, STATS_OK))
        sandbox = self.expect_sandbox()

        tt.compile(job, self.file_cacher)

        # If the compilation failed, we want to return the reason to the user.
        self.assertResultsInJob(job)
        # But no executable stored.
        sandbox.get_file_to_storage.assert_not_called()
        # Still, we delete the sandbox, since it's not an error.
        sandbox.cleanup.assert_called_once_with(delete=True)

    def test_alone_sandbox_failure(self):
        # Sandbox (or CMS) failure. It's the admins' fault.
        tt, job = self.prepare(
            ["alone", ["", ""], "diff"],
            {"foo.%l": FILE_FOO_L1},
            compilation_step_return_value=(False, None, None, None))
        sandbox = self.expect_sandbox()

        tt.compile(job, self.file_cacher)

        self.assertResultsInJob(job)
        sandbox.get_file_to_storage.assert_not_called()
        # We preserve the sandbox to let admins check the problem.
        sandbox.cleanup.assert_called_once_with(delete=False)

    def test_grader_success(self):
        # We sprinkle in also a header, that should be copied, but not the
        # other grader.
        tt, job = self.prepare(["grader", ["", ""], "diff"],
                               files={"foo.%l": FILE_FOO_L1},
                               managers={"grader.l1": GRADER_L1,
                                         "grader.l2": GRADER_L2,
                                         "grader.hl1": HEADER_L1})
        sandbox = self.expect_sandbox()
        sandbox.get_file_to_storage.return_value = "exe_digest"

        tt.compile(job, self.file_cacher)

        # Sandbox created with the correct file cacher and name.
        self.Sandbox.assert_called_once_with(self.file_cacher, name="compile")
        # For grader we need the user source, the grader, and any other
        # relevant manager (in this case, the header).
        sandbox.create_file_from_storage.assert_has_calls([
            call("foo.l1", "digest of foo.l1"),
            call("grader.l1", "digest of grader.l1"),
            call("grader.hl1", "digest of grader.hl1"),
        ], any_order=True)
        self.assertEqual(sandbox.create_file_from_storage.call_count, 3)
        # Compilation step called correctly.
        self.compilation_step.assert_called_once_with(
            sandbox, fake_compilation_commands(
                COMPILATION_COMMAND_1, ["foo.l1", "grader.l1"], "foo"))
        # Results put in job, executable stored and sandbox deleted.
        self.assertResultsInJob(job)
        sandbox.get_file_to_storage.assert_called_once_with("foo", ANY)
        sandbox.cleanup.assert_called_once_with(delete=True)

    def test_grader_failure_missing_grader(self):
        # Grader is missing from the managers, this is a configuration error.
        # No sandbox should be created.
        tt, job = self.prepare(["grader", ["", ""], "diff"],
                               files={"foo.%l": FILE_FOO_L1},
                               managers={"grader.l2": GRADER_L2})

        tt.compile(job, self.file_cacher)

        self.compilation_step.assert_not_called()
        self.assertResultsInJob(job)


class TestEvaluate(TaskTypeTestMixin, unittest.TestCase):
    """Tests for evaluate().

    prepare() creates a task type and a job with the given arguments, and in
    addition set up successful return values for the two steps
    (evaluation_step and eval_output).

    evaluate() depends on 2 parameters (I/O and checker/whitediff); we test
    success for all combinations, but failures and special cases only for one
    of the four.

    """

    def setUp(self):
        super().setUp()
        self.setUpMocks("Batch")
        self.languages.update({LANG_1})
        self.file_cacher = MagicMock()

    @staticmethod
    def job(executables):
        return EvaluationJob(language="L1",
                             input="digest of input",
                             output="digest of correct output",
                             time_limit=2.5,
                             memory_limit=123 * 1024 * 1024,
                             executables=executables,
                             multithreaded_sandbox=True)

    def prepare(self, parameters, executables):
        tt = Batch(parameters)
        job = self.job(executables)
        self.evaluation_step.return_value = (True, True, STATS_OK)
        self.eval_output.return_value = (True, OUTCOME, TEXT)
        return tt, job

    def assertResultsInJob(self, job):
        # Results in the job should be those returned by eval_output, plus the
        # stats returned by evaluation_step. This unless the evaluation was
        # not called (due to prior error) or returned an error (for the
        # sandbox or the user submissions).
        if not self.evaluation_step.called \
                or not self.evaluation_step.return_value[0]:
            # evaluation_step not called or its sandbox gave an error.
            success, outcome, text, stats = False, None, None, None
        elif not self.evaluation_step.return_value[1]:
            # User submission terminated incorrectly.
            success, _, stats = self.evaluation_step.return_value
            outcome = str(0.0)
            text = self.human_evaluation_message.return_value
        else:
            # User submission terminated correctly, output is evaluated.
            _, _, stats = self.evaluation_step.return_value
            success, outcome, text = self.eval_output.return_value
            if isinstance(outcome, float):
                outcome = str(outcome)

        self.assertEqual(job.success, success)
        self.assertEqual(job.outcome, outcome)
        self.assertEqual(job.text, text)
        self.assertEqual(job.plus, stats)

    def test_stdio_diff_success(self):
        tt, job = self.prepare(["alone", ["", ""], "diff"], {"foo": EXE_FOO})
        sandbox = self.expect_sandbox()

        tt.evaluate(job, self.file_cacher)

        # Sandbox created with the correct file cacher and name.
        self.Sandbox.assert_called_once_with(self.file_cacher, name="evaluate")
        # We need input (with the default filename for redirection) and
        # executable copied in the sandbox.
        sandbox.create_file_from_storage.assert_has_calls([
            call("foo", "digest of foo", executable=True),
            call("input.txt", "digest of input"),
        ], any_order=True)
        self.assertEqual(sandbox.create_file_from_storage.call_count, 2)
        # Evaluation step called with the right arguments, in particular
        # redirects, and no (other) writable files.
        self.evaluation_step.assert_called_once_with(
            sandbox,
            fake_evaluation_commands(EVALUATION_COMMAND_1, "foo", "foo"),
            2.5, 123 * 1024 * 1024,
            writable_files=[],
            stdin_redirect="input.txt",
            stdout_redirect="output.txt",
            multiprocess=True)
        # Check eval_output was called correctly.
        self.eval_output.assert_called_once_with(
            self.file_cacher, job, None,
            user_output_path="/path/0/output.txt", user_output_filename="")
        # Results put in job and sandbox deleted.
        self.assertResultsInJob(job)
        sandbox.cleanup.assert_called_once_with(delete=True)

    def test_stdio_diff_failure_missing_file(self):
        # For some reason the executable is missing. This should not happen
        # and is the admin's (or CMS') fault. No sandbox should be created.
        tt, job = self.prepare(["alone", ["", ""], "diff"], {})

        tt.evaluate(job, self.file_cacher)

        self.evaluation_step.assert_not_called()
        self.eval_output.assert_not_called()
        self.assertResultsInJob(job)

    def test_stdio_diff_failure_two_files(self):
        # Same as for a missing file.
        tt, job = self.prepare(["alone", ["", ""], "diff"],
                               {"foo": EXE_FOO, "foo2": EXE_FOO})

        tt.evaluate(job, self.file_cacher)

        self.evaluation_step.assert_not_called()
        self.eval_output.assert_not_called()
        self.assertResultsInJob(job)

    def test_stdio_diff_evaluation_step_submission_failure_(self):
        tt, job = self.prepare(["alone", ["", ""], "diff"], {"foo": EXE_FOO})
        self.evaluation_step.return_value = (True, False, STATS_RE)
        sandbox = self.expect_sandbox()

        tt.evaluate(job, self.file_cacher)

        self.assertResultsInJob(job)
        # eval_output should not have been called, but the since it didn't
        # have any error, the sandbox should be deleted.
        self.eval_output.assert_not_called()
        sandbox.cleanup.assert_called_once_with(delete=True)

    def test_stdio_diff_evaluation_step_sandbox_failure_(self):
        tt, job = self.prepare(["alone", ["", ""], "diff"], {"foo": EXE_FOO})
        self.evaluation_step.return_value = (False, None, None)
        sandbox = self.expect_sandbox()

        tt.evaluate(job, self.file_cacher)

        self.assertResultsInJob(job)
        # eval_output should not have been called, and the sandbox not deleted.
        self.eval_output.assert_not_called()
        sandbox.cleanup.assert_called_once_with(delete=False)

    def test_stdio_diff_eval_output_failure_(self):
        tt, job = self.prepare(["alone", ["", ""], "diff"], {"foo": EXE_FOO})
        self.eval_output.return_value = (False, None, None)
        sandbox = self.expect_sandbox()

        tt.evaluate(job, self.file_cacher)

        self.assertResultsInJob(job)
        # Even if the error is in the eval_output sandbox, we keep also the one
        # for evaluation_step to allow debugging.
        sandbox.cleanup.assert_called_once_with(delete=False)

    def test_stdio_diff_get_output_success(self):
        tt, job = self.prepare(["alone", ["", ""], "diff"], {"foo": EXE_FOO})
        job.get_output = True
        sandbox = self.expect_sandbox()
        sandbox.get_file_to_storage.return_value = "digest of output.txt"

        tt.evaluate(job, self.file_cacher)

        # With get_output, submission is run, output is eval'd, and in addition
        # we store (a truncation of) the user output.
        sandbox.get_file_to_storage.assert_called_once_with(
            "output.txt", ANY, trunc_len=ANY)
        self.assertEqual(job.user_output, "digest of output.txt")
        self.evaluation_step.assert_called_once()
        self.eval_output.assert_called_once()

    def test_stdio_diff_only_execution_success(self):
        tt, job = self.prepare(["alone", ["", ""], "diff"], {"foo": EXE_FOO})
        job.only_execution = True
        self.expect_sandbox()

        tt.evaluate(job, self.file_cacher)

        # We run the submission but don't evaluate the output.
        self.evaluation_step.assert_called_once()
        self.eval_output.assert_not_called()
        self.assertEqual(job.success, True)

    def test_fileio_diff_success(self):
        tt, job = self.prepare(["alone", ["myin", "myout"], "diff"],
                               {"foo": EXE_FOO})
        sandbox = self.expect_sandbox()

        tt.evaluate(job, self.file_cacher)

        # Sandbox created with the correct file cacher and name.
        self.Sandbox.assert_called_once_with(self.file_cacher, name="evaluate")
        # We need input (with the filename specified in the parameters) and
        # executable copied in the sandbox.
        sandbox.create_file_from_storage.assert_has_calls([
            call("foo", "digest of foo", executable=True),
            call("myin", "digest of input"),
        ], any_order=True)
        self.assertEqual(sandbox.create_file_from_storage.call_count, 2)
        # Evaluation step called with the right arguments, in particular
        # the specified output is writable.
        self.evaluation_step.assert_called_once_with(
            sandbox,
            fake_evaluation_commands(EVALUATION_COMMAND_1, "foo", "foo"),
            2.5, 123 * 1024 * 1024,
            writable_files=["myout"],
            stdin_redirect=None,
            stdout_redirect=None,
            multiprocess=True)
        # Check eval_output was called correctly.
        self.eval_output.assert_called_once_with(
            self.file_cacher, job, None, user_output_path="/path/0/myout",
            user_output_filename="myout")
        # Results put in job and sandbox deleted.
        self.assertResultsInJob(job)
        sandbox.cleanup.assert_called_once_with(delete=True)

    def test_stdio_checker_success(self):
        tt, job = self.prepare(["alone", ["", ""], "comparator"],
                               {"foo": EXE_FOO})
        sandbox = self.expect_sandbox()

        tt.evaluate(job, self.file_cacher)

        # We only perform checks for the final eval step (checker).
        self.eval_output.assert_called_once_with(
            self.file_cacher, job, "checker",
            user_output_path="/path/0/output.txt", user_output_filename="")
        # Results put in job and sandbox deleted.
        self.assertResultsInJob(job)
        sandbox.cleanup.assert_called_once_with(delete=True)

    def test_fileio_checker_success(self):
        tt, job = self.prepare(["alone", ["myin", "myout"], "comparator"],
                               {"foo": EXE_FOO})
        sandbox = self.expect_sandbox()

        tt.evaluate(job, self.file_cacher)

        # We only perform checks for the final eval step (checker).
        self.eval_output.assert_called_once_with(
            self.file_cacher, job, "checker",
            user_output_path="/path/0/myout",
            user_output_filename="myout")
        # Results put in job and sandbox deleted.
        self.assertResultsInJob(job)
        sandbox.cleanup.assert_called_once_with(delete=True)


if __name__ == "__main__":
    unittest.main()
