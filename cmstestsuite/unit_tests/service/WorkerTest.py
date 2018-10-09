#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2013-2016 Stefano Maggiolo <s.maggiolo@gmail.com>
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

import unittest
from unittest.mock import Mock, call

import gevent

import cms.service.Worker
from cms.grading import JobException
from cms.grading.Job import JobGroup, EvaluationJob
from cms.service.Worker import Worker
from cms.service.esoperations import ESOperation
from cmstestsuite.unit_tests.testidgenerator import \
    unique_long_id, unique_unicode_id


class TestWorker(unittest.TestCase):

    def setUp(self):
        self.service = Worker(0)

    # Testing execute_job.

    def test_execute_job_success(self):
        """Executes three successful jobs.

        """
        n_jobs = 3
        jobs, calls = TestWorker.new_jobs(n_jobs)
        task_type = FakeTaskType([True] * n_jobs)
        cms.service.Worker.get_task_type = Mock(return_value=task_type)

        for job in jobs:
            job_group = JobGroup([job])
            ret_job_group = JobGroup.import_from_dict(
                self.service.execute_job_group(job_group.export_to_dict()))
            self.assertTrue(ret_job_group.jobs[0].success)

        cms.service.Worker.get_task_type.assert_has_calls(calls)
        self.assertEquals(task_type.call_count, n_jobs)

    def test_execute_job_failure(self):
        """Executes two unsuccessful jobs.

        """
        n_jobs = 2
        jobs, unused_calls = TestWorker.new_jobs(n_jobs)
        task_type = FakeTaskType([False] * n_jobs)
        cms.service.Worker.get_task_type = Mock(return_value=task_type)

        results = []
        for job in jobs:
            job_group = JobGroup([job])
            results.append(JobGroup.import_from_dict(
                self.service.execute_job_group(job_group.export_to_dict())))

        for job_group in results:
            for job in job_group.jobs:
                self.assertFalse(job.success)
        self.assertEquals(cms.service.Worker.get_task_type.call_count, n_jobs)
        self.assertEquals(task_type.call_count, n_jobs)

    def test_execute_job_tasktype_raise(self):
        """Executes two jobs raising exceptions.

        """
        n_jobs = 2
        jobs, unused_calls = TestWorker.new_jobs(n_jobs)
        task_type = FakeTaskType([Exception(), Exception()])
        cms.service.Worker.get_task_type = Mock(return_value=task_type)

        for job in jobs:
            with self.assertRaises(JobException):
                job_group = JobGroup([job])
                JobGroup.import_from_dict(
                    self.service.execute_job_group(job_group.export_to_dict()))

        self.assertEquals(cms.service.Worker.get_task_type.call_count, n_jobs)
        self.assertEquals(task_type.call_count, n_jobs)

    def test_execute_job_subsequent_success(self):
        """Executes three successful jobs, then four others.

        """
        n_jobs_a = 3
        jobs_a, calls_a = TestWorker.new_jobs(n_jobs_a, prefix="a")
        task_type_a = FakeTaskType([True] * n_jobs_a)
        cms.service.Worker.get_task_type = Mock(return_value=task_type_a)

        for job in jobs_a:
            job_group = JobGroup([job])
            JobGroup.import_from_dict(
                self.service.execute_job_group(job_group.export_to_dict()))

        cms.service.Worker.get_task_type.assert_has_calls(calls_a)
        self.assertEquals(task_type_a.call_count, n_jobs_a)

        n_jobs_b = 4
        jobs_b, calls_b = TestWorker.new_jobs(n_jobs_b, prefix="b")
        task_type_b = FakeTaskType([True] * n_jobs_b)
        cms.service.Worker.get_task_type = Mock(return_value=task_type_b)

        for job in jobs_b:
            job_group = JobGroup([job])
            JobGroup.import_from_dict(
                self.service.execute_job_group(job_group.export_to_dict()))

        cms.service.Worker.get_task_type.assert_has_calls(calls_b)
        self.assertEquals(task_type_b.call_count, n_jobs_b)

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
            job_group = JobGroup([jobs_a[0]])
            JobGroup.import_from_dict(
                self.service.execute_job_group(job_group.export_to_dict()))

        first_greenlet = gevent.spawn(first_call)
        gevent.sleep(0)  # To ensure we call jobgroup_a first.

        with self.assertRaises(JobException):
            job_group = JobGroup([jobs_b[0]])
            JobGroup.import_from_dict(
                self.service.execute_job_group(job_group.export_to_dict()))

        first_greenlet.get()
        self.assertNotIn(calls_b[0],
                         cms.service.Worker.get_task_type.mock_calls)
        cms.service.Worker.get_task_type.assert_has_calls(calls_a)

    def test_execute_job_failure_releases_lock(self):
        """After a failure, the worker should be able to accept another job.

        """
        n_jobs_a = 1
        jobs_a, calls_a = TestWorker.new_jobs(n_jobs_a)
        task_type_a = FakeTaskType([Exception()])
        cms.service.Worker.get_task_type = Mock(return_value=task_type_a)

        with self.assertRaises(JobException):
            job_group = JobGroup([jobs_a[0]])
            JobGroup.import_from_dict(
                self.service.execute_job_group(job_group.export_to_dict()))
        cms.service.Worker.get_task_type.assert_has_calls(calls_a)
        self.assertEquals(task_type_a.call_count, n_jobs_a)

        n_jobs_b = 3
        jobs_b, calls_b = TestWorker.new_jobs(n_jobs_b)
        task_type_b = FakeTaskType([True] * n_jobs_b)
        cms.service.Worker.get_task_type = Mock(return_value=task_type_b)

        for job in jobs_b:
            job_group = JobGroup([job])
            JobGroup.import_from_dict(
                self.service.execute_job_group(job_group.export_to_dict()))

        cms.service.Worker.get_task_type.assert_has_calls(calls_b)
        self.assertEquals(task_type_b.call_count, n_jobs_b)

    def test_execute_job_group_success(self):
        """Executes two successful job groups.

        """
        n_jobs = [3, 3]
        job_groups, calls = TestWorker.new_job_groups(n_jobs)
        task_type = FakeTaskType([True] * sum(n_jobs))
        cms.service.Worker.get_task_type = Mock(return_value=task_type)

        for job_group in job_groups:
            JobGroup.import_from_dict(
                self.service.execute_job_group(job_group.export_to_dict()))

        cms.service.Worker.get_task_type.assert_has_calls(calls)
        self.assertEquals(task_type.call_count, sum(n_jobs))

    def test_execute_job_group_mixed_success(self):
        """Executes three job groups with mixed grades of success.

        """
        n_jobs = [4, 4, 4]
        expected_success = (
            [True] * n_jobs[0] +
            [False] + [True] * (n_jobs[1] - 1) +
            [False] * n_jobs[2])
        self.assertEquals(sum(n_jobs), len(expected_success))

        job_groups, calls = TestWorker.new_job_groups(n_jobs)
        task_type = FakeTaskType(expected_success)
        cms.service.Worker.get_task_type = Mock(return_value=task_type)

        results = []
        for job_group in job_groups:
            results.append(JobGroup.import_from_dict(
                self.service.execute_job_group(job_group.export_to_dict())))

        expected_idx = 0
        for result in results:
            for job in result.jobs:
                self.assertIs(expected_success[expected_idx], job.success)
                expected_idx += 1

        cms.service.Worker.get_task_type.assert_has_calls(calls)
        self.assertEquals(task_type.call_count, sum(n_jobs))

    def test_execute_job_group_mixed_exceptions(self):
        """Executes a job group with some exceptions.

        """
        n_jobs = 4
        expected_success = [True, Exception(), False, True]
        self.assertEquals(n_jobs, len(expected_success))

        job_groups, unused_calls = TestWorker.new_job_groups([n_jobs])
        task_type = FakeTaskType(expected_success)
        cms.service.Worker.get_task_type = Mock(return_value=task_type)

        with self.assertRaises(JobException):
            JobGroup.import_from_dict(
                self.service.execute_job_group(job_groups[0].export_to_dict()))

    @staticmethod
    def new_jobs(number_of_jobs, prefix=None):
        prefix = prefix if prefix is not None else ""
        jobs = []
        calls = []
        for i in range(number_of_jobs):
            job_params = [
                ESOperation(ESOperation.EVALUATION,
                            unique_long_id(), unique_long_id(),
                            unique_unicode_id()),
                "fake_task_type",
                "fake_parameters_%s%d" % (prefix, i)
            ]
            job = EvaluationJob(*job_params, info="%s%d" % (prefix, i))
            jobs.append(job)
            # Arguments to get_task_type are the same as for the job,
            # but omitting the operation.
            calls.append(call(*job_params[1:]))
        return jobs, calls

    @staticmethod
    def new_job_groups(spec, prefix=None):
        """Return len(spec) job groups each with spec[i] jobs."""
        prefix = prefix if prefix is not None else ""
        job_groups = []
        calls = []
        for i, number_of_jobs in enumerate(spec):
            jobs, this_calls = TestWorker.new_jobs(
                number_of_jobs, str(i) + prefix)
            job_groups.append(JobGroup(jobs))
            calls += this_calls
        return job_groups, calls


class FakeTaskType:
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
