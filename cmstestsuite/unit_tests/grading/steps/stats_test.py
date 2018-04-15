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
from cms.grading.steps import merge_execution_stats


class TestMergeExecutionStats(unittest.TestCase):

    @staticmethod
    def _res(execution_time, execution_wall_clock_time, execution_memory,
             exit_status, signal=None):
        r = {
            "execution_time": execution_time,
            "execution_wall_clock_time": execution_wall_clock_time,
            "execution_memory": execution_memory,
            "exit_status": exit_status,
        }
        if signal is not None:
            r["signal"] = signal
        return r

    def assertRes(self, r0, r1):
        """Assert that r0 and r1 are the same result."""
        self.assertAlmostEqual(r0["execution_time"], r1["execution_time"])
        self.assertAlmostEqual(r0["execution_wall_clock_time"],
                               r1["execution_wall_clock_time"])
        self.assertAlmostEqual(r0["execution_memory"], r1["execution_memory"])
        self.assertEqual(r0["exit_status"], r1["exit_status"])

        key = "signal"
        self.assertEqual(key in r0, key in r1)
        self.assertEqual(r0.get(key), r1.get(key))

    def test_success_status_ok(self):
        self.assertRes(
            merge_execution_stats(
                self._res(1.0, 2.0, 300, Sandbox.EXIT_OK),
                self._res(0.1, 0.2, 0.3, Sandbox.EXIT_OK)),
            self._res(1.1, 2.0, 300.3, Sandbox.EXIT_OK))

    def test_success_sequential(self):
        # In non-concurrent mode memory is max'd and wall clock is added.
        self.assertRes(
            merge_execution_stats(
                self._res(1.0, 2.0, 300, Sandbox.EXIT_OK),
                self._res(0.1, 0.2, 0.3, Sandbox.EXIT_OK),
                concurrent=False),
            self._res(1.1, 2.2, 300.0, Sandbox.EXIT_OK))

    def test_success_first_status_ok(self):
        self.assertRes(
            merge_execution_stats(
                self._res(0, 0, 0, Sandbox.EXIT_OK),
                self._res(0, 0, 0, Sandbox.EXIT_TIMEOUT)),
            self._res(0, 0, 0, Sandbox.EXIT_TIMEOUT))
        self.assertRes(
            merge_execution_stats(
                self._res(0, 0, 0, Sandbox.EXIT_OK),
                self._res(0, 0, 0, Sandbox.EXIT_SIGNAL, signal=11)),
            self._res(0, 0, 0, Sandbox.EXIT_SIGNAL, signal=11))
        self.assertRes(
            merge_execution_stats(
                self._res(0, 0, 0, Sandbox.EXIT_OK),
                self._res(0, 0, 0, Sandbox.EXIT_SIGNAL, signal=11)),
            self._res(0, 0, 0, Sandbox.EXIT_SIGNAL, signal=11))

    def test_success_first_status_not_ok(self):
        self.assertRes(
            merge_execution_stats(
                self._res(0, 0, 0, Sandbox.EXIT_TIMEOUT),
                self._res(0, 0, 0, Sandbox.EXIT_SIGNAL, signal=11)),
            self._res(0, 0, 0, Sandbox.EXIT_TIMEOUT))
        self.assertRes(
            merge_execution_stats(
                self._res(0, 0, 0, Sandbox.EXIT_SIGNAL, signal=9),
                self._res(0, 0, 0, Sandbox.EXIT_SIGNAL, signal=11)),
            self._res(0, 0, 0, Sandbox.EXIT_SIGNAL, signal=9))
        self.assertRes(
            merge_execution_stats(
                self._res(0, 0, 0, Sandbox.EXIT_SIGNAL, signal=9),
                self._res(0, 0, 0, Sandbox.EXIT_OK)),
            self._res(0, 0, 0, Sandbox.EXIT_SIGNAL, signal=9))

    def test_success_results_are_not_modified(self):
        r0 = self._res(1.0, 2.0, 300, Sandbox.EXIT_OK)
        r1 = self._res(0.1, 0.2, 0.3, Sandbox.EXIT_SIGNAL, signal=11)
        m = merge_execution_stats(r0, r1)
        self.assertRes(
            m, self._res(1.1, 2.0, 300.3, Sandbox.EXIT_SIGNAL, signal=11))
        self.assertRes(
            r0, self._res(1.0, 2.0, 300, Sandbox.EXIT_OK))
        self.assertRes(
            r1, self._res(0.1, 0.2, 0.3, Sandbox.EXIT_SIGNAL, signal=11))


if __name__ == "__main__":
    unittest.main()
