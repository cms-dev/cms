#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
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

from cms.db.SQLAlchemyAll import File, Manager, Executable, Testcase


class Job:
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
    # Input: langauge, files, managers
    # Output: success, compilation_success, executables, text, plus

    def __init__(self, task_type=None, task_type_parameters=None,
                 shard=None, sandboxes=None, info=None,
                 language=None, files=None,
                 managers=None, success=None,
                 compilation_success=None,
                 executables=None,
                 text=None, plus=None):
        if language is None:
            language = ""
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
    def from_submission(submission):
        job = CompilationJob()

        # Job
        job.task_type = submission.task.task_type
        job.task_type_parameters = json.loads(
            submission.task.task_type_parameters)

        # CompilationJob
        job.language = submission.language
        job.files = submission.files
        job.managers = submission.task.managers
        job.info = "compile submission %d" % (submission.id)

        return job

    @staticmethod
    def from_user_test(user_test):
        job = CompilationJob()

        # Job
        job.task_type = user_test.task.task_type
        job.task_type_parameters = json.loads(
            user_test.task.task_type_parameters)

        # CompilationJob; dict() is required to detach the dictionary
        # that gets added to the Job from the control of SQLAlchemy
        job.language = user_test.language
        job.files = dict(user_test.files)
        job.managers = dict(user_test.managers)
        job.info = "compile user test %d" % (user_test.id)

        # Add the managers to be got from the Task; get_task_type must
        # be imported here to avoid circular dependencies
        from cms.grading.tasktypes import get_task_type
        task_type = get_task_type(task=user_test.task)
        auto_managers = task_type.get_auto_managers()
        if auto_managers is not None:
            for manager_filename in auto_managers:
                job.managers[manager_filename] = \
                    user_test.task.managers[manager_filename]
        else:
            for manager_filename in user_test.task.managers:
                if manager_filename not in job.managers:
                    job.managers[manager_filename] = \
                        user_test.task.managers[manager_filename]

        return job

    def export_to_dict(self):
        res = Job.export_to_dict(self)
        res.update({
                'type': 'compilation',
                'language': self.language,
                'files': [file_.export_to_dict()
                          for file_ in self.files.itervalues()],
                'managers': [manager.export_to_dict()
                             for manager in self.managers.itervalues()],
                'success': self.success,
                'compilation_success': self.compilation_success,
                'executables': [executable.export_to_dict()
                                for executable
                                in self.executables.itervalues()],
                'text': self.text,
                'plus': self.plus,
                })
        return res

    @classmethod
    def import_from_dict(cls, data):
        data['files'] = [File.import_from_dict(file_data)
                         for file_data in data['files']]
        data['files'] = dict([(file_.filename, file_)
                              for file_ in data['files']])
        data['managers'] = [Manager.import_from_dict(manager_data)
                            for manager_data in data['managers']]
        data['managers'] = dict([(manager.filename, manager)
                                 for manager in data['managers']])
        data['executables'] = [Executable.import_from_dict(executable_data)
                               for executable_data in data['executables']]
        data['executables'] = dict([(executable.filename, executable)
                                    for executable in data['executables']])
        return cls(**data)


class EvaluationJob(Job):

    # Input: executables, testcases, time_limit, memory_limit,
    # managers, files
    # Output: success, evaluations
    # Metadata: only_execution, get_output

    def __init__(self, task_type=None, task_type_parameters=None,
                 shard=None, sandboxes=None, info=None,
                 executables=None, testcases=None,
                 time_limit=None, memory_limit=None,
                 managers=None, files=None,
                 success=None, evaluations=None,
                 only_execution=False, get_output=False):
        if executables is None:
            executables = {}
        if testcases is None:
            testcases = {}
        if managers is None:
            managers = {}
        if files is None:
            files = {}
        if evaluations is None:
            evaluations = {}

        Job.__init__(self, task_type, task_type_parameters,
                     shard, sandboxes, info)
        self.executables = executables
        self.testcases = testcases
        self.time_limit = time_limit
        self.memory_limit = memory_limit
        self.managers = managers
        self.files = files
        self.success = success
        self.evaluations = evaluations
        self.only_execution = only_execution
        self.get_output = get_output

    @staticmethod
    def from_submission(submission):
        job = EvaluationJob()

        # Job
        job.task_type = submission.task.task_type
        job.task_type_parameters = json.loads(
            submission.task.task_type_parameters)

        # EvaluationJob; dict() is required to detach the dictionary
        # that gets added to the Job from the control of SQLAlchemy
        job.executables = dict(submission.executables)
        job.testcases = submission.task.testcases
        job.time_limit = submission.task.time_limit
        job.memory_limit = submission.task.memory_limit
        job.managers = dict(submission.task.managers)
        job.files = dict(submission.files)
        job.info = "evaluate submission %d" % (submission.id)

        return job

    @staticmethod
    def from_user_test(user_test):
        job = EvaluationJob()

        # Job
        job.task_type = user_test.task.task_type
        job.task_type_parameters = json.loads(
            user_test.task.task_type_parameters)

        # EvaluationJob
        job.executables = user_test.executables
        job.testcases = [Testcase(input=user_test.input,
                                  output=None)]
        job.time_limit = user_test.task.time_limit
        job.memory_limit = user_test.task.memory_limit
        job.managers = dict(user_test.managers)
        job.files = user_test.files
        job.info = "evaluate user test %d" % (user_test.id)

        # Add the managers to be got from the Task; get_task_type must
        # be imported here to avoid circular dependencies
        from cms.grading.tasktypes import get_task_type
        task_type = get_task_type(task=user_test.task)
        auto_managers = task_type.get_auto_managers()
        if auto_managers is not None:
            for manager_filename in auto_managers:
                job.managers[manager_filename] = \
                    user_test.task.managers[manager_filename]
        else:
            for manager_filename in user_test.task.managers:
                if manager_filename not in job.managers:
                    job.managers[manager_filename] = \
                        user_test.task.managers[manager_filename]

        return job

    def export_to_dict(self):
        res = Job.export_to_dict(self)
        res.update({
                'type': 'evaluation',
                'executables': [executable.export_to_dict()
                                for executable
                                in self.executables.itervalues()],
                'testcases': [testcase.export_to_dict()
                              for testcase in self.testcases],
                'time_limit': self.time_limit,
                'memory_limit': self.memory_limit,
                'managers': [manager.export_to_dict()
                             for manager in self.managers.itervalues()],
                'files': [file_.export_to_dict()
                          for file_ in self.files.itervalues()],
                'success': self.success,
                'evaluations': self.evaluations,
                'only_execution': self.only_execution,
                'get_output': self.get_output,
                })
        return res

    @classmethod
    def import_from_dict(cls, data):
        data['executables'] = [Executable.import_from_dict(executable_data)
                               for executable_data in data['executables']]
        data['executables'] = dict([(executable.filename, executable)
                                    for executable in data['executables']])
        data['testcases'] = [Testcase.import_from_dict(testcase_data)
                             for testcase_data in data['testcases']]
        data['managers'] = [Manager.import_from_dict(manager_data)
                            for manager_data in data['managers']]
        data['managers'] = dict([(manager.filename, manager)
                                 for manager in data['managers']])
        data['files'] = [File.import_from_dict(file_data)
                         for file_data in data['files']]
        data['files'] = dict([(file_.filename, file_)
                              for file_ in data['files']])
        return cls(**data)
