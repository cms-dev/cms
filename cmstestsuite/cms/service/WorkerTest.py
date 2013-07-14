#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2013 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Tests for the logger service.

"""

import gevent
import unittest
from mock import Mock, call

import cms.service.Worker
from cms.grading import JobException
from cms.grading.Job import EvaluationJob, JobGroup
from cms.service.Worker import Worker


class TestWorker(unittest.TestCase):

    def setUp(self):
        self.service = Worker(0)

    # Testing execute_job_group.

    def test_execute_job_group_success(self):
        """Executes a job group with three successful jobs.

        """
        jobgroup, calls = TestWorker.new_jobgroup(3)
        FakeTaskType.set_results([True] * 3)
        cms.service.Worker.get_task_type = Mock(return_value=FakeTaskType())

        JobGroup.import_from_dict(
            self.service.execute_job_group(jobgroup.export_to_dict()))

        cms.service.Worker.get_task_type.assert_has_calls(
            calls, any_order=True)

    def test_execute_job_group_jobs_failure(self):
        """Executes a job group with three unsuccessful jobs.

        """
        jobgroup, unused_calls = TestWorker.new_jobgroup(2)
        FakeTaskType.set_results([False, False])
        cms.service.Worker.get_task_type = Mock(return_value=FakeTaskType())

        new_group = JobGroup.import_from_dict(
            self.service.execute_job_group(jobgroup.export_to_dict()))

        self.assertFalse(new_group.success)
        # Does not continue after failure.
        self.assertEquals(cms.service.Worker.get_task_type.call_count, 1)

    def test_execute_job_group_tasktype_raise(self):
        """Executes a job group with three jobs raising exceptions.

        """
        jobgroup, unused_calls = TestWorker.new_jobgroup(2)
        FakeTaskType.set_results([Exception()] * 2)
        cms.service.Worker.get_task_type = Mock(return_value=FakeTaskType())

        try:
            JobGroup.import_from_dict(
                self.service.execute_job_group(jobgroup.export_to_dict()))
        except JobException:
            # Expected
            pass
        else:
            self.fail("Expected JobException from the tasktype.")

        # Does not continue after failure.
        self.assertEquals(cms.service.Worker.get_task_type.call_count, 1)

    def test_execute_job_group_subsequent_success(self):
        """Executes a job group with three successful jobs, then another one.

        """
        jobgroup_a, calls_a = TestWorker.new_jobgroup(3)
        FakeTaskType.set_results([True] * 3)
        cms.service.Worker.get_task_type = Mock(return_value=FakeTaskType())

        JobGroup.import_from_dict(
            self.service.execute_job_group(jobgroup_a.export_to_dict()))

        jobgroup_b, calls_b = TestWorker.new_jobgroup(3)
        FakeTaskType.set_results([True] * 3)

        JobGroup.import_from_dict(
            self.service.execute_job_group(jobgroup_b.export_to_dict()))

        cms.service.Worker.get_task_type.assert_has_calls(
            calls_a + calls_b, any_order=True)

    def test_execute_job_group_subsequent_locked(self):
        """Executes a job group with one long job, then another one
        that should fail because of the lock.

        """
        jobgroup_a, calls_a = TestWorker.new_jobgroup(1, prefix="a")
        # Because of how gevent works, the interval here can be very small.
        FakeTaskType.set_results([0.01])
        cms.service.Worker.get_task_type = Mock(return_value=FakeTaskType())

        def first_call():
            JobGroup.import_from_dict(
                self.service.execute_job_group(jobgroup_a.export_to_dict()))

        first_greenlet = gevent.spawn(first_call)
        gevent.sleep(0)  # To ensure we call jobgroup a first.

        jobgroup_b, calls_b = TestWorker.new_jobgroup(1, prefix="b")
        FakeTaskType.set_results([True])

        try:
            JobGroup.import_from_dict(
                self.service.execute_job_group(jobgroup_b.export_to_dict()))
        except JobException:
            # Expected
            pass
        else:
            self.fail("Expected JobException from the lock.")

        first_greenlet.get()

        cms.service.Worker.get_task_type.assert_has_calls(
            calls_a, any_order=True)

    def test_execute_job_group_failure_releases_lock(self):
        """After a failure, the worker should be able to accept another job.

        """
        jobgroup_a, calls_a = TestWorker.new_jobgroup(1)
        FakeTaskType.set_results([Exception()])
        cms.service.Worker.get_task_type = Mock(return_value=FakeTaskType())

        try:
            JobGroup.import_from_dict(
                self.service.execute_job_group(jobgroup_a.export_to_dict()))
        except JobException:
            # Expected.
            pass
        else:
            self.fail("Expected Jobexception from tasktype.")

        jobgroup_b, calls_b = TestWorker.new_jobgroup(3)
        FakeTaskType.set_results([True] * 3)

        JobGroup.import_from_dict(
            self.service.execute_job_group(jobgroup_b.export_to_dict()))

        cms.service.Worker.get_task_type.assert_has_calls(
            calls_a + calls_b, any_order=True)

    # Testing ignore_job.

    def test_ignore_job(self):
        """Executes a job group with two jobs, and sends an ignore_job
        request that should discard the second job.

        """
        jobgroup_a, calls_a = TestWorker.new_jobgroup(2)
        FakeTaskType.set_results([0.01])
        cms.service.Worker.get_task_type = Mock(return_value=FakeTaskType())

        def first_call():
            JobGroup.import_from_dict(
                self.service.execute_job_group(jobgroup_a.export_to_dict()))

        first_greenlet = gevent.spawn(first_call)
        gevent.sleep(0)  # Ensure it enters into the first job.

        self.service.ignore_job()

        first_greenlet.get()

        # Only one call should have been made, the other skipped.
        self.assertEquals(cms.service.Worker.get_task_type.call_count, 1)

    @staticmethod
    def new_jobgroup(number_of_jobs, prefix=None):
        prefix = prefix if prefix is not None else ""
        jobgroup_dict = {}
        calls = []
        for i in xrange(number_of_jobs):
            job_params = ("fake_task_type", "fake_parameters_%s" % i)
            job = EvaluationJob(*job_params, info=prefix + str(i))
            jobgroup_dict[str(i)] = job
            calls.append(call(*job_params))
        return JobGroup(jobgroup_dict), calls


class FakeTaskType:
    execute_results = []
    index = 0
    calls = 0

    def execute_job(self, job, file_cacher):
        FakeTaskType.calls += 1
        result = FakeTaskType.execute_results[FakeTaskType.index]
        FakeTaskType.index += 1
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

    @classmethod
    def set_results(cls, results):
        cls.execute_results = results
        cls.index = 0
        cls.calls = 0


if __name__ == "__main__":
    unittest.main()
