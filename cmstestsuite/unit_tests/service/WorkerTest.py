#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2013 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2015 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""Tests for the worker.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import gevent
import unittest
from mock import Mock, call

import cms.service.Worker
from cms.grading import JobException
from cms.grading.Job import Job, EvaluationJob
from cms.service.Worker import Worker


class TestWorker(unittest.TestCase):

    def setUp(self):
        self.service = Worker(0)

    # Testing execute_job.

    def test_execute_job_success(self):
        """Executes three successful jobs.

        """
        jobs, calls = TestWorker.new_jobs(3)
        task_type = FakeTaskType([True, True, True])
        cms.service.Worker.get_task_type = Mock(return_value=task_type)

        for job in jobs:
            Job.import_from_dict_with_type(
                self.service.execute_job(job.export_to_dict()))

        cms.service.Worker.get_task_type.assert_has_calls(calls)
        self.assertEquals(task_type.call_count, 3)

    def test_execute_job_failure(self):
        """Executes two unsuccessful jobs.

        """
        jobs, unused_calls = TestWorker.new_jobs(2)
        task_type = FakeTaskType([False, False])
        cms.service.Worker.get_task_type = Mock(return_value=task_type)

        results = []
        for job in jobs:
            results.append(Job.import_from_dict_with_type(
                self.service.execute_job(job.export_to_dict())))

        self.assertFalse(any(job.success for job in results))
        self.assertEquals(cms.service.Worker.get_task_type.call_count, 2)
        self.assertEquals(task_type.call_count, 2)

    def test_execute_job_tasktype_raise(self):
        """Executes two jobs raising exceptions.

        """
        jobs, unused_calls = TestWorker.new_jobs(2)
        task_type = FakeTaskType([Exception(), Exception()])
        cms.service.Worker.get_task_type = Mock(return_value=task_type)

        for job in jobs:
            with self.assertRaises(JobException):
                Job.import_from_dict_with_type(
                    self.service.execute_job(job.export_to_dict()))

        self.assertEquals(cms.service.Worker.get_task_type.call_count, 2)
        self.assertEquals(task_type.call_count, 2)

    def test_execute_job_subsequent_success(self):
        """Executes three successful jobs, then other three.

        """
        jobs_a, calls_a = TestWorker.new_jobs(3, prefix="a")
        task_type_a = FakeTaskType([True, True, True])
        cms.service.Worker.get_task_type = Mock(return_value=task_type_a)

        for job in jobs_a:
            Job.import_from_dict_with_type(
                self.service.execute_job(job.export_to_dict()))

        cms.service.Worker.get_task_type.assert_has_calls(calls_a)
        self.assertEquals(task_type_a.call_count, 3)

        jobs_b, calls_b = TestWorker.new_jobs(3, prefix="b")
        task_type_b = FakeTaskType([True, True, True])
        cms.service.Worker.get_task_type = Mock(return_value=task_type_b)

        for job in jobs_b:
            Job.import_from_dict_with_type(
                self.service.execute_job(job.export_to_dict()))

        cms.service.Worker.get_task_type.assert_has_calls(calls_b)
        self.assertEquals(task_type_b.call_count, 3)

    def test_execute_job_subsequent_locked(self):
        """Executes a long job, then another one that should fail
        because of the lock.

        """
        # Because of how gevent works, the interval here can be very small.
        task_type = FakeTaskType([0.01])
        cms.service.Worker.get_task_type = Mock(return_value=task_type)

        jobs_a, calls_a = TestWorker.new_jobs(1, prefix="a")
        jobs_b, calls_b = TestWorker.new_jobs(1, prefix="b")

        def first_call():
            Job.import_from_dict_with_type(
                self.service.execute_job(jobs_a[0].export_to_dict()))

        first_greenlet = gevent.spawn(first_call)
        gevent.sleep(0)  # To ensure we call jobgroup_a first.

        with self.assertRaises(JobException):
            Job.import_from_dict_with_type(
                self.service.execute_job(jobs_b[0].export_to_dict()))

        first_greenlet.get()
        self.assertNotIn(calls_b[0],
                         cms.service.Worker.get_task_type.mock_calls)
        cms.service.Worker.get_task_type.assert_has_calls(calls_a)

    def test_execute_job_failure_releases_lock(self):
        """After a failure, the worker should be able to accept another job.

        """
        jobs_a, calls_a = TestWorker.new_jobs(1)
        task_type_a = FakeTaskType([Exception()])
        cms.service.Worker.get_task_type = Mock(return_value=task_type_a)

        with self.assertRaises(JobException):
            Job.import_from_dict_with_type(
                self.service.execute_job(jobs_a[0].export_to_dict()))
        cms.service.Worker.get_task_type.assert_has_calls(calls_a)
        self.assertEquals(task_type_a.call_count, 1)

        jobs_b, calls_b = TestWorker.new_jobs(3)
        task_type_b = FakeTaskType([True, True, True])
        cms.service.Worker.get_task_type = Mock(return_value=task_type_b)

        for job in jobs_b:
            Job.import_from_dict_with_type(
                self.service.execute_job(job.export_to_dict()))

        cms.service.Worker.get_task_type.assert_has_calls(calls_b)
        self.assertEquals(task_type_b.call_count, 3)

    @staticmethod
    def new_jobs(number_of_jobs, prefix=None):
        prefix = prefix if prefix is not None else ""
        jobs = []
        calls = []
        for i in xrange(number_of_jobs):
            job_params = ("fake_task_type",
                          "fake_parameters_%s%d" % (prefix, i))
            job = EvaluationJob(*job_params, info="%s%d" % (prefix, i))
            jobs.append(job)
            calls.append(call(*job_params))
        return jobs, calls


class FakeTaskType(object):
    def __init__(self, execute_results):
        self.execute_results = execute_results
        self.index = 0
        self.call_count = 0

    def execute_job(self, job, file_cacher):
        self.call_count += 1
        result = self.execute_results[self.index]
        self.index += 1
        if isinstance(result, bool):
            # Boolean: it is the success of the job.
            job.success = result
        elif isinstance(result, Exception):
            # Exception: raise.
            raise result
        else:
            # Float: wait the number of seconds.
            job.success = True
            gevent.sleep(result)

    def set_results(self, results):
        self.execute_results = results


if __name__ == "__main__":
    unittest.main()
