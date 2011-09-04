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
import random
import time

from cms.db.SQLAlchemyAll import Contest, SessionGen


class HTTPHelper:
    """A class to emulate a browser's behaviour: for example, cookies
    get automatically accepted, stored and sent with subsequent
    requests.

    """

    def __init__(self):
        self.cookies = cookielib.CookieJar()
        self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookies))

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

    def __init__(self, http_helper, base_url='http://localhost:8888/'):
        self.http_helper = http_helper
        self.base_url = base_url

    def execute(self):
        #print >> sys.stderr, "Cookies before execution:"
        #for cookie in self.http_helper.cookies:
        #    print >> sys.stderr, "  " + repr(cookie)
        self.do_request()
        #print >> sys.stderr, "Cookies after execution:"
        #for cookie in self.http_helper.cookies:
        #    print >> sys.stderr, "  " + repr(cookie)
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

class ActorDying(Exception):
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

        self.http_helper = HTTPHelper()
        self.die = False

    def run(self):
        try:
            print >> sys.stderr, "Starting actor for user %s" % (self.username)
            self.do_step(LoginRequest(self.http_helper, self.username, self.password))
            self.do_step(HomepageRequest(self.http_helper))
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
        time_to_wait = self.metric['time_coeff'] * random.expovariate(self.metric['time_lambda'])
        time.sleep(time_to_wait)

def harvest_user_data(contest_id):
    users = {}
    with SessionGen() as session:
        c = Contest.get_from_id(contest_id, session)
        for u in c.users:
            users[u.username] = {'password': u.password}
    return users

DEFAULT_METRICS = {'time_coeff':  1.0,
                   'time_lambda': 0.5}

def main():
    parser = optparse.OptionParser(usage="usage: %prog [options]")
    parser.add_option("-c", "--contest", help="contest ID to export",
                      dest="contest_id", action="store", type="int", default=None)
    parser.add_option("-n", "--actor-num", help="the number of actors to spawn",
                      dest="actor_num", action="store", type="int", default=None)
    options, args = parser.parse_args()

    if options.actor_num is None:
        users = harvest_user_data(options.contest_id)
    else:
        user_items = harvest_user_data(options.contest_id).items()
        random.shuffle(user_items)
        users = dict(user_items[:options.actor_num])

    actors = [Actor(username, data['password'], DEFAULT_METRICS) for username, data in users.iteritems()]
    for a in actors:
        a.start()

if __name__ == '__main__':
    main()
