#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

Used by ContestImporter and DumpUpdater.

This converts the dump to the new schema introduced to support task
versioning in commits
bd80d0c930e25972eeda861719f96990de6e7822
8ee8fa7496d53ff4a8638804eb3aa497586fc6a3
6ee99114f5aca4ad1a94a76f0b11b5363ba2ffd5

"""

from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function


def split_dict(src, *keys):
    ret = dict()
    for k in list(src.iterkeys()):
        v = src[k]
        if k in keys:
            ret[k] = v
            del src[k]
    return ret


class Updater(object):

    def __init__(self, data):
        assert data["_version"] == 1
        self.objs = data
        self.next_id = len(data)

    def get_id(self):
        while unicode(self.next_id) in self.objs:
            self.next_id += 1
        return unicode(self.next_id)

    def run(self):
        for k in list(self.objs.iterkeys()):
            if k.startswith("_"):
                continue
            v = self.objs[k]
            if v["_class"] == "Task":
                self.split_task(k, v)
        return self.objs

    def split_task(self, task_id, task_data):
        dataset_id = self.get_id()
        dataset_data = split_dict(
            task_data,
            "time_limit", "memory_limit",
            "task_type", "task_type_parameters",
            "score_type", "score_type_parameters",
            "managers", "testcases")
        self.objs[dataset_id] = dataset_data

        task_data["_class"] = "Task"
        dataset_data["_class"] = "Dataset"

        task_data["datasets"] = [dataset_id]
        task_data["active_dataset"] = dataset_id
        dataset_data["task"] = task_id
        dataset_data["description"] = "Default"
        dataset_data["autojudge"] = False

        for id_ in dataset_data["managers"].itervalues():
            del self.objs[id_]["task"]
            self.objs[id_]["dataset"] = dataset_id

        for id_ in dataset_data["testcases"]:
            del self.objs[id_]["task"]
            self.objs[id_]["dataset"] = dataset_id

        for id_ in task_data["submissions"]:
            self.split_submission(id_, self.objs[id_], dataset_id)

        for id_ in task_data["user_tests"]:
            self.split_user_test(id_, self.objs[id_], dataset_id)

    def split_submission(self, submission_id, sr_data, dataset_id):
        sr_id = self.get_id()
        submission_data = split_dict(
            sr_data,
            "user", "task",
            "timestamp", "language",
            "files", "token")
        self.objs[submission_id] = submission_data
        self.objs[sr_id] = sr_data

        submission_data["_class"] = "Submission"
        sr_data["_class"] = "SubmissionResult"

        submission_data["results"] = [sr_id]
        sr_data["submission"] = submission_id
        sr_data["dataset"] = dataset_id

        for id_ in sr_data["executables"].itervalues():
            self.objs[id_]["submission"] = submission_id
            self.objs[id_]["dataset"] = dataset_id
            self.objs[id_]["submission_result"] = sr_id

        for id_ in sr_data["evaluations"]:
            self.objs[id_]["submission"] = submission_id
            self.objs[id_]["dataset"] = dataset_id
            self.objs[id_]["submission_result"] = sr_id

    def split_user_test(self, user_test_id, ur_data, dataset_id):
        ur_id = self.get_id()
        user_test_data = split_dict(
            ur_data,
            "user", "task",
            "timestamp", "language", "input",
            "files", "managers")
        self.objs[user_test_id] = user_test_data
        self.objs[ur_id] = ur_data

        user_test_data["_class"] = "UserTest"
        ur_data["_class"] = "UserTestResult"

        user_test_data["results"] = [ur_id]
        ur_data["user_test"] = user_test_id
        ur_data["dataset"] = dataset_id

        for id_ in ur_data["executables"].itervalues():
            self.objs[id_]["submission"] = user_test_id
            self.objs[id_]["dataset"] = dataset_id
            self.objs[id_]["submission_result"] = ur_id
