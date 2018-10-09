#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2012 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2013-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2013-2016 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Luca Versari <veluca93@gmail.com>
# Copyright © 2014 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2016 Peyman Jabbarzade Ganje <peyman.jabarzade@gmail.com>
# Copyright © 2017 Luca Chiodini <luca@chiodini.org>
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

import json
import logging
import re
import sys
import time

from cmstestsuite import CONFIG, TestException, sh
from cmstestsuite.web import Browser
from cmstestsuite.web.AWSRequests import \
    AWSLoginRequest, AWSSubmissionViewRequest, AWSUserTestViewRequest
from cmstestsuite.web.CWSRequests import \
    CWSLoginRequest, SubmitRequest, SubmitUserTestRequest


logger = logging.getLogger(__name__)


class FunctionalTestFramework:
    """An object encapsulating the status of a functional test

    It maintains facilities to interact with the services while running a
    functional tests, e.g. via virtual browsers, and also offers facilities
    to create and retrieve objects from the services.

    """

    # Base URLs for AWS and CWS
    AWS_BASE_URL = "http://localhost:8889"
    CWS_BASE_URL = "http://localhost:8888"

    # Regexes for submission statuses.
    WAITING_STATUSES = re.compile(
        r'Compiling\.\.\.|Evaluating\.\.\.|Scoring\.\.\.|Evaluated')
    COMPLETED_STATUSES = re.compile(
        r'Compilation failed|Evaluated \(|Scored \(')

    # Regexes for user test statuses
    WAITING_STATUSES_USER_TEST = re.compile(
        r'Compiling\.\.\.|Evaluating\.\.\.')
    COMPLETED_STATUSES_USER_TEST = re.compile(
        r'Compilation failed|Evaluated')

    # Singleton instance for this class.
    __instance = None

    def __new__(cls):
        if FunctionalTestFramework.__instance is None:
            FunctionalTestFramework.__instance = object.__new__(cls)
        return FunctionalTestFramework.__instance

    def __init__(self):
        # This holds the decoded-JSON of the cms.conf configuration file.
        # Lazily loaded, to be accessed through the getter method.
        self._cms_config = None

        # Persistent browsers to access AWS and CWS. Lazily loaded, to be
        # accessed through the getter methods.
        self._aws_browser = None
        self._cws_browser = None

        # List of users and tasks we created as part of the test.
        self.created_users = {}
        self.created_tasks = {}

        # Information on the administrator running the tests.
        self.admin_info = {}

    def get_aws_browser(self):
        if self._aws_browser is None:
            self._aws_browser = Browser()

            lr = AWSLoginRequest(self._aws_browser,
                                 self.admin_info["username"],
                                 self.admin_info["password"],
                                 base_url=self.AWS_BASE_URL)
            self._aws_browser.login(lr)
        return self._aws_browser

    def get_cws_browser(self, user_id):
        if self._cws_browser is None:
            self._cws_browser = Browser()
            username = self.created_users[user_id]['username']
            password = self.created_users[user_id]['password']
            lr = CWSLoginRequest(
                self._cws_browser, username, password,
                base_url=self.CWS_BASE_URL)
            self._cws_browser.login(lr)
        return self._cws_browser

    def initialize_aws(self):
        """Create an admin.

        The username will be admin_<suffix>, where <suffix> will be the first
        integer (from 1) for which an admin with that name doesn't yet exist.

        return (str): the suffix.

        """
        logger.info("Creating admin...")
        self.admin_info["password"] = "adminpwd"

        suffix = "1"
        while True:
            self.admin_info["username"] = "admin_%s" % suffix
            logger.info("Trying %(username)s" % self.admin_info)
            try:
                sh([sys.executable, "cmscontrib/AddAdmin.py",
                    "%(username)s" % self.admin_info,
                    "-p", "%(password)s" % self.admin_info],
                   ignore_failure=False)
            except TestException:
                suffix = str(int(suffix) + 1)
            else:
                break

        return suffix

    def get_cms_config(self):
        if self._cms_config is None:
            with open("%(CONFIG_PATH)s" % CONFIG, "rt", encoding="utf-8") as f:
                self._cms_config = json.load(f)
        return self._cms_config

    def admin_req(self, path, args=None, files=None):
        browser = self.get_aws_browser()
        return browser.do_request(self.AWS_BASE_URL + '/' + path, args, files)

    def get_tasks(self):
        """Return the existing tasks

        return ({string: {id: string, title: string}}): the tasks, as a
            dictionary with the task name as key.

        """
        r = self.admin_req('tasks')
        groups = re.findall(r'''
            <tr>\s*
            <td><a\s+href="./task/(\d+)">(.*)</a></td>\s*
            <td>(.*)</td>\s*
            ''', r.text, re.X)
        tasks = {}
        for g in groups:
            id_, name, title = g
            id_ = int(id_)
            tasks[name] = {
                'title': title,
                'id': id_,
            }
        return tasks

    def get_users(self, contest_id):
        """Return the existing users

        return ({string: {id: string, firstname: string, lastname: string}):
            the users, as a dictionary with the username as key.

        """
        r = self.admin_req('contest/%s/users' % contest_id)
        groups = re.findall(r'''
            <tr> \s*
            <td> \s* (.*) \s* </td> \s*
            <td> \s* (.*) \s* </td> \s*
            <td><a\s+href="./user/(\d+)">(.*)</a></td>
        ''', r.text, re.X)
        users = {}
        for g in groups:
            firstname, lastname, id_, username = g
            id_ = int(id_)
            users[username] = {
                'firstname': firstname,
                'lastname': lastname,
                'id': id_,
            }
        return users

    def add_contest(self, **kwargs):
        add_args = {
            "name": kwargs.get('name'),
            "description": kwargs.get('description'),
        }
        resp = self.admin_req('contests/add', args=add_args)
        # Contest ID is returned as HTTP response.
        page = resp.text
        match = re.search(
            r'<form enctype="multipart/form-data" '
            r'action="../contest/([0-9]+)" '
            r'method="POST" name="edit_contest" style="display:inline;">',
            page)
        if match is not None:
            contest_id = int(match.groups()[0])
            self.admin_req('contest/%s' % contest_id, args=kwargs)
            return contest_id
        else:
            raise TestException("Unable to create contest.")

    def add_task(self, **kwargs):
        add_args = {
            "name": kwargs.get('name'),
            "title": kwargs.get('title'),
        }
        r = self.admin_req('tasks/add', args=add_args)
        response = r.text
        match_task_id = re.search(r'/task/([0-9]+)$', r.url)
        match_dataset_id = re.search(r'/dataset/([0-9]+)', response)
        if match_task_id and match_dataset_id:
            task_id = int(match_task_id.group(1))
            dataset_id = int(match_dataset_id.group(1))
            edit_args = {}
            for k, v in kwargs.items():
                edit_args[k.replace("{{dataset_id}}", str(dataset_id))] = v
            r = self.admin_req('task/%s' % task_id, args=edit_args)
            self.created_tasks[task_id] = kwargs
        else:
            raise TestException("Unable to create task.")

        r = self.admin_req('contest/' + kwargs["contest_id"] + '/tasks/add',
                           args={"task_id": str(task_id)})
        g = re.search('<input type="radio" name="task_id" value="' +
                      str(task_id) + '"/>', r.text)
        if g:
            return task_id
        else:
            raise TestException("Unable to assign task to contest.")

    def add_manager(self, task_id, manager):
        args = {}
        files = [
            ('manager', manager),
        ]
        dataset_id = self.get_task_active_dataset_id(task_id)
        self.admin_req('dataset/%s/managers/add' % dataset_id,
                       files=files, args=args)

    def get_task_active_dataset_id(self, task_id):
        resp = self.admin_req('task/%s' % task_id)
        page = resp.text
        match = re.search(
            r'id="title_dataset_([0-9]+).* \(Live\)</',
            page)
        if match is None:
            raise TestException("Unable to create contest.")
        dataset_id = int(match.groups()[0])
        return dataset_id

    def add_testcase(self, task_id, num, input_file, output_file, public):
        files = [
            ('input', input_file),
            ('output', output_file),
        ]
        args = {}
        args["codename"] = "%03d" % num
        if public:
            args['public'] = '1'
        dataset_id = self.get_task_active_dataset_id(task_id)
        self.admin_req('dataset/%s/testcases/add' % dataset_id,
                       files=files, args=args)

    def add_user(self, **kwargs):
        r = self.admin_req('users/add', args=kwargs)
        g = re.search(r'/user/([0-9]+)$', r.url)
        if g:
            user_id = int(g.group(1))
            self.created_users[user_id] = kwargs
        else:
            raise TestException("Unable to create user.")

        kwargs["user_id"] = user_id
        r = self.admin_req('contest/%s/users/add' % kwargs["contest_id"],
                           args=kwargs)
        g = re.search('<input type="radio" name="user_id" value="' +
                      str(user_id) + '"/>', r.text)
        if g:
            return user_id
        else:
            raise TestException("Unable to create participation.")

    def add_existing_task(self, task_id, **kwargs):
        """Inform the framework of an existing task"""
        self.created_tasks[task_id] = kwargs

    def add_existing_user(self, user_id, **kwargs):
        """Inform the framework of an existing user"""
        self.created_users[user_id] = kwargs

    def cws_submit(self, task_id, user_id,
                   submission_format, filenames, language):
        task = (task_id, self.created_tasks[task_id]['name'])

        browser = self.get_cws_browser(user_id)
        sr = SubmitRequest(browser, task, base_url=self.CWS_BASE_URL,
                           submission_format=submission_format,
                           filenames=filenames, language=language)
        sr.execute()
        submission_id = sr.get_submission_id()

        if submission_id is None:
            raise TestException("Failed to submit solution.")

        return submission_id

    def cws_submit_user_test(self, task_id, user_id,
                             submission_format, filenames, language):
        task = (task_id, self.created_tasks[task_id]['name'])

        browser = self.get_cws_browser(user_id)
        sr = SubmitUserTestRequest(
            browser, task, base_url=self.CWS_BASE_URL,
            submission_format=submission_format,
            filenames=filenames, language=language)
        sr.execute()
        user_test_id = sr.get_user_test_id()

        if user_test_id is None:
            raise TestException("Failed to submit user test.")

        return user_test_id

    def get_evaluation_result(self, contest_id, submission_id, timeout=60):
        browser = self.get_aws_browser()
        sleep_interval = 0.1
        while timeout > 0:
            timeout -= sleep_interval

            sr = AWSSubmissionViewRequest(browser,
                                          submission_id,
                                          base_url=self.AWS_BASE_URL)
            sr.execute()

            result = sr.get_submission_info()
            status = result['status']

            if self.COMPLETED_STATUSES.search(status):
                return result

            if self.WAITING_STATUSES.search(status):
                time.sleep(sleep_interval)
                continue

            raise TestException("Unknown submission status: %s" % status)

        raise TestException("Waited too long for submission result.")

    def get_user_test_result(self, contest_id, user_test_id, timeout=60):
        browser = self.get_aws_browser()
        sleep_interval = 0.1
        while timeout > 0:
            timeout -= sleep_interval

            sr = AWSUserTestViewRequest(browser,
                                        user_test_id,
                                        base_url=self.AWS_BASE_URL)
            sr.execute()

            result = sr.get_user_test_info()
            status = result['status']

            if self.COMPLETED_STATUSES_USER_TEST.search(status):
                return result

            if self.WAITING_STATUSES_USER_TEST.search(status):
                time.sleep(sleep_interval)
                continue

            raise TestException("Unknown user test status: %s" % status)

        raise TestException("Waited too long for user test result.")
