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

import os
import sys
import mechanize
import threading
import optparse
import random
import time
import codecs

from cms import config
from cms.async import ServiceCoord, get_service_address
from cms.db.SQLAlchemyAll import Contest, SessionGen

import cmstestsuite.web
from cmstestsuite.web.CWSRequests import HomepageRequest, \
     LoginRequest, TaskRequest, TaskStatementRequest, \
     SubmitRandomRequest


cmstestsuite.web.debug = True


class RequestLog:

    def __init__(self, log_dir=None):
        self.total = 0
        self.success = 0
        self.failure = 0
        self.error = 0
        self.undecided = 0
        self.total_time = 0.0
        self.max_time = 0.0

        self.log_dir = log_dir
        if self.log_dir is not None:
            try:
                os.makedirs(self.log_dir)
            except OSError:
                pass

    def print_stats(self):
        print >> sys.stderr, "TOTAL:          %5d" % (self.total)
        print >> sys.stderr, "SUCCESS:        %5d" % (self.success)
        print >> sys.stderr, "FAIL:           %5d" % (self.failure)
        print >> sys.stderr, "ERROR:          %5d" % (self.error)
        print >> sys.stderr, "UNDECIDED:      %5d" % (self.undecided)
        print >> sys.stderr, "Total time:   %7.3f" % (self.total_time)
        print >> sys.stderr, "Average time: %7.3f" % (self.total_time /
                                                      self.total)
        print >> sys.stderr, "Max time:     %7.3f" % (self.max_time)

    def merge(self, log2):
        self.total += log2.total
        self.success += log2.success
        self.failure += log2.failure
        self.error += log2.error
        self.undecided += log2.undecided
        self.total_time += log2.total_time
        self.max_time = max(self.max_time, log2.max_time)

    def store_to_file(self, request):
        if self.log_dir is None:
            return

        filename = "%s_%s.log" % (request.start_time,
                                  request.__class__.__name__)
        filepath = os.path.join(self.log_dir, filename)
        linkpath = os.path.join(self.log_dir, request.__class__.__name__)
        with codecs.open(filepath, 'w', encoding='utf-8') as fd:
            request.store_to_file(fd)
        try:
            os.remove(linkpath)
        except OSError:
            pass
        os.symlink(filename, linkpath)


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

    def __init__(self, username, password, metrics, tasks,
                 log=None, base_url=None, submissions_path=None):
        threading.Thread.__init__(self)

        self.username = username
        self.password = password
        self.metric = metrics
        self.tasks = tasks
        self.log = log
        self.base_url = base_url
        self.submissions_path = submissions_path

        self.name = "Actor thread for user %s" % (self.username)

        self.browser = mechanize.Browser()
        self.die = False

    def run(self):
        try:
            print >> sys.stderr, "Starting actor for user %s" % (self.username)
            self.act()

        except ActorDying:
            print >> sys.stderr, "Actor dying for user %s" % (self.username)

    def act(self):
        """Define the behaviour of the actor. Subclasses are expected
        to overwrite this stub method properly.

        """
        raise Exception("Not implemented. Please subclass Action" \
                            "and overwrite act()")

    def do_step(self, request):
        self.wait_next()
        self.log.total += 1
        try:
            request.prepare()
        except Exception as exc:
            print >> sys.stderr, "Unhandled exception while " \
                "preparing the request: %s" % (str(exc))
            return
        try:
            request.execute()
        except Exception as exc:
            print >> sys.stderr, "Unhandled exception while " \
                "executing the request %s" % (str(exc))
            return
        self.log.__dict__[request.outcome] += 1
        self.log.total_time += request.duration
        self.log.max_time = max(self.log.max_time, request.duration)
        self.log.store_to_file(request)

    def wait_next(self):
        """Wait some time. At the moment it waits c*X seconds, where c
        is the time_coeff parameter in metrics and X is an
        exponentially distributed random variable, with parameter
        time_lambda in metrics.

        The total waiting time is divided in lots of little sleep()
        call each one of 0.1 seconds, so that the waiting gets
        interrupted if a die signal arrives.

        If a die signal is received, an ActorDying exception is
        raised.

        """
        SLEEP_PERIOD = 0.1
        time_to_wait = self.metric['time_coeff'] * \
                       random.expovariate(self.metric['time_lambda'])
        sleep_num = int(time_to_wait / SLEEP_PERIOD)
        for i in xrange(sleep_num):
            time.sleep(SLEEP_PERIOD)
            if self.die:
                raise ActorDying()


class RandomActor(Actor):

    def act(self):
        # Start with logging in and checking to be logged in
        self.do_step(HomepageRequest(self.browser,
                                     self.username,
                                     loggedin=False,
                                     base_url=self.base_url))
        self.do_step(LoginRequest(self.browser,
                                  self.username,
                                  self.password,
                                  base_url=self.base_url))
        self.do_step(HomepageRequest(self.browser,
                                     self.username,
                                     loggedin=True,
                                     base_url=self.base_url))

        # Then keep forever stumbling across user pages
        while True:
            choice = random.random()
            if choice < 0.1 and self.submissions_path is not None:
                task = random.choice(self.tasks)
                self.do_step(SubmitRandomRequest(
                        self.browser,
                        task,
                        base_url=self.base_url,
                        submissions_path=self.submissions_path))
            elif choice < 0.5:
                task = random.choice(self.tasks)
                self.do_step(TaskRequest(self.browser,
                                         task[0],
                                         base_url=self.base_url))
            else:
                task = random.choice(self.tasks)
                self.do_step(TaskStatementRequest(self.browser,
                                                  task[0],
                                                  base_url=self.base_url))


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
            tasks.append((task.id, task.name))
    return users, tasks


DEFAULT_METRICS = {'time_coeff':  10.0,
                   'time_lambda': 2.0}


def main():
    parser = optparse.OptionParser(usage="usage: %prog [options]")
    parser.add_option("-c", "--contest",
                      help="contest ID to export", dest="contest_id",
                      action="store", type="int", default=None)
    parser.add_option("-n", "--actor-num",
                      help="the number of actors to spawn", dest="actor_num",
                      action="store", type="int", default=None)
    parser.add_option("-s", "--sort-actors",
                      help="sort usernames alphabetically "
                      "instead of randomizing before slicing them",
                      action="store_true", default=False, dest="sort_actors")
    parser.add_option("-u", "--base-url",
                      help="base URL for placing HTTP requests",
                      action="store", default=None, dest="base_url")
    parser.add_option("-S", "--submissions-path",
                      help="base path for submission to send",
                      action="store", default=None, dest="submissions_path")
    options = parser.parse_args()[0]

    users, tasks = harvest_contest_data(options.contest_id)
    if options.actor_num is not None:
        user_items = users.items()
        if options.sort_actors:
            user_items.sort()
        else:
            random.shuffle(user_items)
        users = dict(user_items[:options.actor_num])

    # If the base URL is not specified, we try to guess it; anyway,
    # the guess code isn't very smart...
    if options.base_url is not None:
        base_url = options.base_url
    else:
        base_url = "http://%s:%d/" % \
            (get_service_address(ServiceCoord('ContestWebServer', 0))[0],
             config.contest_listen_port[0])

    actors = [RandomActor(username, data['password'], DEFAULT_METRICS, tasks,
                          log=RequestLog(log_dir=os.path.join('./test_logs',
                                                              username)),
                          base_url=base_url,
                          submissions_path=options.submissions_path)
              for username, data in users.iteritems()]
    for actor in actors:
        actor.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print >> sys.stderr, "Taking down actors"
        for actor in actors:
            actor.die = True

    # Turn on some memory profiling
    #from meliae import scanner
    #print "Dumping"
    #scanner.dump_all_objects('objects.json')
    #print "Dump finished"

    finished = False
    while not finished:
        for actor in actors:
            actor.join()
        else:
            finished = True

    print >> sys.stderr, "Test finished"

    great_log = RequestLog()
    for actor in actors:
        great_log.merge(actor.log)

    great_log.print_stats()

if __name__ == '__main__':
    main()
