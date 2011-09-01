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

import os
import sys
import urllib
import urllib2
import cookielib
import threading
import optparse

from cms.db.SQLAlchemyAll import Contest, SessionGen


class HTTPHelper:

    def __init__(self):
        self.cookies = cookielib.CookieJar()
        self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookies))

    def do_request(self, url, data=None):
        if data is None:
            request = urllib2.Request(url)
        else:
            request = urllib2.Request(url, self.encode_post_data(data))
        #self.cookies.add_cookie_header(request)
        response = self.opener.open(request)
        #self.cookies.extract_cookies(response, request)
        return response

    def encode_post_data(self, data):
        return urllib.urlencode(data)

class TestRequest:

    def __init__(self, http_helper, base_url='http://localhost:8888/'):
        self.http_helper = http_helper
        self.base_url = base_url

    def execute(self):
        print >> sys.stderr, "Cookies before execution:"
        for cookie in self.http_helper.cookies:
            print >> sys.stderr, "  " + repr(cookie)
        self.do_request()
        print >> sys.stderr, "Cookies after execution:"
        for cookie in self.http_helper.cookies:
            print >> sys.stderr, "  " + repr(cookie)
        fail = self.test_fail()
        success = self.test_success()
        description = self.describe()
        if fail and not success:
            print >> sys.stderr, "Fail when requesting %s" % (description)
        elif not fail and success:
            print >> sys.stderr, "Request %s successfully completed" % (description)
        elif not fail and not success:
            print >> sys.stderr, "Couldn't decide on request %s" % (description)
        else:
            print >> sys.stderr, "WHAT?! Request %s both failed and succeded!" % (description)

    def describe(self):
        raise NotImplemented("Please subclass this class and actually implement some request")

    def do_request(self):
        raise NotImplemented("Please subclass this class and actually implement some request")

    def test_fail(self):
        raise NotImplemented("Please subclass this class and actually implement some request")

    def test_success(self):
        raise NotImplemented("Please subclass this class and actually implement some request")

class HomepageRequest(TestRequest):

    def __init__(self, http_helper):
        TestRequest.__init__(self, http_helper)

    def describe(self):
        return "check the main page"

    def do_request(self):
        self.response = self.http_helper.do_request(self.base_url)
        self.res_data = self.response.read()

    def test_success(self):
        if self.response.getcode() == 200 and len(self.res_data) >= 10:
            return True
        return False

    def test_fail(self):
        if self.response.getcode() != 200:
            return True
        if len(self.res_data) < 10:
            return True
        return False

class LoginRequest(TestRequest):

    def __init__(self, http_helper, username, password):
        TestRequest.__init__(self, http_helper)
        self.username = username
        self.password = password

    def describe(self):
        return "try to login"

    def do_request(self):
        data = {'username': self.username, 'password': self.password, 'next': '/'}
        self.response = self.http_helper.do_request('%s%s' % (self.base_url, "login"), data)
        self.res_data = self.response.read()

    def test_success(self):
        if self.response.getcode() == 200 and len(self.res_data) >= 10:
            return True
        return False

    def test_fail(self):
        if self.response.getcode() != 200:
            return True
        if len(self.res_data) < 10:
            return True
        return False

class Actor(threading.Thread):

    def __init__(self, username, password, metrics):
        threading.Thread.__init__(self)

        self.username = username
        self.password = password
        self.metric = metrics

        self.http_helper = HTTPHelper()

    def run(self):
        print >> sys.stderr, "Starting actor for user %s" % (self.username)
        request = LoginRequest(self.http_helper, self.username, self.password)
        request.execute()
        request = HomepageRequest(self.http_helper)
        request.execute()

def harvest_user_data(contest_id):
    users = {}
    with SessionGen() as session:
        c = Contest.get_from_id(contest_id, session)
        for u in c.users:
            users[u.username] = {'password': u.password}
    return users

DEFAULT_METRICS = {}

def main():
    parser = optparse.OptionParser(usage="usage: %prog [options]")
    parser.add_option("-c", "--contest", help="contest ID to export",
                      dest="contest_id", action="store", type="int", default=None)
    options, args = parser.parse_args()

    users = dict(harvest_user_data(options.contest_id).items()[:])

    actors = [Actor(username, data['password'], DEFAULT_METRICS) for username, data in users.iteritems()]
    for a in actors:
        a.start()

if __name__ == '__main__':
    main()
