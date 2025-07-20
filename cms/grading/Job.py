#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2013-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2013-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""A Job is an abstraction of an "atomic" action of a Worker.

Jobs play a major role in the interface with TaskTypes: they are a
data structure containing all information about what the TaskTypes
should do. They are mostly used in the communication between ES and
the Workers, hence they contain only serializable data (for example,
the name of the task type, not the task type object itself).

A Job represents an indivisible action of a Worker, for example
"compile the submission" or "evaluate the submission on a certain
testcase".

"""

import logging
from typing import Self

from cms.db import (
    Dataset,
    Evaluation,
    Executable,
    File,
    Manager,
    Submission,
    UserTest,
    UserTestExecutable,
    Contest,
    SubmissionResult,
    UserTestResult,
)
from cms.grading.languagemanager import get_language
from cms.service.esoperations import ESOperation


logger = logging.getLogger(__name__)


def _is_contest_multithreaded(contest: Contest) -> bool:
    """Return if the contest allows multithreaded compilations and evaluations

    The rule is that this is allowed when the contest has a language that
    requires this.

    contest: the contest to check
    return: True if the sandbox should allow multithreading.

    """
    return any(get_language(l).requires_multithreading
               for l in contest.languages)


class Job:
    """Base class for all jobs.

    Input data (usually filled by ES): task_type,
    task_type_parameters. Metadata: shard, sandboxes, info.

    """

    def __init__(
        self,
        operation: ESOperation | None = None,
        task_type: str | None = None,
        task_type_parameters: object = None,
        language: str | None = None,
        multithreaded_sandbox: bool = False,
        archive_sandbox: bool = False,
        shard: int | None = None,
        keep_sandbox: bool = False,
        sandboxes: list[str] | None = None,
        sandbox_digests: dict[str, str] | None = None,
        info: str | None = None,
        success: bool | None = None,
        text: list[str] | None = None,
        files: dict[str, File] | None = None,
        managers: dict[str, Manager] | None = None,
        executables: dict[str, Executable] | None = None,
    ):
        """Initialization.

        operation: the operation.
        task_type: the name of the task type.
        task_type_parameters: the parameters for the
            creation of the correct task type.
        language: the language of the submission / user test.
        multithreaded_sandbox: whether the sandbox should
            allow multithreading.
        archive_sandbox: whether the sandbox is to be archived.
        shard: the shard of the Worker completing this job.
        keep_sandbox: whether to forcefully keep the sandbox,
            even if other conditions (the config, the sandbox status)
            don't warrant it.
        sandboxes: the paths of the sandboxes used in
            the Worker during the execution of the job.
        sandbox_digests: the digests of the sandbox archives used to
            debug solutions. (map of sandbox path -> archive digest)
        info: a human readable description of the job.
        success: whether the job succeeded.
        text: description of the outcome of the job,
            to be presented to the user. The first item is a string,
            potentially with %-escaping; the following items are the
            values to be %-formatted into the first.
        files: files submitted by the user.
        managers: managers provided by the admins.
        executables: executables created in the compilation.

        """
        if task_type is None:
            task_type = ""
        if sandboxes is None:
            sandboxes = []
        if sandbox_digests is None:
            sandbox_digests = {}
        if info is None:
            info = ""
        if files is None:
            files = {}
        if managers is None:
            managers = {}
        if executables is None:
            executables = {}

        self.operation = operation
        self.task_type = task_type
        self.task_type_parameters = task_type_parameters
        self.language = language
        self.multithreaded_sandbox = multithreaded_sandbox
        self.archive_sandbox = archive_sandbox
        self.shard = shard
        self.keep_sandbox = keep_sandbox
        self.sandboxes = sandboxes
        self.sandbox_digests = sandbox_digests
        self.info = info

        self.success = success
        self.text = text

        self.files = files
        self.managers = managers
        self.executables = executables

    def export_to_dict(self) -> dict:
        """Return a dict representing the job."""
        res = {
            'operation': (self.operation.to_dict()
                          if self.operation is not None
                          else None),
            'task_type': self.task_type,
            'task_type_parameters': self.task_type_parameters,
            'language': self.language,
            'multithreaded_sandbox': self.multithreaded_sandbox,
            'archive_sandbox': self.archive_sandbox,
            'shard': self.shard,
            'keep_sandbox': self.keep_sandbox,
            'sandboxes': self.sandboxes,
            'sandbox_digests': self.sandbox_digests,
            'info': self.info,
            'success': self.success,
            'text': self.text,
            'files': dict((k, v.digest)
                          for k, v in self.files.items()),
            'managers': dict((k, v.digest)
                             for k, v in self.managers.items()),
            'executables': dict((k, v.digest)
                                for k, v in self.executables.items()),
            }
        return res

    @staticmethod
    def import_from_dict_with_type(data: dict) -> "Job":
        """Create a Job from a dict having a type information.

        data: a dict with all the items required for a job, and
            in addition a 'type' key with associated value
            'compilation' or 'evaluation'.

        return: either a CompilationJob or an EvaluationJob.

        """
        type_ = data['type']
        del data['type']
        if type_ == 'compilation':
            return CompilationJob.import_from_dict(data)
        elif type_ == 'evaluation':
            return EvaluationJob.import_from_dict(data)
        else:
            raise Exception("Couldn't import dictionary with type %s" %
                            (type_))

    @classmethod
    def import_from_dict(cls, data: dict) -> Self:
        """Create a Job from the output of export_to_dict."""
        if data['operation'] is not None:
            data['operation'] = ESOperation.from_dict(data['operation'])
        data['files'] = dict(
            (k, File(k, v)) for k, v in data['files'].items())
        data['managers'] = dict(
            (k, Manager(k, v)) for k, v in data['managers'].items())
        data['executables'] = dict(
            (k, Executable(k, v)) for k, v in data['executables'].items())
        return cls(**data)

    @staticmethod
    def from_operation(
        operation: ESOperation, object_: Submission | UserTest, dataset: Dataset
    ) -> "Job":
        """Produce the job for the operation in the argument.

        Return the Job object that has to be sent to Workers to have
        them perform the operation this object describes.

        operation: the operation to use.
        object_: the object this operation
            refers to (might be a submission or a user test).
        dataset: the dataset this operation refers to.

        return: the job encoding of the operation, as understood
            by Workers and TaskTypes.

        raise (ValueError): if object_ or dataset are not those
            referred by the operation.

        """
        if operation.object_id != object_.id:
            logger.error("Programming error: operation is for object `%s' "
                         "while passed object is `%s'.",
                         operation.object_id, object_.id)
            raise ValueError("Object mismatch while building job.")
        if operation.dataset_id != dataset.id:
            logger.error("Programming error: operation is for dataset `%s' "
                         "while passed dataset is `%s'.",
                         operation.dataset_id, dataset.id)
            raise ValueError("Dataset mismatch while building job.")

        job = None
        if operation.type_ == ESOperation.COMPILATION:
            job = CompilationJob.from_submission(operation, object_, dataset)
        elif operation.type_ == ESOperation.EVALUATION:
            job = EvaluationJob.from_submission(operation, object_, dataset)
        elif operation.type_ == ESOperation.USER_TEST_COMPILATION:
            job = CompilationJob.from_user_test(operation, object_, dataset)
        elif operation.type_ == ESOperation.USER_TEST_EVALUATION:
            job = EvaluationJob.from_user_test(operation, object_, dataset)
        return job

    def get_sandbox_digest_list(self) -> list[str] | None:
        """
        Convert self.sandbox_digests into a list, where each index matches the
        corresponding index in self.sandboxes.
        """
        if not self.sandbox_digests:
            return None
        res: list[str | None] = [None] * len(self.sandboxes)
        for k,v in self.sandbox_digests.items():
            if k in self.sandboxes:
                index = self.sandboxes.index(k)
                res[index] = v
            else:
                logger.warning("Have digest for unknown sandbox %s", k)
        if None in res:
            ind = res.index(None)
            logger.warning("Sandbox %s was not archived", self.sandboxes[ind])
            return None
        return res


class CompilationJob(Job):
    """Job representing a compilation.

    Can represent either the compilation of a user test, or of a
    submission, or of an arbitrary source (as used in cmsMake).

    Input data (usually filled by ES): language, files,
    managers. Output data (filled by the Worker): success,
    compilation_success, executables, text, plus.

    """

    def __init__(
        self,
        operation: ESOperation | None = None,
        task_type: str | None = None,
        task_type_parameters: object = None,
        shard: int | None = None,
        keep_sandbox: bool = False,
        sandboxes: list[str] | None = None,
        sandbox_digests: dict[str, str] | None = None,
        info: str | None = None,
        language: str | None = None,
        multithreaded_sandbox: bool = False,
        archive_sandbox: bool = False,
        files: dict[str, File] | None = None,
        managers: dict[str, Manager] | None = None,
        success: bool | None = None,
        compilation_success: bool | None = None,
        executables: dict[str, Executable] | None = None,
        text: list[str] | None = None,
        plus: dict | None = None,
    ):
        """Initialization.

        See base class for the remaining arguments.

        compilation_success: whether the compilation implicit
            in the job succeeded, or there was a compilation error.
        plus: additional metadata.

        """

        Job.__init__(self, operation, task_type, task_type_parameters,
                     language, multithreaded_sandbox, archive_sandbox,
                     shard, keep_sandbox, sandboxes, sandbox_digests, info, success,
                     text, files, managers, executables)
        self.compilation_success = compilation_success
        self.plus = plus

    def export_to_dict(self) -> dict:
        res = Job.export_to_dict(self)
        res.update({
            'type': 'compilation',
            'compilation_success': self.compilation_success,
            'plus': self.plus,
            })
        return res

    @staticmethod
    def from_submission(
        operation: ESOperation, submission: Submission, dataset: Dataset
    ) -> "CompilationJob":
        """Create a CompilationJob from a submission.

        operation: a COMPILATION operation.
        submission: the submission object referred by the
            operation.
        dataset: the dataset object referred by the
            operation.

        return: the job.

        """
        if operation.type_ != ESOperation.COMPILATION:
            logger.error("Programming error: asking for a compilation job, "
                         "but the operation is %s.", operation.type_)
            raise ValueError("Operation is not a compilation")

        multithreaded = _is_contest_multithreaded(submission.task.contest)

        # dict() is required to detach the dictionary that gets added
        # to the Job from the control of SQLAlchemy
        return CompilationJob(
            operation=operation,
            task_type=dataset.task_type,
            task_type_parameters=dataset.task_type_parameters,
            language=submission.language,
            multithreaded_sandbox=multithreaded,
            archive_sandbox=operation.archive_sandbox,
            files=dict(submission.files),
            managers=dict(dataset.managers),
            info="compile submission %d" % (submission.id)
        )

    def to_submission(self, sr: SubmissionResult):
        """Fill detail of the submission result with the job result.

        sr: the DB object to fill.

        """
        # This should actually be useless.
        sr.invalidate_compilation()

        # No need to check self.success because this method gets called
        # only if it is True.

        sr.set_compilation_outcome(self.compilation_success)
        sr.compilation_text = self.text
        sr.compilation_stdout = self.plus.get('stdout')
        sr.compilation_stderr = self.plus.get('stderr')
        sr.compilation_time = self.plus.get('execution_time')
        sr.compilation_wall_clock_time = \
            self.plus.get('execution_wall_clock_time')
        sr.compilation_memory = self.plus.get('execution_memory')
        sr.compilation_shard = self.shard
        sr.compilation_sandbox_paths = self.sandboxes
        sr.compilation_sandbox_digests = self.get_sandbox_digest_list()
        for executable in self.executables.values():
            sr.executables.set(executable)

    @staticmethod
    def from_user_test(
        operation: ESOperation, user_test: UserTest, dataset: Dataset
    ) -> "CompilationJob":
        """Create a CompilationJob from a user test.

        operation: a USER_TEST_COMPILATION operation.
        user_test: the user test object referred by the
            operation.
        dataset: the dataset object referred by the
            operation.

        return: the job.

        """
        if operation.type_ != ESOperation.USER_TEST_COMPILATION:
            logger.error("Programming error: asking for a user test "
                         "compilation job, but the operation is %s.",
                         operation.type_)
            raise ValueError("Operation is not a user test compilation")

        multithreaded = _is_contest_multithreaded(user_test.task.contest)

        # Add the managers to be got from the Task.
        # dict() is required to detach the dictionary that gets added
        # to the Job from the control of SQLAlchemy
        try:
            language = get_language(user_test.language)
        except KeyError:
            language = None
        managers = dict(user_test.managers)
        task_type = dataset.task_type_object
        auto_managers = task_type.get_auto_managers()
        if auto_managers is not None:
            for manager_filename in auto_managers:
                if manager_filename.endswith(".%l") and language is not None:
                    manager_filename = manager_filename.replace(
                        ".%l", language.source_extension)
                managers[manager_filename] = dataset.managers[manager_filename]
        else:
            for manager_filename in dataset.managers:
                if manager_filename not in managers:
                    managers[manager_filename] = \
                        dataset.managers[manager_filename]

        # Copy header files from dataset.
        # FIXME This bypasses get_auto_managers() logic
        if language is not None:
            for manager_filename in dataset.managers:
                if any(manager_filename.endswith(header)
                       for header in language.header_extensions):
                    managers[manager_filename] = \
                        dataset.managers[manager_filename]

        return CompilationJob(
            operation=operation,
            task_type=dataset.task_type,
            task_type_parameters=dataset.task_type_parameters,
            language=user_test.language,
            multithreaded_sandbox=multithreaded,
            archive_sandbox=operation.archive_sandbox,
            files=dict(user_test.files),
            managers=managers,
            info="compile user test %d" % (user_test.id)
        )

    def to_user_test(self, ur: UserTestResult):
        """Fill detail of the user test result with the job result.

        ur: the DB object to fill.

        """
        # This should actually be useless.
        ur.invalidate_compilation()

        # No need to check self.success because this method gets called
        # only if it is True.

        ur.set_compilation_outcome(self.compilation_success)
        ur.compilation_text = self.text
        ur.compilation_stdout = self.plus.get('stdout')
        ur.compilation_stderr = self.plus.get('stderr')
        ur.compilation_time = self.plus.get('execution_time')
        ur.compilation_wall_clock_time = \
            self.plus.get('execution_wall_clock_time')
        ur.compilation_memory = self.plus.get('execution_memory')
        ur.compilation_shard = self.shard
        ur.compilation_sandbox_paths = self.sandboxes
        ur.compilation_sandbox_digests = self.get_sandbox_digest_list()
        for executable in self.executables.values():
            u_executable = UserTestExecutable(
                executable.filename, executable.digest)
            ur.executables.set(u_executable)


class EvaluationJob(Job):
    """Job representing an evaluation on a testcase.

    Can represent either the evaluation of a user test, or of a
    submission, or of an arbitrary source (as used in cmsMake).

    Input data (usually filled by ES): testcase_codename, language,
    files, managers, executables, input, output, time_limit,
    memory_limit. Output data (filled by the Worker): success,
    outcome, text, user_output, executables, text, plus. Metadata:
    only_execution, get_output.

    """
    def __init__(
        self,
        operation: ESOperation | None = None,
        task_type: str | None = None,
        task_type_parameters: object = None,
        shard: int | None = None,
        keep_sandbox: bool = False,
        sandboxes: list[str] | None = None,
        sandbox_digests: dict[str, str] | None = None,
        info: str | None = None,
        language: str | None = None,
        multithreaded_sandbox: bool = False,
        archive_sandbox: bool = False,
        files: dict[str, File] | None = None,
        managers: dict[str, Manager] | None = None,
        executables: dict[str, Executable] | None = None,
        input: str | None = None,
        output: str | None = None,
        time_limit: float | None = None,
        memory_limit: int | None = None,
        success: bool | None = None,
        outcome: str | None = None,
        text: list[str] | None = None,
        user_output: str | None = None,
        plus: dict | None = None,
        only_execution: bool | None = False,
        get_output: bool | None = False,
    ):
        """Initialization.

        See base class for the remaining arguments.

        input: digest of the input file.
        output: digest of the output file.
        time_limit: user time limit in seconds.
        memory_limit: memory limit in bytes.
        outcome: the outcome of the evaluation, from
            which to compute the score.
        user_output: if requested (with get_output),
            the digest of the file containing the output of the user
            program.
        plus: additional metadata.
        only_execution: whether to perform only the
            execution, or to compare the output with the reference
            solution too.
        get_output: whether to retrieve the execution
            output (together with only_execution, useful for the user
            tests).

        """
        Job.__init__(self, operation, task_type, task_type_parameters,
                     language, multithreaded_sandbox, archive_sandbox,
                     shard, keep_sandbox, sandboxes, sandbox_digests, info, success,
                     text, files, managers, executables)
        self.input = input
        self.output = output
        self.time_limit = time_limit
        self.memory_limit = memory_limit
        self.outcome = outcome
        self.user_output = user_output
        self.plus = plus
        self.only_execution = only_execution
        self.get_output = get_output

    def export_to_dict(self) -> dict:
        res = Job.export_to_dict(self)
        res.update({
            'type': 'evaluation',
            'input': self.input,
            'output': self.output,
            'time_limit': self.time_limit,
            'memory_limit': self.memory_limit,
            'outcome': self.outcome,
            'user_output': self.user_output,
            'plus': self.plus,
            'only_execution': self.only_execution,
            'get_output': self.get_output,
            })
        return res

    @staticmethod
    def from_submission(
        operation: ESOperation, submission: Submission, dataset: Dataset
    ) -> "EvaluationJob":
        """Create an EvaluationJob from a submission.

        operation: an EVALUATION operation.
        submission: the submission object referred by the operation.
        dataset: the dataset object referred by the operation.

        return: the job.

        """
        if operation.type_ != ESOperation.EVALUATION:
            logger.error("Programming error: asking for an evaluation job, "
                         "but the operation is %s.", operation.type_)
            raise ValueError("Operation is not an evaluation")

        multithreaded = _is_contest_multithreaded(submission.task.contest)

        submission_result = submission.get_result(dataset)
        # This should have been created by now.
        assert submission_result is not None

        testcase = dataset.testcases[operation.testcase_codename]

        info = "evaluate submission %d on testcase %s" % \
            (submission.id, testcase.codename)

        # dict() is required to detach the dictionary that gets added
        # to the Job from the control of SQLAlchemy
        return EvaluationJob(
            operation=operation,
            task_type=dataset.task_type,
            task_type_parameters=dataset.task_type_parameters,
            language=submission.language,
            multithreaded_sandbox=multithreaded,
            archive_sandbox=operation.archive_sandbox,
            files=dict(submission.files),
            managers=dict(dataset.managers),
            executables=dict(submission_result.executables),
            input=testcase.input,
            output=testcase.output,
            time_limit=dataset.time_limit,
            memory_limit=dataset.memory_limit,
            info=info
        )

    def to_submission(self, sr: SubmissionResult):
        """Fill detail of the submission result with the job result.

        sr: the DB object to fill.

        """
        # No need to check self.success because this method gets called
        # only if it is True.

        sr.evaluations += [Evaluation(
            text=self.text,
            outcome=self.outcome,
            execution_time=self.plus.get('execution_time'),
            execution_wall_clock_time=self.plus.get(
                'execution_wall_clock_time'),
            execution_memory=self.plus.get('execution_memory'),
            evaluation_shard=self.shard,
            evaluation_sandbox_paths=self.sandboxes,
            evaluation_sandbox_digests=self.get_sandbox_digest_list(),
            testcase=sr.dataset.testcases[self.operation.testcase_codename])]

    @staticmethod
    def from_user_test(
        operation: ESOperation, user_test: UserTest, dataset: Dataset
    ) -> "EvaluationJob":
        """Create an EvaluationJob from a user test.

        operation: an USER_TEST_EVALUATION operation.
        user_test: the user test object referred by the
            operation.
        dataset: the dataset object referred by the
            operation.

        return: the job.

        """
        if operation.type_ != ESOperation.USER_TEST_EVALUATION:
            logger.error("Programming error: asking for a user test "
                         "evaluation job, but the operation is %s.",
                         operation.type_)
            raise ValueError("Operation is not a user test evaluation")

        multithreaded = _is_contest_multithreaded(user_test.task.contest)

        user_test_result = user_test.get_result(dataset)
        # This should have been created by now.
        assert user_test_result is not None

        # Add the managers to be got from the Task.
        # dict() is required to detach the dictionary that gets added
        # to the Job from the control of SQLAlchemy
        language = get_language(user_test.language)
        managers = dict(user_test.managers)
        task_type = dataset.task_type_object
        auto_managers = task_type.get_auto_managers()
        if auto_managers is not None:
            for manager_filename in auto_managers:
                if manager_filename.endswith(".%l") and language is not None:
                    manager_filename = manager_filename.replace(
                        ".%l", language.source_extension)
                managers[manager_filename] = dataset.managers[manager_filename]
        else:
            for manager_filename in dataset.managers:
                if manager_filename not in managers:
                    managers[manager_filename] = \
                        dataset.managers[manager_filename]

        return EvaluationJob(
            operation=operation,
            task_type=dataset.task_type,
            task_type_parameters=dataset.task_type_parameters,
            language=user_test.language,
            multithreaded_sandbox=multithreaded,
            archive_sandbox=operation.archive_sandbox,
            files=dict(user_test.files),
            managers=managers,
            executables=dict(user_test_result.executables),
            input=user_test.input,
            time_limit=dataset.time_limit,
            memory_limit=dataset.memory_limit,
            info="evaluate user test %d" % (user_test.id),
            get_output=True,
            only_execution=True
        )

    def to_user_test(self, ur: UserTestResult):
        """Fill detail of the user test result with the job result.

        ur: the DB object to fill.

        """
        # This should actually be useless.
        ur.invalidate_evaluation()

        # No need to check self.success because this method gets called
        # only if it is True.

        ur.evaluation_text = self.text
        ur.set_evaluation_outcome()
        ur.execution_time = self.plus.get('execution_time')
        ur.execution_wall_clock_time = \
            self.plus.get('execution_wall_clock_time')
        ur.execution_memory = self.plus.get('execution_memory')
        ur.evaluation_shard = self.shard
        ur.evaluation_sandbox_paths = self.sandboxes
        ur.evaluation_sandbox_digests = self.get_sandbox_digest_list()
        ur.output = self.user_output


class JobGroup:
    """A simple collection of jobs."""

    def __init__(self, jobs: list[Job] | None = None):
        self.jobs = jobs if jobs is not None else []

    def export_to_dict(self):
        return {
            "jobs": [job.export_to_dict() for job in self.jobs],
        }

    @classmethod
    def import_from_dict(cls, data: dict) -> Self:
        jobs = []
        for job in data["jobs"]:
            jobs.append(Job.import_from_dict_with_type(job))
        return cls(jobs)

    @staticmethod
    def from_operations(operations, session):
        jobs = []
        for operation in operations:
            # The get_from_id method loads from the instance map (if the
            # object exists there), which thus acts as a cache.
            if operation.for_submission():
                object_ = Submission.get_from_id(operation.object_id, session)
            else:
                object_ = UserTest.get_from_id(operation.object_id, session)
            dataset = Dataset.get_from_id(operation.dataset_id, session)

            jobs.append(Job.from_operation(operation, object_, dataset))
        return JobGroup(jobs)
