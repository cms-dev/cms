#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2012 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2013-2016 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2013-2016 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Luca Versari <veluca93@gmail.com>
# Copyright © 2014 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2016 Peyman Jabbarzade Ganje <peyman.jabarzade@gmail.com>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import io
import json
import logging
import os
import re
import subprocess
import sys
import time

import requests

from cmstestsuite.web import Browser
from cmstestsuite.web.AWSRequests import \
    AWSLoginRequest, AWSSubmissionViewRequest, AWSUserTestViewRequest
from cmstestsuite.web.CWSRequests import \
    CWSLoginRequest, SubmitRequest, SubmitUserTestRequest


logger = logging.getLogger(__name__)


# CONFIG is populated by our test script.
CONFIG = {
    'VERBOSITY': 0,
}


# cms_config holds the decoded-JSON of the cms.conf configuration file.
cms_config = None


# List of users and tasks we created as part of the test.
created_users = {}
created_tasks = {}


# Information on the administrator running the tests.
admin_info = {}


# Base URLs for AWS and CWS
AWS_BASE_URL = "http://localhost:8889/"
CWS_BASE_URL = "http://localhost:8888/"


# Persistent browsers to access AWS and CWS.
aws_browser = None
cws_browser = None


def get_aws_browser():
    global aws_browser
    if aws_browser is None:
        aws_browser = Browser()

        lr = AWSLoginRequest(aws_browser,
                             admin_info["username"], admin_info["password"],
                             base_url=AWS_BASE_URL)
        aws_browser.login(lr)
    return aws_browser


def get_cws_browser(user_id):
    global cws_browser
    if cws_browser is None:
        cws_browser = Browser()
        username = created_users[user_id]['username']
        password = created_users[user_id]['password']
        lr = CWSLoginRequest(
            cws_browser, username, password, base_url=CWS_BASE_URL)
        cws_browser.login(lr)
    return cws_browser


class FrameworkException(Exception):
    pass


def read_cms_config():
    global cms_config
    with io.open("%(CONFIG_PATH)s" % CONFIG, "rt") as f:
        cms_config = json.load(f)


def get_cms_config():
    if cms_config is None:
        read_cms_config()
    return cms_config


def sh(cmdline, ignore_failure=False):
    """Execute a simple shell command.

    If cmdline is a string, it is passed to sh -c verbatim.  All escaping must
    be performed by the user. If cmdline is an array, then no escaping is
    required.

    """
    if CONFIG["VERBOSITY"] >= 1:
        # TODO Use shlex.quote in Python 3.3.
        logger.info('$ ' + ' '.join(cmdline))
    kwargs = dict()
    if CONFIG["VERBOSITY"] >= 3:
        # TODO Use subprocess.DEVNULL in Python 3.3.
        kwargs["stdout"] = io.open(os.devnull, "wb")
        kwargs["stderr"] = subprocess.STDOUT
    ret = subprocess.call(cmdline, **kwargs)
    if not ignore_failure and ret != 0:
        raise FrameworkException(
            # TODO Use shlex.quote in Python 3.3.
            "Execution failed with %d/%d. Tried to execute:\n%s\n" %
            (ret & 0xff, ret >> 8, ' '.join(cmdline)))


def configure_cms(options):
    """Creates the cms.conf file, setting any parameters as requested.

    The parameters are substituted in textually, and thus this may be
    quite fragile.

    options (dict): mapping from parameter to textual JSON argument.

    """
    with io.open("%(TEST_DIR)s/config/cms.conf.sample" % CONFIG,
                 "rt", encoding="utf-8") as in_f:
        lines = in_f.readlines()

    unset = set(options.keys())
    for i, line in enumerate(lines):
        g = re.match(r'^(\s*)"([^"]+)":', line)
        if g:
            whitespace, key = g.groups()
            if key in unset:
                lines[i] = '%s"%s": %s,\n' % (whitespace, key, options[key])
                unset.remove(key)

    with io.open("%(CONFIG_PATH)s" % CONFIG, "wt", encoding="utf-8") as out_f:
        for l in lines:
            out_f.write(l)

    if unset:
        print("These configuration items were not set:")
        print("  " + ", ".join(sorted(list(unset))))

    # Load the config database.
    read_cms_config()


def combine_coverage():
    logger.info("Combining coverage results.")
    sh([sys.executable, "-m", "coverage", "combine"])


def initialize_aws(rand):
    """Create an admin and logs in

    rand (int): some random bit to add to the admin username.

    """
    logger.info("Creating admin...")
    admin_info["username"] = "admin%s" % rand
    admin_info["password"] = "adminpwd"
    sh([sys.executable, "cmscontrib/AddAdmin.py", "%(username)s" % admin_info,
        "-p", "%(password)s" % admin_info])


def admin_req(path, args=None, files=None):
    browser = get_aws_browser()
    return browser.do_request(AWS_BASE_URL + path, args, files)


def get_tasks():
    '''Return a list of existing tasks, returned as a dictionary of
      'taskname' => { 'id': ..., 'title': ... }

    '''
    r = admin_req('tasks')
    groups = re.findall(r'''
        <tr>\s*
        <td><a\s+href="./task/(\d+)">(.*)</a></td>\s*
        <td>(.*)</td>\s*
        ''', r.text, re.X)
    tasks = {}
    for g in groups:
        id, name, title = g
        id = int(id)
        tasks[name] = {
            'title': title,
            'id': id,
        }

    return tasks


def get_users(contest_id):
    '''Return a list of existing users, returned as a dictionary of
      'username' => { 'id': ..., 'firstname': ..., 'lastname': ... }

    '''
    r = admin_req('contest/' + str(contest_id) + '/users')
    groups = re.findall(r'''
        <tr> \s*
        <td> \s* (.*) \s* </td> \s*
        <td> \s* (.*) \s* </td> \s*
        <td><a\s+href="./user/(\d+)">(.*)</a></td>
    ''', r.text, re.X)
    users = {}
    for g in groups:
        firstname, lastname, id, username = g
        id = int(id)
        users[username] = {
            'firstname': firstname,
            'lastname': lastname,
            'id': id,
        }

    return users


def add_contest(**kwargs):
    add_args = {
        "name": kwargs.get('name'),
        "description": kwargs.get('description'),
    }
    resp = admin_req('contests/add', args=add_args)
    # Contest ID is returned as HTTP response.
    page = resp.text
    match = re.search(
        r'<form enctype="multipart/form-data" action="../contest/([0-9]+)" '
        'method="POST" name="edit_contest" style="display:inline;">',
        page)
    if match is not None:
        contest_id = int(match.groups()[0])
        admin_req('contest/%s' % contest_id, args=kwargs)
        return contest_id
    else:
        raise FrameworkException("Unable to create contest.")


def add_task(**kwargs):
    add_args = {
        "name": kwargs.get('name'),
        "title": kwargs.get('title'),
    }
    r = admin_req('tasks/add', args=add_args)
    response = r.text
    match_task_id = re.search(r'/task/([0-9]+)$', r.url)
    match_dataset_id = re.search(r'/dataset/([0-9]+)', response)
    if match_task_id and match_dataset_id:
        task_id = int(match_task_id.group(1))
        dataset_id = int(match_dataset_id.group(1))
        edit_args = {}
        for k, v in kwargs.iteritems():
            edit_args[k.replace("{{dataset_id}}", str(dataset_id))] = v
        r = admin_req('task/%s' % task_id, args=edit_args)
        created_tasks[task_id] = kwargs
    else:
        raise FrameworkException("Unable to create task.")

    r = admin_req('contest/' + kwargs["contest_id"] + '/tasks/add',
                  args={"task_id": str(task_id)})
    g = re.search('<input type="radio" name="task_id" value="' +
                  str(task_id) + '"/>', r.text)
    if g:
        return task_id
    else:
        raise FrameworkException("Unable to assign task to contest.")


def add_manager(task_id, manager):
    args = {}
    files = [
        ('manager', manager),
    ]
    dataset_id = get_task_active_dataset_id(task_id)
    admin_req('dataset/%d/managers/add' % dataset_id, files=files, args=args)


def get_task_active_dataset_id(task_id):
    resp = admin_req('task/%d' % task_id)
    page = resp.text
    match = re.search(
        r'id="title_dataset_([0-9]+).* \(Live\)</',
        page)
    if match is None:
        raise FrameworkException("Unable to create contest.")
    dataset_id = int(match.groups()[0])
    return dataset_id


def add_testcase(task_id, num, input_file, output_file, public):
    files = [
        ('input', input_file),
        ('output', output_file),
    ]
    args = {}
    args["codename"] = "%03d" % num
    if public:
        args['public'] = '1'
    dataset_id = get_task_active_dataset_id(task_id)
    admin_req('dataset/%d/testcases/add' % dataset_id, files=files, args=args)


def add_user(**kwargs):
    r = admin_req('users/add', args=kwargs)
    g = re.search(r'/user/([0-9]+)$', r.url)
    if g:
        user_id = int(g.group(1))
        created_users[user_id] = kwargs
    else:
        raise FrameworkException("Unable to create user.")

    kwargs["user_id"] = user_id
    r = admin_req('contest/' + kwargs["contest_id"] + '/users/add',
                  args=kwargs)
    g = re.search('<input type="radio" name="user_id" value="' +
                  str(user_id) + '"/>', r.text)
    if g:
        return user_id
    else:
        raise FrameworkException("Unable to create participation.")


def add_existing_task(task_id, **kwargs):
    '''Add information about an existing task to our database so that we can
    use it for submitting later.'''
    created_tasks[task_id] = kwargs


def add_existing_user(user_id, **kwargs):
    '''Add information about an existing user to our database so that we can
    use it for submitting later.'''
    created_users[user_id] = kwargs


def cws_submit(contest_id, task_id, user_id, submission_format,
               filenames, language):
    task = (task_id, created_tasks[task_id]['name'])

    browser = get_cws_browser(user_id)
    sr = SubmitRequest(browser, task, base_url=CWS_BASE_URL,
                       submission_format=submission_format,
                       filenames=filenames, language=language)
    sr.execute()
    submission_id = sr.get_submission_id()

    if submission_id is None:
        raise FrameworkException("Failed to submit solution.")

    return submission_id


def cws_submit_user_test(contest_id, task_id, user_id, submission_format,
                         filenames, language):
    task = (task_id, created_tasks[task_id]['name'])

    browser = get_cws_browser(user_id)
    sr = SubmitUserTestRequest(
        browser, task, base_url=CWS_BASE_URL,
        submission_format=submission_format,
        filenames=filenames)
    sr.execute()
    user_test_id = sr.get_user_test_id()

    if user_test_id is None:
        raise FrameworkException("Failed to submit user test.")

    return user_test_id


def get_evaluation_result(contest_id, submission_id, timeout=60):
    WAITING_STATUSES = re.compile(
        r'Compiling\.\.\.|Evaluating\.\.\.|Scoring\.\.\.|Evaluated')
    COMPLETED_STATUS = re.compile(
        r'Compilation failed|Evaluated \(|Scored \(')

    browser = get_aws_browser()
    sleep_interval = 0.1
    while timeout > 0:
        timeout -= sleep_interval

        sr = AWSSubmissionViewRequest(browser,
                                      submission_id,
                                      base_url=AWS_BASE_URL)
        sr.execute()

        result = sr.get_submission_info()
        status = result['status']

        if COMPLETED_STATUS.search(status):
            return result

        if WAITING_STATUSES.search(status):
            time.sleep(sleep_interval)
            continue

        raise FrameworkException("Unknown submission status: %s" % status)

    raise FrameworkException("Waited too long for submission result.")


def get_user_test_result(contest_id, user_test_id, timeout=60):
    WAITING_STATUSES = re.compile(
        r'Compiling\.\.\.|Evaluating\.\.\.')
    COMPLETED_STATUS = re.compile(
        r'Compilation failed|Evaluated')

    browser = get_aws_browser()
    sleep_interval = 0.1
    while timeout > 0:
        timeout -= sleep_interval

        sr = AWSUserTestViewRequest(browser,
                                    user_test_id,
                                    base_url=AWS_BASE_URL)
        sr.execute()

        result = sr.get_user_test_info()
        status = result['status']

        if COMPLETED_STATUS.search(status):
            return result

        if WAITING_STATUSES.search(status):
            time.sleep(sleep_interval)
            continue

        raise FrameworkException("Unknown user test status: %s" % status)

    raise FrameworkException("Waited too long for user test result.")
