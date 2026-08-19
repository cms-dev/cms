#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2026 Luca Versari <veluca93@gmail.com>
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

"""Tests for updater 49."""

import copy
import unittest

from cmscontrib.updaters.update_49 import Updater


class TestUpdate49(unittest.TestCase):

    def test_communication_migration(self):
        data = {
            "_version": 48,
            "1": {
                "_class": "Task",
                "name": "comm_task",
            },
            "2": {
                "_class": "Dataset",
                "task": "1",
                "task_type": "Communication",
                "task_type_parameters": [1, "stub", "fifo_io"],
            },
            "3": {
                "_class": "Manager",
                "dataset": "2",
                "filename": "stub.cpp",
                "digest": "abc",
            },
            "4": {
                "_class": "Manager",
                "dataset": "2",
                "filename": "stub.py",
                "digest": "def",
            },
            "5": {
                "_class": "Manager",
                "dataset": "2",
                "filename": "manager",
                "digest": "ghi",
            },
            "6": {
                "_class": "UserTest",
                "task": "1",
            },
            "7": {
                "_class": "UserTestManager",
                "user_test": "6",
                "filename": "stub.cpp",
                "digest": "abc",
            },
            "8": {
                "_class": "Task",
                "name": "batch_task",
            },
            "9": {
                "_class": "Dataset",
                "task": "8",
                "task_type": "Batch",
                "task_type_parameters": ["alone", ["input.txt", "output.txt"], "diff"],
            },
            "10": {
                "_class": "Manager",
                "dataset": "9",
                "filename": "stub.cpp",
                "digest": "xyz",
            },
        }

        updater = Updater(copy.deepcopy(data))
        res = updater.run()

        # Communication dataset parameters updated
        self.assertEqual(res["2"]["task_type_parameters"], [1, "grader", "fifo_io"])
        # Managers on communication dataset renamed
        self.assertEqual(res["3"]["filename"], "grader.cpp")
        self.assertEqual(res["4"]["filename"], "grader.py")
        self.assertEqual(res["5"]["filename"], "manager")
        # UserTestManager on communication task renamed
        self.assertEqual(res["7"]["filename"], "grader.cpp")
        # Batch dataset and its managers untouched
        self.assertEqual(res["9"]["task_type_parameters"], ["alone", ["input.txt", "output.txt"], "diff"])
        self.assertEqual(res["10"]["filename"], "stub.cpp")

    def test_conflict_dataset_raises(self):
        data = {
            "_version": 48,
            "1": {
                "_class": "Task",
                "name": "comm_task",
            },
            "2": {
                "_class": "Dataset",
                "task": "1",
                "task_type": "Communication",
                "task_type_parameters": [1, "stub", "fifo_io"],
            },
            "3": {
                "_class": "Manager",
                "dataset": "2",
                "filename": "stub.cpp",
                "digest": "abc",
            },
            "4": {
                "_class": "Manager",
                "dataset": "2",
                "filename": "grader.cpp",
                "digest": "xyz",
            },
        }

        updater = Updater(copy.deepcopy(data))
        with self.assertRaises(RuntimeError):
            updater.run()

    def test_conflict_user_test_raises(self):
        data = {
            "_version": 48,
            "1": {
                "_class": "Task",
                "name": "comm_task",
            },
            "2": {
                "_class": "Dataset",
                "task": "1",
                "task_type": "Communication",
                "task_type_parameters": [1, "stub", "fifo_io"],
            },
            "6": {
                "_class": "UserTest",
                "task": "1",
            },
            "7": {
                "_class": "UserTestManager",
                "user_test": "6",
                "filename": "stub.cpp",
                "digest": "abc",
            },
            "8": {
                "_class": "UserTestManager",
                "user_test": "6",
                "filename": "grader.cpp",
                "digest": "xyz",
            },
        }

        updater = Updater(copy.deepcopy(data))
        with self.assertRaises(RuntimeError):
            updater.run()


if __name__ == "__main__":
    unittest.main()
