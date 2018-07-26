#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa
from six import itervalues, iteritems

import logging

from cms import FEEDBACK_LEVEL_RESTRICTED
from cms.db import File, Manager, Executable, UserTestExecutable, Evaluation
from cms.grading.languagemanager import get_language
from cms.service.esoperations import ESOperation


logger = logging.getLogger(__name__)


def _is_contest_multithreaded(contest):
    """Return if the contest allows multithreaded compilations and evaluations

    The rule is that this is allowed when the contest has a language that
    requires this.

    contest (Contest): the contest to check
    return (boolean): True if the sandbox should allow multithreading.

    """
    return any(get_language(l).requires_multithreading
               for l in contest.languages)


class Job(object):
    """Base class for all jobs.

    Input data (usually filled by ES): task_type,
    task_type_parameters. Metadata: shard, sandboxes, info.

    """

    def __init__(self, operation=None,
                 task_type=None, task_type_parameters=None,
                 language=None, multithreaded_sandbox=False,
                 shard=None, sandboxes=None, info=None,
                 success=None, text=None,
                 files=None, managers=None, executables=None):
        """Initialization.

        operation (dict|None): the operation, in the format that
            ESOperation.to_dict() uses.
        task_type (string|None): the name of the task type.
        task_type_parameters (object|None): the parameters for the
            creation of the correct task type.
        language (string|None): the language of the submission / user
            test.
        multithreaded_sandbox (boolean): whether the sandbox should
            allow multithreading.
        shard (int|None): the shard of the Worker completing this job.
        sandboxes ([string]|None): the paths of the sandboxes used in
            the Worker during the execution of the job.
        info (string|None): a human readable description of the job.
        success (bool|None): whether the job succeeded.
        text ([object]|None): description of the outcome of the job,
            to be presented to the user. The first item is a string,
            potentially with %-escaping; the following items are the
            values to be %-formatted into the first.
        files ({string: File}|None): files submitted by the user.
        managers ({string: Manager}|None): managers provided by the
            admins.
        executables ({string: Executable}|None): executables created
            in the compilation.

        """
        if operation is None:
            operation = {}
        if task_type is None:
            task_type = ""
        if sandboxes is None:
            sandboxes = []
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
        self.shard = shard
        self.sandboxes = sandboxes
        self.info = info

        self.success = success
        self.text = text

        self.files = files
        self.managers = managers
        self.executables = executables

    def export_to_dict(self):
        """Return a dict representing the job."""
        res = {
            'operation': self.operation,
            'task_type': self.task_type,
            'task_type_parameters': self.task_type_parameters,
            'language': self.language,
            'multithreaded_sandbox': self.multithreaded_sandbox,
            'shard': self.shard,
            'sandboxes': self.sandboxes,
            'info': self.info,
            'success': self.success,
            'text': self.text,
            'files': dict((k, v.digest)
                          for k, v in iteritems(self.files)),
            'managers': dict((k, v.digest)
                             for k, v in iteritems(self.managers)),
            'executables': dict((k, v.digest)
                                for k, v in iteritems(self.executables)),
            }
        return res

    @staticmethod
    def import_from_dict_with_type(data):
        """Create a Job from a dict having a type information.

        data (dict): a dict with all the items required for a job, and
            in addition a 'type' key with associated value
            'compilation' or 'evaluation'.

        return (Job): either a CompilationJob or an EvaluationJob.

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
    def import_from_dict(cls, data):
        """Create a Job from the output of export_to_dict."""
        return cls(**data)

    @staticmethod
    def from_operation(operation, object_, dataset):
        """Produce the job for the operation in the argument.

        Return the Job object that has to be sent to Workers to have
        them perform the operation this object describes.

        operation (ESOperation): the operation to use.
        object_ (Submission|UserTest): the object this operation
            refers to (might be a submission or a user test).
        dataset (Dataset): the dataset this operation refers to.

        return (Job): the job encoding of the operation, as understood
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


class CompilationJob(Job):
    """Job representing a compilation.

    Can represent either the compilation of a user test, or of a
    submission, or of an arbitrary source (as used in cmsMake).

    Input data (usually filled by ES): language, files,
    managers. Output data (filled by the Worker): success,
    compilation_success, executables, text, plus.

    """

    def __init__(self, operation=None, task_type=None,
                 task_type_parameters=None,
                 shard=None, sandboxes=None, info=None,
                 language=None, multithreaded_sandbox=False,
                 files=None, managers=None,
                 success=None, compilation_success=None,
                 executables=None, text=None, plus=None):
        """Initialization.

        See base class for the remaining arguments.

        compilation_success (bool|None): whether the compilation implicit
            in the job succeeded, or there was a compilation error.
        plus ({}|None): additional metadata.

        """

        Job.__init__(self, operation, task_type, task_type_parameters,
                     language, multithreaded_sandbox,
                     shard, sandboxes, info, success, text,
                     files, managers, executables)
        self.compilation_success = compilation_success
        self.plus = plus

    def export_to_dict(self):
        res = Job.export_to_dict(self)
        res.update({
            'type': 'compilation',
            'compilation_success': self.compilation_success,
            'plus': self.plus,
            })
        return res

    @classmethod
    def import_from_dict(cls, data):
        data['files'] = dict(
            (k, File(k, v)) for k, v in iteritems(data['files']))
        data['managers'] = dict(
            (k, Manager(k, v)) for k, v in iteritems(data['managers']))
        data['executables'] = dict(
            (k, Executable(k, v)) for k, v in iteritems(data['executables']))
        return cls(**data)

    @staticmethod
    def from_submission(operation, submission, dataset):
        """Create a CompilationJob from a submission.

        operation (ESOperation): a COMPILATION operation.
        submission (Submission): the submission object referred by the
            operation.
        dataset (Dataset): the dataset object referred by the
            operation.

        return (CompilationJob): the job.

        """
        if operation.type_ != ESOperation.COMPILATION:
            logger.error("Programming error: asking for a compilation job, "
                         "but the operation is %s.", operation.type_)
            raise ValueError("Operation is not a compilation")

        multithreaded = _is_contest_multithreaded(submission.task.contest)

        # dict() is required to detach the dictionary that gets added
        # to the Job from the control of SQLAlchemy
        return CompilationJob(
            operation=operation.to_dict(),
            task_type=dataset.task_type,
            task_type_parameters=dataset.task_type_parameters,
            language=submission.language,
            multithreaded_sandbox=multithreaded,
            files=dict(submission.files),
            managers=dict(dataset.managers),
            info="compile submission %d" % (submission.id)
        )

    def to_submission(self, sr):
        """Fill detail of the submission result with the job result.

        sr (SubmissionResult): the DB object to fill.

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
        sr.compilation_sandbox = ":".join(self.sandboxes)
        for executable in itervalues(self.executables):
            sr.executables.set(executable)

    @staticmethod
    def from_user_test(operation, user_test, dataset):
        """Create a CompilationJob from a user test.

        operation (ESOperation): a USER_TEST_COMPILATION operation.
        user_test (UserTest): the user test object referred by the
            operation.
        dataset (Dataset): the dataset object referred by the
            operation.

        return (CompilationJob): the job.

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

        return CompilationJob(
            operation=operation.to_dict(),
            task_type=dataset.task_type,
            task_type_parameters=dataset.task_type_parameters,
            language=user_test.language,
            multithreaded_sandbox=multithreaded,
            files=dict(user_test.files),
            managers=managers,
            info="compile user test %d" % (user_test.id)
        )

    def to_user_test(self, ur):
        """Fill detail of the user test result with the job result.

        ur (UserTestResult): the DB object to fill.

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
        ur.compilation_sandbox = ":".join(self.sandboxes)
        for executable in itervalues(self.executables):
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
    def __init__(self, operation=None, task_type=None,
                 task_type_parameters=None, shard=None,
                 sandboxes=None, info=None,
                 language=None, multithreaded_sandbox=False,
                 files=None, managers=None, executables=None,
                 feedback_level=FEEDBACK_LEVEL_RESTRICTED,
                 input=None, output=None,
                 time_limit=None, memory_limit=None,
                 success=None, outcome=None, text=None,
                 user_output=None, plus=None,
                 only_execution=False, get_output=False):
        """Initialization.

        See base class for the remaining arguments.

        feedback_level (str): the level of details to show to users.
        input (string|None): digest of the input file.
        output (string|None): digest of the output file.
        time_limit (float|None): user time limit in seconds.
        memory_limit (int|None): memory limit in bytes.
        outcome (string|None): the outcome of the evaluation, from
            which to compute the score.
        user_output (unicode|None): if requested (with get_output),
            the digest of the file containing the output of the user
            program.
        plus ({}|None): additional metadata.
        only_execution (bool|None): whether to perform only the
            execution, or to compare the output with the reference
            solution too.
        get_output (bool|None): whether to retrieve the execution
            output (together with only_execution, useful for the user
            tests).

        """
        Job.__init__(self, operation, task_type, task_type_parameters,
                     language, multithreaded_sandbox,
                     shard, sandboxes, info, success, text,
                     files, managers, executables)
        self.feedback_level = feedback_level
        self.input = input
        self.output = output
        self.time_limit = time_limit
        self.memory_limit = memory_limit
        self.outcome = outcome
        self.user_output = user_output
        self.plus = plus
        self.only_execution = only_execution
        self.get_output = get_output

    def export_to_dict(self):
        res = Job.export_to_dict(self)
        res.update({
            'type': 'evaluation',
            'feedback_level': self.feedback_level,
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

    @classmethod
    def import_from_dict(cls, data):
        data['files'] = dict(
            (k, File(k, v)) for k, v in iteritems(data['files']))
        data['managers'] = dict(
            (k, Manager(k, v)) for k, v in iteritems(data['managers']))
        data['executables'] = dict(
            (k, Executable(k, v)) for k, v in iteritems(data['executables']))
        return cls(**data)

    @staticmethod
    def from_submission(operation, submission, dataset):
        """Create an EvaluationJob from a submission.

        operation (ESOperation): an EVALUATION operation.
        submission (Submission): the submission object referred by the
            operation.
        dataset (Dataset): the dataset object referred by the
            operation.

        return (EvaluationJob): the job.

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
            operation=operation.to_dict(),
            task_type=dataset.task_type,
            task_type_parameters=dataset.task_type_parameters,
            language=submission.language,
            multithreaded_sandbox=multithreaded,
            files=dict(submission.files),
            managers=dict(dataset.managers),
            executables=dict(submission_result.executables),
            feedback_level=dataset.task.feedback_level,
            input=testcase.input,
            output=testcase.output,
            time_limit=dataset.time_limit,
            memory_limit=dataset.memory_limit,
            info=info
        )

    def to_submission(self, sr):
        """Fill detail of the submission result with the job result.

        sr (SubmissionResult): the DB object to fill.

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
            evaluation_sandbox=":".join(self.sandboxes),
            testcase=sr.dataset.testcases[
                self.operation["testcase_codename"]])]

    @staticmethod
    def from_user_test(operation, user_test, dataset):
        """Create an EvaluationJob from a user test.

        operation (ESOperation): an USER_TEST_EVALUATION operation.
        user_test (UserTest): the user test object referred by the
            operation.
        dataset (Dataset): the dataset object referred by the
            operation.

        return (EvaluationJob): the job.

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
            operation=operation.to_dict(),
            task_type=dataset.task_type,
            task_type_parameters=dataset.task_type_parameters,
            language=user_test.language,
            multithreaded_sandbox=multithreaded,
            files=dict(user_test.files),
            managers=managers,
            executables=dict(user_test_result.executables),
            feedback_level=dataset.task.feedback_level,
            input=user_test.input,
            time_limit=dataset.time_limit,
            memory_limit=dataset.memory_limit,
            info="evaluate user test %d" % (user_test.id),
            get_output=True,
            only_execution=True
        )

    def to_user_test(self, ur):
        """Fill detail of the user test result with the job result.

        ur (UserTestResult): the DB object to fill.

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
        ur.evaluation_sandbox = ":".join(self.sandboxes)
        ur.output = self.user_output


class JobGroup(object):
    """A simple collection of jobs."""

    def __init__(self, jobs=None):
        self.jobs = jobs if jobs is not None else []

    def export_to_dict(self):
        return {
            "jobs": [job.export_to_dict() for job in self.jobs],
        }

    @classmethod
    def import_from_dict(cls, data):
        jobs = []
        for job in data["jobs"]:
            jobs.append(Job.import_from_dict_with_type(job))
        return cls(jobs)
