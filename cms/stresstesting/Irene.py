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
import mechanize
import threading
import optparse
import random
import time
import re

from cms.db.SQLAlchemyAll import Contest, SessionGen


class RequestLog:

    total = 0
    successes = 0
    failures = 0
    errors = 0
    undecided = 0

    def __init__(self):
        self.tests = []

    def add_test(self, data):
        self.tests.append((time.time(), data))

    def print_stats(self):
        print >> sys.stderr, "TOTAL:       %5d" % (self.total)
        print >> sys.stderr, "SUCCESS:     %5d" % (self.successes)
        print >> sys.stderr, "FAIL:        %5d" % (self.failures)
        print >> sys.stderr, "ERROR:       %5d" % (self.errors)
        print >> sys.stderr, "UNDECIDED:   %5d" % (self.undecided)

    def merge(self, log2):
        self.total += log2.total
        self.successes += log2.successes
        self.failures += log2.failures
        self.errors += log2.errors
        self.undecided += log2.undecided
        self.tests += log2.tests

class TestRequest:
    """Docstring TODO.

    """
    def __init__(self, browser, base_url=None):
        if base_url is None:
            base_url = 'http://localhost:8888/'
        self.browser = browser
        self.base_url = base_url

    def execute(self, log=None):
        if log is not None:
            log.total += 1
        description = self.describe()
        try:
            self.do_request()
            success = self.test_success()
        except Exception as exc:
            print >> sys.stderr, "Request '%s' terminated " \
                "with an exception: %s" % (description, repr(exc))
            if log is not None:
                log.errors += 1
                log.add_test(self.get_test_data())
        else:
            if success is None:
                print >> sys.stderr, "Could not determine " \
                    "status for request '%s'" % (description)
                if log is not None:
                    log.undecided += 1
                    log.add_test(self.get_test_data())
            elif success:
                print >> sys.stderr, "Request '%s' successfully " \
                    "completed" % (description)
                if log is not None:
                    log.successes += 1
                    log.add_test(self.get_test_data())
            elif not success:
                print >> sys.stderr, "Request '%s' failed" % (description)
                if log is not None:
                    log.failures += 1
                    log.add_test(self.get_test_data())

    def describe(self):
        raise NotImplementedError("Please subclass this class "
                                  "and actually implement some request")

    def do_request(self):
        raise NotImplementedError("Please subclass this class "
                                  "and actually implement some request")

    def test_success(self):
        raise NotImplementedError("Please subclass this class "
                                  "and actually implement some request")

    def get_test_data(self):
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

    def get_test_data(self):
        return (self.res_data, self.response.info())


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

    def __init__(self, username, password, metrics, tasks, log=None):
        threading.Thread.__init__(self)

        self.username = username
        self.password = password
        self.metric = metrics
        self.tasks = tasks
        self.log = log

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
        request.execute(self.log)

    def wait_next(self):
        """Wait some time. At the moment it waits c*X seconds, where c
        is the time_coeff parameter in metrics and X is an
        exponentially distributed random variable, with parameter
        time_lambda in metrics.

        """
        time_to_wait = self.metric['time_coeff'] * \
                       random.expovariate(self.metric['time_lambda'])
        time.sleep(time_to_wait)

def harvest_contest_data(contest_id):
    """Retrieve the couples username, password and the task list for a
    given contest.

    contest_id (int): the id of the contest we want.
    return (tuple): the first element is a dictionary mapping
                    usernames to passwords; the second one is the list
                    of the task names.

    """
    users = {}
    tasks = []
    with SessionGen() as session:
        contest = Contest.get_from_id(contest_id, session)
        for user in contest.users:
            users[user.username] = {'password': user.password}
        for task in contest.tasks:
            tasks.append(task.name)
    return users, tasks


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

    users, tasks = harvest_contest_data(options.contest_id)
    if options.actor_num is not None:
        user_items = users.items()
        random.shuffle(user_items)
        users = dict(user_items[:options.actor_num])

    actors = [Actor(username, data['password'], DEFAULT_METRICS, tasks, log=RequestLog())
              for username, data in users.iteritems()]
    for actor in actors:
        actor.start()

    finished = False
    while not finished:
        try:
            for actor in actors:
                actor.join()
            else:
                finished = True
        except KeyboardInterrupt:
            print >> sys.stderr, "Taking down actors"
            for actor in actors:
                actor.die = True

    print >> sys.stderr, "Test finished"

    great_log = RequestLog()
    for actor in actors:
        great_log.merge(actor.log)

    great_log.print_stats()

if __name__ == '__main__':
    main()
