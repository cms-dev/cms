#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2016 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

import logging
import os
import random
import re
import tempfile
from urllib.parse import parse_qs, urlsplit

from cms import config
from cms.grading.languagemanager import filename_to_language
from cmscommon.crypto import decrypt_number
from cmstestsuite.web import GenericRequest, LoginRequest


logger = logging.getLogger(__name__)


class CWSLoginRequest(LoginRequest):
    def test_success(self):
        if not LoginRequest.test_success(self):
            return False
        if self.redirected_to.rstrip("/") != self.base_url.rstrip("/"):
            return False
        return True


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


class TaskRequest(GenericRequest):
    """Load a task page in CWS.

    """
    def __init__(self, browser, task_id, base_url=None):
        GenericRequest.__init__(self, browser, base_url)
        self.url = "%s/tasks/%s/description" % (self.base_url, task_id)
        self.task_id = task_id

    def describe(self):
        return "load page for task %s (%s)" % (self.task_id, self.url)


class TaskStatementRequest(GenericRequest):
    """Load a task statement in CWS.

    """
    def __init__(self, browser, task_id, language_code, base_url=None):
        GenericRequest.__init__(self, browser, base_url)
        self.url = "%s/tasks/%s/statements/%s" % (self.base_url,
                                                  task_id, language_code)
        self.task_id = task_id

    def describe(self):
        return "load statement for task %s (%s)" % (self.task_id, self.url)

    def specific_info(self):
        return '\nNO DATA DUMP FOR TASK STATEMENTS\n'


class SubmitRequest(GenericRequest):
    """Submit a solution in CWS.

    """
    def __init__(self, browser, task, submission_format,
                 filenames, language=None, base_url=None):
        GenericRequest.__init__(self, browser, base_url)
        self.url = "%s/tasks/%s/submit" % (self.base_url, task[1])
        self.task = task
        self.submission_format = submission_format
        self.filenames = filenames
        self.data = {}
        # If not passed, try to recover the language from the filenames.
        if language is None:
            for filename in filenames:
                lang = filename_to_language(filename)
                if lang is not None:
                    language = lang.name
                    break
        # Only send the language in the request if not None.
        if language is not None:
            self.data = {"language": language}

    def _prepare(self):
        GenericRequest._prepare(self)
        self.files = list(zip(self.submission_format, self.filenames))

    def describe(self):
        return "submit sources %s for task %s (ID %d) %s" % \
            (repr(self.filenames), self.task[1], self.task[0], self.url)

    def specific_info(self):
        return 'Task: %s (ID %d)\nFile: %s\n' % \
            (self.task[1], self.task[0], repr(self.filenames)) + \
            GenericRequest.specific_info(self)

    def test_success(self):
        if not GenericRequest.test_success(self):
            return False

        return self.get_submission_id() is not None

    def get_submission_id(self):
        # Only valid after self.execute()
        # Parse submission ID out of redirect.
        if self.redirected_to is None:
            return None

        query = parse_qs(urlsplit(self.redirected_to).query)
        if "submission_id" not in query or len(query["submission_id"]) != 1:
            logger.warning("Redirected to an unexpected page: `%s'",
                           self.redirected_to)
            return None
        try:
            submission_id = decrypt_number(query["submission_id"][0],
                                           config.secret_key)
        except Exception:
            logger.warning("Unable to decrypt submission id from page: `%s'",
                           self.redirected_to)
            return None
        return submission_id


class SubmitUserTestRequest(GenericRequest):
    """Submit a user test in CWS."""
    def __init__(self, browser, task, submission_format,
                 filenames, language=None, base_url=None):
        GenericRequest.__init__(self, browser, base_url)
        self.url = "%s/tasks/%s/test" % (self.base_url, task[1])
        self.task = task
        self.submission_format = submission_format
        self.filenames = filenames
        self.data = {}
        # If not passed, try to recover the language from the filenames.
        if language is None:
            for filename in filenames:
                lang = filename_to_language(filename)
                if lang is not None:
                    language = lang.name
                    break
        # Only send the language in the request if not None.
        if language is not None:
            self.data = {"language": language}

    def _prepare(self):
        GenericRequest._prepare(self)
        # Let's generate an arbitrary input file.
        # TODO: delete this file once we're done with it.
        _, temp_filename = tempfile.mkstemp()
        self.files = \
            list(zip(self.submission_format, self.filenames)) + \
            [("input", temp_filename)]

    def describe(self):
        return "submit user test %s for task %s (ID %d) %s" % \
            (repr(self.filenames), self.task[1], self.task[0], self.url)

    def specific_info(self):
        return 'Task: %s (ID %d)\nFile: %s\n' % \
            (self.task[1], self.task[0], repr(self.filenames)) + \
            GenericRequest.specific_info(self)

    def test_success(self):
        if not GenericRequest.test_success(self):
            return False

        return self.get_user_test_id() is not None

    def get_user_test_id(self):
        # Only valid after self.execute()
        # Parse submission ID out of redirect.
        if self.redirected_to is None:
            return None

        query = parse_qs(urlsplit(self.redirected_to).query)
        if "user_test_id" not in query or len(query["user_test_id"]) != 1:
            logger.warning("Redirected to an unexpected page: `%s'",
                           self.redirected_to)
            return None
        try:
            user_test_id = decrypt_number(query["user_test_id"][0],
                                          config.secret_key)
        except Exception:
            logger.warning("Unable to decrypt user test id from page: `%s'",
                           self.redirected_to)
            return None
        return user_test_id


class TokenRequest(GenericRequest):
    """Release test a submission.

    """
    def __init__(self, browser, task, submission_num, base_url=None):
        GenericRequest.__init__(self, browser, base_url)
        self.url = "%s/tasks/%s/submissions/%s/token" % (self.base_url,
                                                         task[1],
                                                         submission_num)
        self.task = task
        self.submission_num = submission_num
        self.data = {}

    def describe(self):
        return "release test the %s-th submission for task %s (ID %d)" % \
            (self.submission_num, self.task[1], self.task[0])

    def specific_info(self):
        return 'Task: %s (ID %d)\nSubmission: %s\n' % \
            (self.task[1], self.task[0], self.submission_num) + \
            GenericRequest.specific_info(self)


class SubmitRandomRequest(GenericRequest):
    """Submit a solution in CWS.

    """
    def __init__(self, browser, task, base_url=None,
                 submissions_path=None):
        GenericRequest.__init__(self, browser, base_url)
        self.url = "%s/tasks/%s/submit" % (self.base_url, task[1])
        self.task = task
        self.submissions_path = submissions_path
        self.data = {}

    def _prepare(self):
        """Select a random solution and prepare it for submission.

        If task/ is the task directory, it might contain files (only
        if the submission format is with a single file) and
        directory. If it contains a file, it is assumed that it is the
        only element in the submission format, and is the basename
        without extension of the file. If it is a directory, all files
        inside are assumed to be part of the submission format with
        their basenames without extension.

        """
        GenericRequest._prepare(self)

        # Select a random directory or file inside the task directory.
        task_path = os.path.join(self.submissions_path, self.task[1])
        sources = os.listdir(task_path)
        source = random.choice(sources)
        lang = filename_to_language(source)
        if lang is not None:
            self.data["language"] = lang.name
        self.source_path = os.path.join(task_path, source)

        # Compose the submission format
        self.files = []
        if os.path.isdir(self.source_path):
            submission_formats = os.listdir(self.source_path)
            self.files = [('%s.%%l' % (os.path.splitext(sf)[0]),
                           os.path.join(self.source_path, sf))
                          for sf in submission_formats]
        else:
            submission_format = os.path.splitext(source)[0]
            self.files = [('%s.%%l' % (submission_format), self.source_path)]

    def describe(self):
        return "submit source %s for task %s (ID %d) %s" % \
            (self.source_path, self.task[1], self.task[0], self.url)

    def specific_info(self):
        return 'Task: %s (ID %d)\nFile: %s\n' % \
            (self.task[1], self.task[0], self.source_path) + \
            GenericRequest.specific_info(self)
