#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

"""Tests for stats.py."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa

import unittest

from cms.grading.Sandbox import Sandbox
from cms.grading.steps import execution_stats, merge_execution_stats
from cmstestsuite.unit_tests.grading.steps.fakeisolatesandbox \
    import FakeIsolateSandbox


def get_stats(execution_time, execution_wall_clock_time, execution_memory,
              exit_status, signal=None):
    stats = {
        "execution_time": execution_time,
        "execution_wall_clock_time": execution_wall_clock_time,
        "execution_memory": execution_memory,
        "exit_status": exit_status,
    }
    if signal is not None:
        stats["signal"] = signal
    return stats


class TestExecutionStats(unittest.TestCase):

    def setUp(self):
        super(TestExecutionStats, self).setUp()
        self.sandbox = FakeIsolateSandbox(True, None)
        self.sandbox.stdout_file = "stdout.txt"
        self.sandbox.stderr_file = "stderr.txt"

    def test_success(self):
        # Tell the fake sandbox the command data to fake, and execute it.
        self.sandbox.fake_execute_data(
            True, b"o", b"e", 0.1, 0.5, 1000, "OK")
        self.sandbox.execute_without_std(["command"], wait=True)

        stats = execution_stats(self.sandbox)
        self.assertEqual(stats,
                         get_stats(0.1, 0.5, 1000 * 1024, Sandbox.EXIT_OK))

    def test_success_signal_exit(self):
        self.sandbox.fake_execute_data(
            True, b"o", b"e", 0.1, 0.5, 1000, "SG", signal=11)
        self.sandbox.execute_without_std(["command"], wait=True)

        stats = execution_stats(self.sandbox)
        self.assertEqual(stats,
                         get_stats(0.1, 0.5, 1000 * 1024, Sandbox.EXIT_SIGNAL,
                                   signal=11))


class TestMergeExecutionStats(unittest.TestCase):

    def assertStats(self, r0, r1):
        """Assert that r0 and r1 are the same result."""
        self.assertAlmostEqual(r0["execution_time"], r1["execution_time"])
        self.assertAlmostEqual(r0["execution_wall_clock_time"],
                               r1["execution_wall_clock_time"])
        self.assertAlmostEqual(r0["execution_memory"], r1["execution_memory"])
        self.assertEqual(r0["exit_status"], r1["exit_status"])

        # Optional keys.
        for key in ["signal", "stdout", "stderr"]:
            self.assertEqual(key in r0, key in r1, key)
            self.assertEqual(r0.get(key), r1.get(key))

    def test_success_status_ok(self):
        self.assertStats(
            merge_execution_stats(
                get_stats(1.0, 2.0, 300, Sandbox.EXIT_OK),
                get_stats(0.1, 0.2, 0.3, Sandbox.EXIT_OK)),
            get_stats(1.1, 2.0, 300.3, Sandbox.EXIT_OK))

    def test_success_sequential(self):
        # In non-concurrent mode memory is max'd and wall clock is added.
        self.assertStats(
            merge_execution_stats(
                get_stats(1.0, 2.0, 300, Sandbox.EXIT_OK),
                get_stats(0.1, 0.2, 0.3, Sandbox.EXIT_OK),
                concurrent=False),
            get_stats(1.1, 2.2, 300.0, Sandbox.EXIT_OK))

    def test_success_first_status_ok(self):
        self.assertStats(
            merge_execution_stats(
                get_stats(0, 0, 0, Sandbox.EXIT_OK),
                get_stats(0, 0, 0, Sandbox.EXIT_TIMEOUT)),
            get_stats(0, 0, 0, Sandbox.EXIT_TIMEOUT))
        self.assertStats(
            merge_execution_stats(
                get_stats(0, 0, 0, Sandbox.EXIT_OK),
                get_stats(0, 0, 0, Sandbox.EXIT_SIGNAL, signal=11)),
            get_stats(0, 0, 0, Sandbox.EXIT_SIGNAL, signal=11))
        self.assertStats(
            merge_execution_stats(
                get_stats(0, 0, 0, Sandbox.EXIT_OK),
                get_stats(0, 0, 0, Sandbox.EXIT_SIGNAL, signal=11)),
            get_stats(0, 0, 0, Sandbox.EXIT_SIGNAL, signal=11))

    def test_success_first_status_not_ok(self):
        self.assertStats(
            merge_execution_stats(
                get_stats(0, 0, 0, Sandbox.EXIT_TIMEOUT),
                get_stats(0, 0, 0, Sandbox.EXIT_SIGNAL, signal=11)),
            get_stats(0, 0, 0, Sandbox.EXIT_TIMEOUT))
        self.assertStats(
            merge_execution_stats(
                get_stats(0, 0, 0, Sandbox.EXIT_SIGNAL, signal=9),
                get_stats(0, 0, 0, Sandbox.EXIT_SIGNAL, signal=11)),
            get_stats(0, 0, 0, Sandbox.EXIT_SIGNAL, signal=9))
        self.assertStats(
            merge_execution_stats(
                get_stats(0, 0, 0, Sandbox.EXIT_SIGNAL, signal=9),
                get_stats(0, 0, 0, Sandbox.EXIT_OK)),
            get_stats(0, 0, 0, Sandbox.EXIT_SIGNAL, signal=9))

    def test_success_stats_are_not_modified(self):
        r0 = get_stats(1.0, 2.0, 300, Sandbox.EXIT_OK)
        r1 = get_stats(0.1, 0.2, 0.3, Sandbox.EXIT_SIGNAL, signal=11)
        m = merge_execution_stats(r0, r1)
        self.assertStats(
            m, get_stats(1.1, 2.0, 300.3, Sandbox.EXIT_SIGNAL, signal=11))
        self.assertStats(
            r0, get_stats(1.0, 2.0, 300, Sandbox.EXIT_OK))
        self.assertStats(
            r1, get_stats(0.1, 0.2, 0.3, Sandbox.EXIT_SIGNAL, signal=11))


if __name__ == "__main__":
    unittest.main()
