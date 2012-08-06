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


class Job:
    # Input
    task_type = ""
    task_type_parameters = []

    # Metadata
    shard = None
    sandboxes = []
    info = ""


class CompilationJob(Job):

    # Input
    language = ""
    files = {}
    managers = {}

    # Output
    success = None
    compilation_success = None
    executables = {}
    text = None
    plus = None

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


class EvaluationJob(Job):

    # Input
    executables = {}
    testcases = {}
    time_limit = None
    memory_limit = None
    managers = {}
    files = {}

    # Output
    success = None
    evaluations = {}

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
