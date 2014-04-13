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

This converts the dump to the new format introduced in commit
db4adada08d66b4797d0569d95e8f0c028a4e5e0.

"""

from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

from functools import partial


class Updater(object):

    def __init__(self, data):
        self.data = data
        self.objs = dict()
        self.next_id = 0

    def run(self):
        self.parse_contest(self.data)
        self.objs["_objects"] = ["0"]
        return self.objs

    def get_id(self):
        ret = unicode(self.next_id)
        self.next_id += 1
        return ret

    def parse_list(self, list_, fun, num=False, **kwargs):
        ret = list()
        for i, item in enumerate(list_):
            item_id = fun(item)
            if num:
                self.objs[item_id]['num'] = i
            for k, v in kwargs.iteritems():
                self.objs[item_id][k] = v
            ret.append(item_id)
        return ret

    def parse_dict(self, list_, fun, key, **kwargs):
        ret = dict()
        for item in list_:
            item_id = fun(item)
            for k, v in kwargs.iteritems():
                self.objs[item_id][k] = v
            ret[item[key]] = item_id
        return ret

    def parse_generic(self, data, cls):
        id_ = self.get_id()
        data['_class'] = cls
        self.objs[id_] = data
        return id_

    def parse_contest(self, data):
        id_ = self.get_id()

        data['tasks'] = self.parse_list(
            data['tasks'], self.parse_task, contest=id_)

        tasks_by_name = dict((self.objs[i]['name'], i) for i in data['tasks'])

        data['users'] = self.parse_list(data['users'],
                                        partial(self.parse_user,
                                                tasks_by_name=tasks_by_name),
                                        contest=id_)
        data['announcements'] = self.parse_list(
            data['announcements'],
            partial(self.parse_generic, cls='Announcement'), contest=id_)

        data['_class'] = 'Contest'
        self.objs[id_] = data
        return id_

    def parse_task(self, data):
        id_ = self.get_id()

        data['statements'] = self.parse_dict(
            data['statements'], partial(self.parse_generic, cls='Statement'),
            'language', task=id_)
        data['attachments'] = self.parse_dict(
            data['attachments'], partial(self.parse_generic, cls='Attachment'),
            'filename', task=id_)
        data['submission_format'] = self.parse_list(
            data['submission_format'],
            partial(self.parse_generic, cls='SubmissionFormatElement'),
            task=id_)
        data['managers'] = self.parse_dict(
            data['managers'], partial(self.parse_generic, cls='Manager'),
            'filename', task=id_)
        data['testcases'] = self.parse_list(
            data['testcases'], partial(self.parse_generic, cls='Testcase'),
            True, task=id_)

        data['submissions'] = []
        data['user_tests'] = []

        # Handle some pre-1.0 dumps
        if "score_parameters" in data:
            data["score_type_parameters"] = data["score_parameters"]
            del data["score_parameters"]

        data['_class'] = 'Task'
        self.objs[id_] = data
        return id_

    def parse_user(self, data, tasks_by_name):
        id_ = self.get_id()

        data['messages'] = self.parse_list(
            data['messages'],
            partial(self.parse_generic, cls='Message'), user=id_)
        data['questions'] = self.parse_list(
            data['questions'],
            partial(self.parse_generic, cls='Question'), user=id_)
        data['submissions'] = self.parse_list(
            data['submissions'],
            partial(self.parse_submission, tasks_by_name=tasks_by_name),
            user=id_)
        # Because of a bug in older versions of CMS, some dumps may
        # lack the user_tests key; unfortunately user tests for such
        # contests have been lost
        if 'user_tests' in data:
            data['user_tests'] = self.parse_list(
                data['user_tests'],
                partial(self.parse_user_test, tasks_by_name=tasks_by_name),
                user=id_)
        else:
            data['user_tests'] = []

        data['_class'] = 'User'
        self.objs[id_] = data
        return id_

    def parse_submission(self, data, tasks_by_name):
        id_ = self.get_id()

        data['files'] = self.parse_dict(
            data['files'],
            partial(self.parse_generic, cls='File'), 'filename',
            submission=id_)
        data['executables'] = self.parse_dict(
            data['executables'],
            partial(self.parse_generic, cls='Executable'), 'filename',
            submission=id_)
        data['evaluations'] = self.parse_list(
            data['evaluations'],
            partial(self.parse_generic, cls='Evaluation'), submission=id_)
        if data['token'] is not None:
            data['token'] = self.parse_generic(data['token'], 'Token')

        task_id = tasks_by_name[data['task']]
        data['task'] = task_id
        self.objs[task_id]['submissions'].append(id_)

        data['_class'] = 'Submission'
        self.objs[id_] = data
        return id_

    def parse_user_test(self, data, tasks_by_name):
        id_ = self.get_id()

        data['files'] = self.parse_dict(
            data['files'], partial(self.parse_generic, cls='UserTestFile'),
            'filename', user_test=id_)
        data['executables'] = self.parse_dict(
            data['executables'],
            partial(self.parse_generic, cls='UserTestExecutable'),
            'filename', user_test=id_)
        data['managers'] = self.parse_dict(
            data['managers'],
            partial(self.parse_generic, cls='UserTestManager'),
            'filename', user_test=id_)

        task_id = tasks_by_name[data['task']]
        data['task'] = task_id
        self.objs[task_id]['user_tests'].append(id_)

        data['_class'] = 'UserTest'
        self.objs[id_] = data
        return id_
