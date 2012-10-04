#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
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

import re
import os
import random
import urlparse

from cmscommon.Cryptographics import encrypt_number, decrypt_number
from cmstestsuite.web import GenericRequest


class HomepageRequest(GenericRequest):
    """Load the main page of CWS.

    """
    def __init__(self, browser, username, loggedin, base_url=None):
        GenericRequest.__init__(self, browser, base_url)
        self.url = self.base_url
        self.username = username
        self.loggedin = loggedin

    def describe(self):
        return "check the main page"

    def test_success(self):
        if not GenericRequest.test_success(self):
            return False
        username_re = re.compile(self.username)
        if self.loggedin:
            if username_re.search(self.res_data) is None:
                return False
        else:
            if username_re.search(self.res_data) is not None:
                return False
        return True


class LoginRequest(GenericRequest):
    """Try to login to CWS with given credentials.

    """
    def __init__(self, browser, username, password, base_url=None):
        GenericRequest.__init__(self, browser, base_url)
        self.username = username
        self.password = password
        self.url = '%slogin' % self.base_url
        self.data = {'username': self.username,
                     'password': self.password,
                     'next': '/'}

    def describe(self):
        return "try to login"

    def test_success(self):
        if not GenericRequest.test_success(self):
            return False
        fail_re = re.compile('Failed to log in.')
        if fail_re.search(self.res_data) is not None:
            return False
        username_re = re.compile(self.username)
        if username_re.search(self.res_data) is None:
            return False
        return True

    def specific_info(self):
        return 'Username: %s\nPassword: %s\n' % \
               (self.username, self.password) + \
            GenericRequest.specific_info(self)


class TaskRequest(GenericRequest):
    """Load a task page in CWS.

    """
    def __init__(self, browser, task_id, base_url=None):
        GenericRequest.__init__(self, browser, base_url)
        self.url = "%stasks/%s" % (self.base_url, encrypt_number(task_id))
        self.task_id = task_id

    def describe(self):
        return "load page for task %s" % (self.task_id)


class TaskStatementRequest(GenericRequest):
    """Load a task statement in CWS.

    """
    def __init__(self, browser, task_id, base_url=None):
        GenericRequest.__init__(self, browser, base_url)
        self.url = "%stasks/%s/statement" % (self.base_url,
                                             encrypt_number(task_id))
        self.task_id = task_id

    def describe(self):
        return "load statement for task %s" % (self.task_id)

    def specific_info(self):
        return '\nNO DATA DUMP FOR TASK STATEMENTS\n'


class SubmitRequest(GenericRequest):
    """Submit a solution in CWS.

    """
    def __init__(self, browser, task, filename, base_url=None):
        GenericRequest.__init__(self, browser, base_url)
        self.url = "%stasks/%s/submit" % (self.base_url, task[1])
        self.task = task
        self.filename = filename
        self.data = {}

    def prepare(self):
        GenericRequest.prepare(self)
        self.files = [('%s.%%l' % (self.task[1]), self.filename)]

    def describe(self):
        return "submit source %s for task %s (ID %d)" % \
            (self.filename, self.task[1], self.task[0])

    def specific_info(self):
        return 'Task: %s (ID %d)\nFile: %s\n' % \
            (self.task[1], self.task[0], self.filename) + \
            GenericRequest.specific_info(self)

    def test_success(self):
        if not GenericRequest.test_success(self):
            return False

        return self.get_submission_id() is not None

    def get_submission_id(self):
        # Only valid after self.execute()
        # Parse submission ID out of response.
        p = self.browser.geturl().split("?")[-1]
        try:
            submission_id = decrypt_number(p)
        except Exception as error:
            return None
        return submission_id


class TokenRequest(GenericRequest):
    """Release test a submission.

    """
    def __init__(self, browser, task, submission_num, base_url=None):
        GenericRequest.__init__(self, browser, base_url)
        self.url = "%stasks/%s/submissions/%s/token" % (self.base_url,
                                                        task[1],
                                                        submission_num)
        self.task = task
        self.submission_num = submission_num
        self.data = {}

    def prepare(self):
        GenericRequest.prepare(self)

    def describe(self):
        return "release test the %s-th submission for task %s (ID %d)" % \
            (self.submission_num, self.task[1], self.task[0])

    def specific_info(self):
        return 'Task: %s (ID %d)\nSubmission: %s\n' % \
            (self.task[1], self.task[0], self.submission_num) + \
            GenericRequest.specific_info(self)

    def test_success(self):
        if not GenericRequest.test_success(self):
            return False

        return True


class SubmitRandomRequest(SubmitRequest):
    """Submit a solution in CWS.

    """
    def __init__(self, browser, task, base_url=None,
                 submissions_path=None):
        GenericRequest.__init__(self, browser, base_url)
        self.url = "%ssubmit/%s" % (self.base_url,
                                    encrypt_number(task[0]))
        self.task = task
        self.submissions_path = submissions_path
        self.data = {}

    def prepare(self):
        GenericRequest.prepare(self)
        task_path = os.path.join(self.submissions_path, self.task[1])
        sources = os.listdir(task_path)
        source = random.choice(sources)
        self.source_path = os.path.join(task_path, source)
        self.files = [('%s.%%l' % (self.task[1]), self.source_path)]

    def describe(self):
        return "submit source %s for task %s (ID %d)" % \
            (self.source_path, self.task[1], self.task[0])

    def specific_info(self):
        return 'Task: %s (ID %d)\nFile: %s\n' % \
            (self.task[1], self.task[0], self.source_path) + \
            GenericRequest.specific_info(self)
