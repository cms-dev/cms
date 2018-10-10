#!/usr/bin/env python3

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

import unittest

from cms.grading.Sandbox import Sandbox
from cms.grading.steps import execution_stats, merge_execution_stats
from cmstestsuite.unit_tests.grading.steps.fakeisolatesandbox \
    import FakeIsolateSandbox


INVALID_UTF8 = b"\xc3\x28"


def get_stats(execution_time, execution_wall_clock_time, execution_memory,
              exit_status, signal=None, stdout=None, stderr=None):
    stats = {
        "execution_time": execution_time,
        "execution_wall_clock_time": execution_wall_clock_time,
        "execution_memory": execution_memory,
        "exit_status": exit_status,
    }
    if signal is not None:
        stats["signal"] = signal
    if stdout is not None:
        stats["stdout"] = stdout
    if stderr is not None:
        stats["stderr"] = stderr
    return stats


class TestExecutionStats(unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.sandbox = FakeIsolateSandbox(None)
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

    def test_success_with_output(self):
        self.sandbox.fake_execute_data(
            True, b"o", b"e", 0.1, 0.5, 1000, "OK")
        self.sandbox.execute_without_std(["command"], wait=True)

        stats = execution_stats(self.sandbox, collect_output=True)
        self.assertEqual(stats,
                         get_stats(0.1, 0.5, 1000 * 1024, Sandbox.EXIT_OK,
                                   stdout="o", stderr="e"))

    def test_invalid_utf8(self):
        self.sandbox.fake_execute_data(
            True,
            b"o" + INVALID_UTF8 + b"1",
            b"e" + INVALID_UTF8 + b"2",
            0.1, 0.5, 1000, "OK")

        self.sandbox.execute_without_std(["command"], wait=True)

        stats = execution_stats(self.sandbox, collect_output=True)

        # UTF-8 invalid parts are replaced with funny question marks (\uFFFD).
        self.assertRegex(stats["stdout"], "^o.*1$")
        self.assertRegex(stats["stderr"], "^e.*2$")


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

    def test_success_first_none(self):
        r1 = get_stats(0.1, 0.2, 0.3, Sandbox.EXIT_SIGNAL, signal=11)
        m = merge_execution_stats(None, r1)
        self.assertStats(m, r1)
        self.assertIsNot(r1, m)

    def test_success_output_joined(self):
        r0 = get_stats(0, 0, 0, Sandbox.EXIT_OK, stdout="o1", stderr="e1")
        r1 = get_stats(0, 0, 0, Sandbox.EXIT_OK, stdout="o2", stderr="e2")
        m = merge_execution_stats(r0, r1)
        self.assertStats(
            m, get_stats(0, 0, 0, Sandbox.EXIT_OK,
                         stdout="o1\n===\no2", stderr="e1\n===\ne2"))

    def test_success_output_missing_one(self):
        r0 = get_stats(0, 0, 0, Sandbox.EXIT_OK, stdout="o1")
        r1 = get_stats(0, 0, 0, Sandbox.EXIT_OK, stderr="e2")
        m = merge_execution_stats(r0, r1)
        self.assertStats(
            m, get_stats(0, 0, 0, Sandbox.EXIT_OK, stdout="o1", stderr="e2"))

    def test_failure_second_none(self):
        with self.assertRaises(ValueError):
            merge_execution_stats(None, None)

        r0 = get_stats(0.1, 0.2, 0.3, Sandbox.EXIT_OK)
        with self.assertRaises(ValueError):
            merge_execution_stats(r0, None)

    def test_empty_outputs_are_preserved(self):
        r0 = get_stats(0, 0, 0, Sandbox.EXIT_OK, stdout="o1", stderr="")
        r1 = get_stats(0, 0, 0, Sandbox.EXIT_OK, stdout="", stderr="e2")
        m = merge_execution_stats(r0, r1)
        self.assertStats(
            m, get_stats(0, 0, 0, Sandbox.EXIT_OK,
                         stdout="o1\n===\n", stderr="\n===\ne2"))

    def test_missing_outputs_are_not_preserved(self):
        r0 = get_stats(0, 0, 0, Sandbox.EXIT_OK)
        r1 = get_stats(0, 0, 0, Sandbox.EXIT_OK, stdout="o2", stderr="e2")
        m = merge_execution_stats(r0, r1)
        self.assertStats(
            m, get_stats(0, 0, 0, Sandbox.EXIT_OK, stdout="o2", stderr="e2"))


if __name__ == "__main__":
    unittest.main()
