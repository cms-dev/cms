#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2012 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2016 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
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

import datetime
import sys
import time
import traceback

import requests


debug = False


class Browser:
    def __init__(self):
        self.xsrf_token = None
        self.session = requests.Session()

    def read_xsrf_token(self, url):
        self.session.get(url)
        for cookie in self.session.cookies:
            if cookie.name == "_xsrf":
                self.xsrf_token = cookie.value

    def login(self, login_request):
        self.read_xsrf_token(login_request.base_url)
        login_request.execute()

    def do_request(self, url, data=None, file_names=None):
        """Open an URL, optionally passing the specified data and files as
           POST arguments.

        url (string): the URL to open.
        data (dict): a dictionary of parameters to pass as POST
            arguments.
        file_names ([(str, str)]): a list of files to pass as POST
            arguments. Each entry is a tuple containing two strings:
            the field name and the name of the file to send.

        """
        if file_names is None:
            if data is None:
                response = self.session.get(url)
            else:
                data = data.copy()
                data['_xsrf'] = self.xsrf_token
                response = self.session.post(url, data)
        else:
            file_objs = {}
            try:
                data = data.copy()
                data['_xsrf'] = self.xsrf_token
                for k, v in file_names:
                    file_objs[k] = open(v, "rb")
                response = self.session.post(url, data, files=file_objs)
            finally:
                for fobj in file_objs.values():
                    fobj.close()
        return response


class GenericRequest:
    """Request to a server.

    """

    OUTCOME_SUCCESS = 'success'
    OUTCOME_FAILURE = 'failure'
    OUTCOME_UNDECIDED = 'undecided'
    OUTCOME_ERROR = 'error'

    MINIMUM_LENGTH = 100

    def __init__(self, browser, base_url=None):
        if base_url is None:
            base_url = 'http://localhost:8888/'
        self.browser = browser
        self.base_url = base_url
        self.outcome = None

        self.start_time = None
        self.stop_time = None
        self.duration = None
        self.exc_value = None
        self.exc_traceback = None

        self.url = None
        self.data = None
        self.files = None

        self.status_code = None
        self.response = None
        self.res_data = None
        self.redirected_to = None

    def execute(self):
        """Main entry point to execute the test"""
        self._prepare()
        self._execute()

    def _prepare(self):
        """Optional convenience hook called just after creating the Request"""
        pass

    def _execute(self):
        """Execute the test"""
        description = self.describe()
        self.start_time = time.time()
        try:
            self.response = self.browser.do_request(
                self.url, self.data, self.files)
            self.response.raise_for_status()

            self.status_code = self.response.status_code
            self.res_data = self.response.text

            if self.response.history:
                self.redirected_to = self.response.url

        # Catch possible exceptions
        except Exception as exc:
            self.exc_value = exc
            self.exc_traceback = traceback.format_exc()
            self.outcome = GenericRequest.OUTCOME_ERROR

        else:
            self.outcome = None

        finally:
            self.stop_time = time.time()
            self.duration = self.stop_time - self.start_time

        success = None
        try:
            success = self.test_success()
        except Exception as exc:
            self.exc_value = exc
            self.exc_traceback = traceback.format_exc()
            self.outcome = GenericRequest.OUTCOME_ERROR

        # If no exceptions were casted, decode the test evaluation
        if self.outcome is None:

            # Could not decide on the evaluation
            if success is None:
                if debug:
                    print("Could not determine status for request '%s'" %
                          (description), file=sys.stderr)
                self.outcome = GenericRequest.OUTCOME_UNDECIDED

            # Success
            elif success:
                if debug:
                    print("Request '%s' successfully completed in %.3fs" %
                          (description, self.duration), file=sys.stderr)
                self.outcome = GenericRequest.OUTCOME_SUCCESS

            # Failure
            elif not success:
                if debug:
                    print("Request '%s' failed" % (description),
                          file=sys.stderr)
                self.outcome = GenericRequest.OUTCOME_FAILURE

        # Otherwise report the exception
        else:
            print("Request '%s' terminated with an exception: %s\n%s" %
                  (description, self.exc_value, self.exc_traceback),
                  file=sys.stderr)

    def test_success(self):
        if self.status_code not in [200, 302]:
            return False
        if self.status_code == 200 and self.res_data is None:
            return False
        if self.status_code == 200 and \
                len(self.res_data) < GenericRequest.MINIMUM_LENGTH:
            return False
        return True

    def specific_info(self):
        res = "URL: %s\n" % self.url
        if self.response is not None:
            res += "\nREQUEST HEADERS\n"
            for key, value in self.response.request.headers.items():
                res += "%s: %s\n" % (key, value)
            res += "\nREQUEST DATA\n%s\n" % self.response.request.body
        else:
            res += "\nNO REQUEST INFORMATION AVAILABLE\n"
        if self.res_data is not None:
            res += "\nRESPONSE HEADERS\n"
            for key, value in self.response.headers.items():
                res += "%s: %s\n" % (key, value)
            res += "\nRESPONSE DATA\n%s\n" % (self.res_data)
        else:
            res += "\nNO RESPONSE INFORMATION AVAILABLE\n"
        return res

    def describe(self):
        raise NotImplementedError("Please subclass this class "
                                  "and actually implement some request")

    def store_to_file(self, fd):
        print("Test type: %s" % (self.__class__.__name__), file=fd)
        print("Execution start time: %s" %
              (datetime.datetime.fromtimestamp(self.start_time).
               strftime("%d/%m/%Y %H:%M:%S.%f")), file=fd)
        print("Execution stop time: %s" %
              (datetime.datetime.fromtimestamp(self.stop_time).
               strftime("%d/%m/%Y %H:%M:%S.%f")), file=fd)
        print("Duration: %f seconds" % (self.duration), file=fd)
        print("Outcome: %s" % (self.outcome), file=fd)
        fd.write(self.specific_info())
        if self.exc_traceback is not None:
            print("", file=fd)
            print("EXCEPTION CASTED", file=fd)
            fd.write(str(self.exc_traceback))


class LoginRequest(GenericRequest):
    """Try to login to CWS or AWS with the given credentials.

    """
    def __init__(self, browser, username, password, base_url=None):
        GenericRequest.__init__(self, browser, base_url)
        self.username = username
        self.password = password
        self.url = '%s/login' % self.base_url
        self.data = {'username': self.username,
                     'password': self.password}

    def describe(self):
        return "try to login"

    def test_success(self):
        if not GenericRequest.test_success(self):
            return False
        # Additional checks need to be done by the subclasses.
        return True

    def specific_info(self):
        return 'Username: %s\nPassword: %s\n' % \
               (self.username, self.password) + \
            GenericRequest.specific_info(self)
