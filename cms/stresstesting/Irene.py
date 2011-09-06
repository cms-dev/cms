#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2011 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2011 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2011 Matteo Boscariol <boscarim@hotmail.com>
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
import urllib
import urllib2
import cookielib
import mechanize
import threading
import optparse
import random
import time
import re
import email.mime.multipart
import email.mime.nonmultipart

from cms.db.SQLAlchemyAll import Contest, SessionGen


def urlencode(data):
    """Encode a dictionary as its elements were the data of a HTML
    form passed to the server.

    data (dict): the dictionary to encode.
    return (string): the encoded dictionary.

    """
    msg = email.mime.multipart.MIMEMultipart('form-data')
    for key, value in data.iteritems():
        elem = email.mime.nonmultipart.MIMENonMultipart('text', 'plain')
        elem.add_header('Contest-Disposition', 'form-data; name="%s"' % (key))
        elem.set_payload(value)
        msg.attach(elem)
    return msg


class HTTPHelper:
    """A class to emulate a browser's behaviour: for example, cookies
    get automatically accepted, stored and sent with subsequent
    requests.

    """
    def __init__(self):
        self.cookies = cookielib.CookieJar()
        self.opener = urllib2.build_opener(
            urllib2.HTTPCookieProcessor(self.cookies))

    def do_request(self, url, data=None):
        """Request the specified URL.

        url (string): the URL to request; the protocol is detected
        from the URL.
        data (dict): the data to sent with the URL; used when an
                     HTTP(S) request is performed: if data is None, a
                     plain GET request is performed. Otherwise a POST
                     request is performed, with the attached data.
        returns: the response; it is a file-like objects that the
                 consumer can read; is also supports other methods,
                 described in the documentation of urllib2.urlopen().

        """
        if data is None:
            request = urllib2.Request(url)
        else:
            request = urllib2.Request(url, urllib.urlencode(data))
        response = self.opener.open(request)
        return response


class TestRequest:
    """Docstring TODO.

    """
    def __init__(self, browser, base_url=None):
        if base_url is None:
            base_url = 'http://localhost:8888/'
        self.browser = browser
        self.base_url = base_url

    def execute(self):
        #print >> sys.stderr, "Cookies before execution:"
        #for cookie in self.http_helper.cookies:
        #    print >> sys.stderr, "  " + repr(cookie)
        self.do_request()
        #print >> sys.stderr, "Cookies after execution:"
        #for cookie in self.http_helper.cookies:
        #    print >> sys.stderr, "  " + repr(cookie)
        success = self.test_success()
        description = self.describe()
        if success:
            print >> sys.stderr, "Request %s " \
                  "successfully completed" % description
        elif not success:
            print >> sys.stderr, "Fail when requesting %s" % description

    def describe(self):
        raise NotImplementedError("Please subclass this class "
                                  "and actually implement some request")

    def do_request(self):
        raise NotImplementedError("Please subclass this class "
                                  "and actually implement some request")

    def test_success(self):
        raise NotImplementedError("Please subclass this class "
                                  "and actually implement some request")


class GenericRequest(TestRequest):
    """Docstring TODO.

    """
    MINIMUM_LENGTH = 100

    def __init__(self, browser, base_url=None):
        TestRequest.__init__(self, browser, base_url)
        self.url = None
        self.data = None

    def do_request(self):
        if self.data is None:
            self.response = self.browser.open(self.url)
        else:
            self.response = self.browser.open(self.url,
                                              urllib.urlencode(self.data))
        self.res_data = self.response.read()

    def test_success(self):
        #if self.response.getcode() != 200:
        #    return False
        if len(self.res_data) < GenericRequest.MINIMUM_LENGTH:
            return False
        return True


class HomepageRequest(GenericRequest):
    """Load the main page of CWS.

    """
    def __init__(self, http_helper, username, loggedin, base_url=None):
        GenericRequest.__init__(self, http_helper, base_url)
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
    def __init__(self, http_helper, username, password, base_url=None):
        TestRequest.__init__(self, http_helper, base_url)
        self.username = username
        self.password = password
        self.url = self.base_url + 'login'
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


class ActorDying(Exception):
    """Exception to be raised when an Actor is going to die soon. See
    Actor class.

    """
    pass


class Actor(threading.Thread):
    """Class that simulates the behaviour of a user of the system. It
    performs some requests at randomized times (checking CMS pages,
    doing submissions, ...), checking for their success or failure.

    The probability that the users doing actions depends on the value
    specified in an object called "metrics".

    """

    def __init__(self, username, password, metrics):
        threading.Thread.__init__(self)

        self.username = username
        self.password = password
        self.metric = metrics

        self.name = "Actor thread for user %s" % (self.username)

        self.browser = mechanize.Browser()
        self.die = False

    def run(self):
        try:
            print >> sys.stderr, "Starting actor for user %s" % (self.username)
            self.do_step(HomepageRequest(self.browser,
                                         self.username,
                                         loggedin=False))
            self.do_step(LoginRequest(self.browser,
                                      self.username,
                                      self.password))
            self.do_step(HomepageRequest(self.browser,
                                         self.username,
                                         loggedin=True))
        except ActorDying:
            print >> sys.stderr, "Actor dying for user %s" % (self.username)

    def do_step(self, request):
        self.wait_next()
        if self.die:
            raise ActorDying()
        request.execute()

    def wait_next(self):
        """Wait some time. At the moment it waits c*X seconds, where c
        is the time_coeff parameter in metrics and X is an
        exponentially distributed random variable, with parameter
        time_lambda in metrics.

        """
        time_to_wait = self.metric['time_coeff'] * \
                       random.expovariate(self.metric['time_lambda'])
        time.sleep(time_to_wait)


def harvest_user_data(contest_id):
    """Retrieve the couples username, password for a given contest.

    contest_id (int): the id of the contest we want.
    return (dict): a dictionary mapping usernames to passwords.

    """
    users = {}
    with SessionGen() as session:
        c = Contest.get_from_id(contest_id, session)
        for u in c.users:
            users[u.username] = {'password': u.password}
    return users


DEFAULT_METRICS = {'time_coeff':  1.0,
                   'time_lambda': 2.0}


def main():
    parser = optparse.OptionParser(usage="usage: %prog [options]")
    parser.add_option("-c", "--contest",
                      help="contest ID to export", dest="contest_id",
                      action="store", type="int", default=None)
    parser.add_option("-n", "--actor-num",
                      help="the number of actors to spawn", dest="actor_num",
                      action="store", type="int", default=None)
    options = parser.parse_args()[0]

    if options.actor_num is None:
        users = harvest_user_data(options.contest_id)
    else:
        user_items = harvest_user_data(options.contest_id).items()
        random.shuffle(user_items)
        users = dict(user_items[:options.actor_num])

    actors = [Actor(username, data['password'], DEFAULT_METRICS)
              for username, data in users.iteritems()]
    for a in actors:
        a.start()

if __name__ == '__main__':
    main()
