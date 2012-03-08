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

import sys
import time
import re
import urllib
import datetime
import traceback
import codecs
import os
import random
import email
import mimetypes

from cms.server import encrypt_number
from mechanize import HTMLForm

utf8_decoder = codecs.getdecoder('utf-8')


def format_multipart_formdata(data, files):
    """Format some data and files so they can be sent inside a POST
    request with Content-type multipart/form-data.

    data (dict): a dictionary of parameters to pass as POST arguments.
    files (list): a list of files to pass as POST arguments. Each
                  entry is a tuple containing two strings: the field
                  name and the file name to send.

    """
    formdata = email.mime.Multipart.MIMEMultipart('form-data')
    for key, value in data.iteritems():
        part = email.mime.Text.MIMEText(value)
        part.add_header('Content-Disposition', 'form-data; name="%s"' % (key))
        part._headers = filter(lambda (key, value):
                                   key.lower() != 'mime-version',
                               part._headers)
        formdata.attach(part)

    for key, filename in files:
        type_, encoding = mimetypes.guess_type(filename)
        if type_ is None:
            type_ = 'application/octet-stream'
        type2 = type_.split('/', 1)
        if type2[0] == 'text':
            with codecs.open(filename, 'r', encoding='utf-8') as fd:
                part = email.mime.Text.MIMEText(fd.read(),
                                                _subtype=type2[1],
                                                _charset='UTF-8')
        else:
            part = email.mime.Base.MIMEBase(type2[0], type2[1])
            with open(filename, 'rb') as fd:
                part.set_payload(fd.read())
            email.Encoders.encode_base64(part)
        part.add_header('Content-Disposition',
                        'form-data; name="%s"; filename="%s"' % \
                            (key, filename))
        part._headers = filter(lambda (key, value):
                                   key.lower() != 'mime-version',
                               part._headers)
        formdata.attach(part)

    # Unfortunately we have to remove the first header lines
    lines = formdata.as_string(unixfrom=False).split('\n')
    empty_idx = lines.index('')
    lines = lines[empty_idx + 1:]

    return '\r\n'.join(lines), formdata.get_boundary()


def browser_do_request(browser, url, data=None, files=None):
    """Open an URL in a mechanize browser, optionally passing the
    specified data and files as POST arguments.

    browser (mechanize.Browser): the browser to use.
    url (string): the URL to open.
    data (dict): a dictionary of parameters to pass as POST arguments.
    files (list): a list of files to pass as POST arguments. Each
                  entry is a tuple containing two strings: the field
                  name and the file name to send.

    """
    if files is None:
        if data is None:
            response = browser.open(url)
        else:
            response = browser.open(url, urllib.urlencode(data))
    else:
        f = files[0]
        browser.form = HTMLForm(url, method='POST', enctype='multipart/form-data', attrs=data)
        browser.form.new_control('file', f[0], {'id': f[0]})
        filename = os.path.basename(f[1])
        browser.form.add_file(open(f[1]), 'text/plain', filename, id=f[0])
        browser.form.set_all_readonly(False)
        browser.form.fixup()
        response = browser.submit()
    return response


class TestRequest:
    """Docstring TODO.

    """

    OUTCOME_SUCCESS = 'success'
    OUTCOME_FAILURE = 'failure'
    OUTCOME_UNDECIDED = 'undecided'
    OUTCOME_ERROR = 'error'

    def __init__(self, browser, base_url=None):
        if base_url is None:
            base_url = 'http://localhost:8888/'
        self.browser = browser
        self.base_url = base_url
        self.outcome = None

        self.start_time = None
        self.stop_time = None
        self.duration = None
        self.exception_data = None

    def execute(self):

        # Execute the test
        description = self.describe()
        self.start_time = time.time()
        try:
            self.do_request()

        # Catch possible exceptions
        except Exception as exc:
            self.exception_data = traceback.format_exc()
            self.outcome = TestRequest.OUTCOME_ERROR

        else:
            self.outcome = None

        finally:
            self.stop_time = time.time()
            self.duration = self.stop_time - self.start_time

        success = None
        try:
            success = self.test_success()
        except Exception as exc:
            self.exception_data = traceback.format_exc()
            self.outcome = TestRequest.OUTCOME_ERROR

        # If no exceptions were casted, decode the test evaluation
        if self.outcome is None:

            # Could not decide on the evaluation
            if success is None:
                print >> sys.stderr, "Could not determine " \
                    "status for request '%s'" % (description)
                self.outcome = TestRequest.OUTCOME_UNDECIDED

            # Success
            elif success:
                print >> sys.stderr, "Request '%s' successfully " \
                    "completed" % (description)
                self.outcome = TestRequest.OUTCOME_SUCCESS

            # Failure
            elif not success:
                print >> sys.stderr, "Request '%s' failed" % (description)
                self.outcome = TestRequest.OUTCOME_FAILURE

        # Otherwise report the exception
        else:
            print >> sys.stderr, "Request '%s' terminated " \
                "with an exception: %s" % (description, repr(exc))

    def describe(self):
        raise NotImplementedError("Please subclass this class "
                                  "and actually implement some request")

    def do_request(self):
        raise NotImplementedError("Please subclass this class "
                                  "and actually implement some request")

    def test_success(self):
        raise NotImplementedError("Please subclass this class "
                                  "and actually implement some request")

    def prepare(self):
        # This is an optional convenience hook called just after
        # creating the Request
        pass

    def store_to_file(self, fd):
        print >> fd, "Test type: %s" % (self.__class__.__name__)
        print >> fd, "Execution start time: %s" % (
            datetime.datetime.fromtimestamp(self.start_time).\
            strftime("%d/%m/%Y %H:%M:%S.%f"))
        print >> fd, "Execution stop time: %s" % (
            datetime.datetime.fromtimestamp(self.stop_time).\
            strftime("%d/%m/%Y %H:%M:%S.%f"))
        print >> fd, "Duration: %f seconds" % (self.duration)
        print >> fd, "Outcome: %s" % (self.outcome)
        fd.write(self.specific_info())
        if self.exception_data is not None:
            print >> fd
            print >> fd, "EXCEPTION CASTED"
            fd.write(self.exception_data)

    def specific_info(self):
        return ''


class GenericRequest(TestRequest):
    """Docstring TODO.

    """
    MINIMUM_LENGTH = 100

    def __init__(self, browser, base_url=None):
        TestRequest.__init__(self, browser, base_url)
        self.url = None
        self.data = None
        self.files = None

        self.response = None
        self.res_data = None

    def do_request(self):
        self.response = browser_do_request(self.browser,
                                           self.url,
                                           self.data,
                                           self.files)
        self.res_data = self.response.read()

        # TODO - We here clear the history, otherwise the memory
        # consumption would explode; maybe it would be better to use a
        # custom History object that just discards the history; on the
        # other hand the History interface is still unstable
        self.browser.clear_history()

    def test_success(self):
        #if self.response.getcode() != 200:
        #    return False
        if self.res_data is None:
            return False
        if len(self.res_data) < GenericRequest.MINIMUM_LENGTH:
            return False
        return True

    def specific_info(self):
        res = "URL: %s\n" % (unicode(self.url))
        if self.browser.request is not None:
            res += "\nREQUEST HEADERS\n"
            for (key, value) in self.browser.request.header_items():
                res += "%s: %s\n" % (key, value)
            if self.browser.request.get_data() is not None:
                res += "\nREQUEST DATA\n%s\n" % \
                    (self.browser.request.get_data())
            else:
                res += "\nNO REQUEST DATA\n"
        else:
            res += "\nNO REQUEST INFORMATION AVAILABLE\n"
        if self.res_data is not None:
            headers = self.browser.response()._headers.items()
            res += "\nRESPONSE HEADERS\n%s" % (
                "".join(["%s: %s\n" % (unicode(header[0]),
                                       unicode(header[1]))
                         for header in headers]))
            res += "\nRESPONSE DATA\n%s\n" % (utf8_decoder(self.res_data)[0])
        else:
            res += "\nNO RESPONSE INFORMATION AVAILABLE\n"
        return res

    def describe(self):
        raise NotImplementedError("Please subclass this class "
                                  "and actually implement some request")


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
        self.url = "%ssubmit/%s" % (self.base_url,
                                    encrypt_number(task[0]))
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
