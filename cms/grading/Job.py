#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
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

import simplejson as json
from collections import namedtuple

from cms.db.SQLAlchemyAll import File, Manager, Executable


Testcase = namedtuple('Testcase', ['input', 'output'])


class Job(object):
    # Input: task_type, task_type_parameters
    # Metadata: shard, sandboxes, info

    def __init__(self, task_type=None, task_type_parameters=None,
                 shard=None, sandboxes=None, info=None):
        if task_type is None:
            task_type = ""
        if task_type_parameters is None:
            task_type_parameters = []
        if sandboxes is None:
            sandboxes = []
        if info is None:
            info = ""

        self.task_type = task_type
        self.task_type_parameters = task_type_parameters
        self.shard = shard
        self.sandboxes = sandboxes
        self.info = info

    def export_to_dict(self):
        res = {
            'task_type': self.task_type,
            'task_type_parameters': self.task_type_parameters,
            'shard': self.shard,
            'sandboxes': self.sandboxes,
            'info': self.info,
            }
        return res

    @staticmethod
    def import_from_dict_with_type(data):
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
        return cls(**data)


class CompilationJob(Job):
    # Input: language, files, managers
    # Output: success, compilation_success, executables, text, plus

    def __init__(self, task_type=None, task_type_parameters=None,
                 shard=None, sandboxes=None, info=None,
                 language=None, files=None, managers=None,
                 success=None, compilation_success=None,
                 executables=None, text=None, plus=None):
        if files is None:
            files = {}
        if managers is None:
            managers = {}
        if executables is None:
            executables = {}

        Job.__init__(self, task_type, task_type_parameters,
                     shard, sandboxes, info)
        self.language = language
        self.files = files
        self.managers = managers
        self.success = success
        self.compilation_success = compilation_success
        self.executables = executables
        self.text = text
        self.plus = plus

    @staticmethod
    def from_submission(submission, dataset):
        job = CompilationJob()

        # Job
        job.task_type = dataset.task_type
        job.task_type_parameters = json.loads(dataset.task_type_parameters)

        # CompilationJob; dict() is required to detach the dictionary
        # that gets added to the Job from the control of SQLAlchemy
        job.language = submission.language
        job.files = dict(submission.files)
        job.managers = dict(dataset.managers)
        job.info = "compile submission %d" % (submission.id)

        return job

    @staticmethod
    def from_user_test(user_test, dataset):
        job = CompilationJob()

        # Job
        job.task_type = dataset.task_type
        job.task_type_parameters = json.loads(dataset.task_type_parameters)

        # CompilationJob; dict() is required to detach the dictionary
        # that gets added to the Job from the control of SQLAlchemy
        job.language = user_test.language
        job.files = dict(user_test.files)
        job.managers = dict(user_test.managers)
        job.info = "compile user test %d" % (user_test.id)

        # Add the managers to be got from the Task; get_task_type must
        # be imported here to avoid circular dependencies
        from cms.grading.tasktypes import get_task_type
        task_type = get_task_type(dataset=dataset)
        auto_managers = task_type.get_auto_managers()
        if auto_managers is not None:
            for manager_filename in auto_managers:
                job.managers[manager_filename] = \
                    dataset.managers[manager_filename]
        else:
            for manager_filename in dataset.managers:
                if manager_filename not in job.managers:
                    job.managers[manager_filename] = \
                        dataset.managers[manager_filename]

        return job

    def export_to_dict(self):
        res = Job.export_to_dict(self)
        res.update({
            'type': 'compilation',
            'language': self.language,
            'files': dict((k, v.digest)
                          for k, v in self.files.iteritems()),
            'managers': dict((k, v.digest)
                             for k, v in self.managers.iteritems()),
            'success': self.success,
            'compilation_success': self.compilation_success,
            'executables': dict((k, v.digest)
                                for k, v in self.executables.iteritems()),
            'text': self.text,
            'plus': self.plus,
            })
        return res

    @classmethod
    def import_from_dict(cls, data):
        data['files'] = dict(
            (k, File(k, v)) for k, v in data['files'].iteritems())
        data['managers'] = dict(
            (k, Manager(k, v)) for k, v in data['managers'].iteritems())
        data['executables'] = dict(
            (k, Executable(k, v)) for k, v in data['executables'].iteritems())
        return cls(**data)


class EvaluationJob(Job):

    # Input: language, files, managers, executables, testcases,
    #        time_limit, memory_limit
    # Output: success, evaluations
    # Metadata: only_execution, get_output

    # Note that the 'evaluations' attribute isn't a list or a dict of
    # Evaluation objects but just a dict of dicts.

    def __init__(self, task_type=None, task_type_parameters=None,
                 shard=None, sandboxes=None, info=None,
                 language=None, files=None, managers=None,
                 executables=None, testcases=None,
                 time_limit=None, memory_limit=None,
                 success=None, evaluations=None,
                 only_execution=False, get_output=False):
        if files is None:
            files = {}
        if managers is None:
            managers = {}
        if executables is None:
            executables = {}
        if testcases is None:
            testcases = {}
        if evaluations is None:
            evaluations = {}

        Job.__init__(self, task_type, task_type_parameters,
                     shard, sandboxes, info)
        self.language = language
        self.files = files
        self.managers = managers
        self.executables = executables
        self.testcases = testcases
        self.time_limit = time_limit
        self.memory_limit = memory_limit
        self.success = success
        self.evaluations = evaluations
        self.only_execution = only_execution
        self.get_output = get_output

    @staticmethod
    def from_submission(submission, dataset):
        job = EvaluationJob()

        # Job
        job.task_type = dataset.task_type
        job.task_type_parameters = json.loads(dataset.task_type_parameters)

        submission_result = submission.get_result(dataset)

        # This should have been created by now.
        assert submission_result is not None

        # EvaluationJob; dict() is required to detach the dictionary
        # that gets added to the Job from the control of SQLAlchemy
        job.language = submission.language
        job.files = dict(submission.files)
        job.managers = dict(dataset.managers)
        job.executables = dict(submission_result.executables)
        job.testcases = dict((t.num, Testcase(t.input, t.output))
                             for t in dataset.testcases)
        job.time_limit = dataset.time_limit
        job.memory_limit = dataset.memory_limit
        job.info = "evaluate submission %d" % (submission.id)

        return job

    @staticmethod
    def from_user_test(user_test, dataset):
        job = EvaluationJob()

        # Job
        job.task_type = dataset.task_type
        job.task_type_parameters = json.loads(dataset.task_type_parameters)

        user_test_result = user_test.get_result(dataset)

        # This should have been created by now.
        assert user_test_result is not None

        # EvaluationJob; dict() is required to detach the dictionary
        # that gets added to the Job from the control of SQLAlchemy
        job.language = user_test.language
        job.files = dict(user_test.files)
        job.managers = dict(user_test.managers)
        job.executables = dict(user_test_result.executables)
        job.testcases = {0: Testcase(user_test.input, None)}
        job.time_limit = dataset.time_limit
        job.memory_limit = dataset.memory_limit
        job.info = "evaluate user test %d" % (user_test.id)

        # Add the managers to be got from the Task; get_task_type must
        # be imported here to avoid circular dependencies
        from cms.grading.tasktypes import get_task_type
        task_type = get_task_type(dataset=dataset)
        auto_managers = task_type.get_auto_managers()
        if auto_managers is not None:
            for manager_filename in auto_managers:
                job.managers[manager_filename] = \
                    dataset.managers[manager_filename]
        else:
            for manager_filename in dataset.managers:
                if manager_filename not in job.managers:
                    job.managers[manager_filename] = \
                        dataset.managers[manager_filename]

        return job

    def export_to_dict(self):
        res = Job.export_to_dict(self)
        res.update({
            'type': 'evaluation',
            'language': self.language,
            'files': dict((k, v.digest)
                          for k, v in self.files.iteritems()),
            'managers': dict((k, v.digest)
                             for k, v in self.managers.iteritems()),
            'executables': dict((k, v.digest)
                                for k, v in self.executables.iteritems()),
            'testcases': dict((k, (v.input, v.output))
                              for k, v in self.testcases.iteritems()),
            'time_limit': self.time_limit,
            'memory_limit': self.memory_limit,
            'success': self.success,
            # XXX We convert the key from int to str because it'll
            # be the key of a JSON object.
            'evaluations': dict((str(k), v) for k, v
                                in self.evaluations.iteritems()),
            'only_execution': self.only_execution,
            'get_output': self.get_output,
            })
        return res

    @classmethod
    def import_from_dict(cls, data):
        data['files'] = dict(
            (k, File(k, v)) for k, v in data['files'].iteritems())
        data['managers'] = dict(
            (k, Manager(k, v)) for k, v in data['managers'].iteritems())
        data['executables'] = dict(
            (k, Executable(k, v)) for k, v in data['executables'].iteritems())
        data['testcases'] = dict(
            (k, Testcase(*v)) for k, v in data['testcases'].iteritems())
        # XXX We convert the key from str to int because it was the key
        # of a JSON object.
        data['evaluations'] = dict((int(k), v) for k, v
                                   in data['evaluations'].iteritems())
        return cls(**data)
