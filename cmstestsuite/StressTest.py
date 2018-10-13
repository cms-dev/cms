#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
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

import argparse
import ast
import os
import random
import sys
import threading
import time

import cmstestsuite.web
from cms import config, ServiceCoord, get_service_address, utf8_decoder
from cms.db import Contest, SessionGen
from cmscommon.crypto import parse_authentication
from cmstestsuite.web import Browser
from cmstestsuite.web.CWSRequests import HomepageRequest, CWSLoginRequest, \
    TaskRequest, TaskStatementRequest, SubmitRandomRequest


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
        print("TOTAL:          %5d" % (self.total), file=sys.stderr)
        print("SUCCESS:        %5d" % (self.success), file=sys.stderr)
        print("FAIL:           %5d" % (self.failure), file=sys.stderr)
        print("ERROR:          %5d" % (self.error), file=sys.stderr)
        print("UNDECIDED:      %5d" % (self.undecided), file=sys.stderr)
        print("Total time:   %7.3f" % (self.total_time), file=sys.stderr)
        print("Average time: %7.3f" % (self.total_time / self.total),
              file=sys.stderr)
        print("Max time:     %7.3f" % (self.max_time), file=sys.stderr)

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
        with open(filepath, 'wt', encoding='utf-8') as fd:
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
        self.metrics = metrics
        self.tasks = tasks
        self.log = log
        self.base_url = base_url
        self.submissions_path = submissions_path

        self.name = "Actor thread for user %s" % (self.username)

        self.browser = Browser()
        self.die = False

    def run(self):
        try:
            print("Starting actor for user %s" % (self.username),
                  file=sys.stderr)
            self.act()

        except ActorDying:
            print("Actor dying for user %s" % (self.username), file=sys.stderr)

    def act(self):
        """Define the behaviour of the actor. Subclasses are expected
        to overwrite this stub method properly.

        """
        raise Exception("Not implemented. Please subclass Action"
                        "and overwrite act().")

    def do_step(self, request):
        self.wait_next()
        self.log.total += 1
        try:
            request.execute()
        except Exception as exc:
            print("Unhandled exception while executing the request: %s" % exc,
                  file=sys.stderr)
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
        time_to_wait = self.metrics['time_coeff'] * \
            random.expovariate(self.metrics['time_lambda'])
        sleep_num = time_to_wait // SLEEP_PERIOD
        remaining_sleep = time_to_wait - (sleep_num * SLEEP_PERIOD)
        for _ in range(sleep_num):
            time.sleep(SLEEP_PERIOD)
            if self.die:
                raise ActorDying()
        time.sleep(remaining_sleep)
        if self.die:
            raise ActorDying()

    def login(self):
        """Log in and check to be logged in."""
        self.do_step(HomepageRequest(self.browser,
                                     self.username,
                                     loggedin=False,
                                     base_url=self.base_url))
        lr = CWSLoginRequest(self.browser,
                             self.username,
                             self.password,
                             base_url=self.base_url)
        self.browser.read_xsrf_token(lr.base_url)
        self.do_step(lr)
        self.do_step(HomepageRequest(self.browser,
                                     self.username,
                                     loggedin=True,
                                     base_url=self.base_url))


class RandomActor(Actor):

    def act(self):
        self.login()

        while True:
            choice = random.random()
            task = random.choice(self.tasks)
            if choice < 0.1 and self.submissions_path is not None:
                self.do_step(SubmitRandomRequest(
                    self.browser,
                    task,
                    base_url=self.base_url,
                    submissions_path=self.submissions_path))
            elif choice < 0.6 and task[2] != []:
                self.do_step(TaskStatementRequest(self.browser,
                                                  task[1],
                                                  random.choice(task[2]),
                                                  base_url=self.base_url))
            else:
                self.do_step(TaskRequest(self.browser,
                                         task[1],
                                         base_url=self.base_url))


class SubmitActor(Actor):

    def act(self):
        self.login()

        # Then keep forever stumbling across user pages
        while True:
            task = random.choice(self.tasks)
            self.do_step(SubmitRandomRequest(
                self.browser,
                task,
                base_url=self.base_url,
                submissions_path=self.submissions_path))


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
        for participation in contest.participations:
            user = participation.user
            # Pick participation's password if present, or the user's.
            password_source = participation.password
            if password_source is None:
                password_source = user.password
            # We can log in only if we know the plaintext password.
            method, password = parse_authentication(password_source)
            if method != "plaintext":
                print("Not using user %s with non-plaintext password."
                      % user.username)
                continue
            users[user.username] = {'password': password}
        for task in contest.tasks:
            tasks.append((task.id, task.name, list(task.statements.keys())))
    return users, tasks


DEFAULT_METRICS = {'time_coeff': 10.0,
                   'time_lambda': 2.0}


def main():
    parser = argparse.ArgumentParser(description="Stress tester for CMS")
    parser.add_argument(
        "-c", "--contest-id", action="store", type=int, required=True,
        help="ID of the contest to test against")
    parser.add_argument(
        "-n", "--actor-num", action="store", type=int,
        help="the number of actors to spawn")
    parser.add_argument(
        "-s", "--sort-actors", action="store_true",
        help="sort usernames alphabetically before slicing them")
    parser.add_argument(
        "-u", "--base-url", action="store", type=utf8_decoder,
        help="base contest URL for placing HTTP requests "
             "(without trailing slash)")
    parser.add_argument(
        "-S", "--submissions-path", action="store", type=utf8_decoder,
        help="base path for submission to send")
    parser.add_argument(
        "-p", "--prepare-path", action="store", type=utf8_decoder,
        help="file to put contest info to")
    parser.add_argument(
        "-r", "--read-from", action="store", type=utf8_decoder,
        help="file to read contest info from")
    parser.add_argument(
        "-t", "--time-coeff", action="store", type=float, default=10.0,
        help="average wait between actions")
    parser.add_argument(
        "-o", "--only-submit", action="store_true",
        help="whether the actor only submits solutions")
    args = parser.parse_args()

    # If prepare_path is specified we only need to save some useful
    # contest data and exit.
    if args.prepare_path is not None:
        users, tasks = harvest_contest_data(args.contest_id)
        contest_data = dict()
        contest_data['users'] = users
        contest_data['tasks'] = tasks
        with open(args.prepare_path, "wt", encoding="utf-8") as file_:
            file_.write("%s" % contest_data)
        return

    assert args.time_coeff > 0.0
    assert not (args.only_submit and len(args.submissions_path) == 0)

    users = []
    tasks = []

    # If read_from is not specified, read contest data from database
    # if it is specified - read contest data from the file
    if args.read_from is None:
        users, tasks = harvest_contest_data(args.contest_id)
    else:
        with open(args.read_from, "rt", encoding="utf-8") as file_:
            contest_data = ast.literal_eval(file_.read())
        users = contest_data['users']
        tasks = contest_data['tasks']

    if not users:
        print("No viable users, terminating.")
        return

    if args.actor_num is not None:
        user_items = list(users.items())
        if args.sort_actors:
            user_items.sort()
        else:
            random.shuffle(user_items)
        users = dict(user_items[:args.actor_num])

    # If the base URL is not specified, we try to guess it; anyway,
    # the guess code isn't very smart...
    if args.base_url is not None:
        base_url = args.base_url
    else:
        base_url = "http://%s:%d/" % \
            (get_service_address(ServiceCoord('ContestWebServer', 0))[0],
             config.contest_listen_port[0])

    metrics = DEFAULT_METRICS
    metrics["time_coeff"] = args.time_coeff
    actor_class = RandomActor
    if args.only_submit:
        actor_class = SubmitActor
    actors = [actor_class(username, data['password'], metrics, tasks,
                          log=RequestLog(log_dir=os.path.join('./test_logs',
                                                              username)),
                          base_url=base_url,
                          submissions_path=args.submissions_path)
              for username, data in users.items()]
    for actor in actors:
        actor.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Taking down actors", file=sys.stderr)
        for actor in actors:
            actor.die = True

    # Uncomment to turn on some memory profiling.
    # from meliae import scanner
    # print("Dumping")
    # scanner.dump_all_objects('objects.json')
    # print("Dump finished")

    for actor in actors:
        actor.join()

    print("Test finished", file=sys.stderr)

    great_log = RequestLog()
    for actor in actors:
        great_log.merge(actor.log)

    great_log.print_stats()


if __name__ == '__main__':
    main()
