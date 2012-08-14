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

from cms.db.SQLAlchemyAll import File, Manager


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
        job.info = "submission %d" % (submission.id)

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
        return cls(**data)


class EvaluationJob(Job):

    # Input: executables, testcases, time_limit, memory_limit,
    # managers, files
    # Output: success, evaluations

    def __init__(self, task_type=None, task_type_parameters=None,
                 shard=None, sandboxes=None, info=None,
                 executables=None, testcases=None,
                 time_limit=None, memory_limit=None,
                 managers=None, files=None,
                 success=None, evaluations=None):
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

    @staticmethod
    def from_submission(submission):
        job = EvaluationJob()

        # Job
        job.task_type = submission.task.task_type
        job.task_type_parameters = json.loads(
            submission.task.task_type_parameters)

        # EvaluationJob
        job.executables = submission.executables
        job.testcases = submission.task.testcases
        job.time_limit = submission.task.time_limit
        job.memory_limit = submission.task.memory_limit
        job.managers = submission.task.managers
        job.files = submission.files

        return job

    def export_to_dict(self):
        res = Job.export_to_dict(self)
        res.update({
                'type': 'evaluation',
                'executables': self.executables,
                'testcases': self.testcases,
                'time_limit': self.time_limit,
                'memory_limit': self.memory_limit,
                'managers': self.managers,
                'files': self.files,
                'success': self.success,
                'evaluations': self.evaluations,
                })
        return res
