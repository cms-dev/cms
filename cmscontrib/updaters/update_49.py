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

"""A class to update a dump created by CMS.

Used by DumpImporter and DumpUpdater.

Renames Communication and Interactive task managers from stub.%l to grader.%l and updates
the compilation parameter from "stub" to "grader".

"""


class Updater:

    def __init__(self, data):
        assert data["_version"] == 48
        self.objs = data

    def run(self):
        datasets_task_type = {}
        tasks_to_update = set()

        for k, v in self.objs.items():
            if k.startswith("_"):
                continue
            if v.get("_class") == "Dataset":
                datasets_task_type[k] = v.get("task_type")
                if v.get("task_type") in ("Communication", "Interactive"):
                    if "task" in v:
                        tasks_to_update.add(v["task"])
                    params = v.get("task_type_parameters")
                    if isinstance(params, list) and len(params) >= 2:
                        if params[1] == "stub":
                            params[1] = "grader"
                        v["task_type_parameters"] = params

        # Collect existing manager filenames per dataset and user test
        dataset_existing_managers = set()
        user_test_existing_managers = set()
        for k, v in self.objs.items():
            if k.startswith("_"):
                continue
            if v.get("_class") == "Manager":
                dataset_existing_managers.add((v.get("dataset"), v.get("filename")))
            elif v.get("_class") == "UserTestManager":
                user_test_existing_managers.add((v.get("user_test"), v.get("filename")))

        # Check for conflicts and perform renames
        for k, v in self.objs.items():
            if k.startswith("_"):
                continue
            if v.get("_class") == "Manager":
                dataset_key = v.get("dataset")
                if datasets_task_type.get(dataset_key) in ("Communication", "Interactive"):
                    fn = v.get("filename", "")
                    if fn.startswith("stub."):
                        new_fn = "grader" + fn[4:]
                        if (dataset_key, new_fn) in dataset_existing_managers:
                            raise RuntimeError(
                                "Cannot update dump: dataset %s contains both %s and %s"
                                % (dataset_key, fn, new_fn)
                            )
                        v["filename"] = new_fn
                        dataset_existing_managers.add((dataset_key, new_fn))
            elif v.get("_class") == "UserTestManager":
                user_test_key = v.get("user_test")
                user_test_obj = self.objs.get(user_test_key, {})
                task_key = user_test_obj.get("task")
                if task_key in tasks_to_update:
                    fn = v.get("filename", "")
                    if fn.startswith("stub."):
                        new_fn = "grader" + fn[4:]
                        if (user_test_key, new_fn) in user_test_existing_managers:
                            raise RuntimeError(
                                "Cannot update dump: user test %s contains both %s and %s"
                                % (user_test_key, fn, new_fn)
                            )
                        v["filename"] = new_fn
                        user_test_existing_managers.add((user_test_key, new_fn))

        return self.objs
