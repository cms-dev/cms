#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 202 Bernard Blackham <bernard@largestprime.net>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import mechanize
import optparse

from cms.db import Contest, SessionGen

from cmstestsuite.web.CWSRequests import \
    LoginRequest, SubmitRequest, TokenRequest


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


def submit_solution(username, password, task, files, base_url=None):
    def step(request):
        request.prepare()
        request.execute()

    browser = mechanize.Browser()
    browser.set_handle_robots(False)

    step(LoginRequest(browser, username, password, base_url=base_url))
    step(SubmitRequest(browser, task, base_url=base_url, filename=files[0]))


def release_test(username, password, task, submission_num, base_url=None):
    def step(request):
        request.prepare()
        request.execute()

    browser = mechanize.Browser()
    browser.set_handle_robots(False)

    step(LoginRequest(browser, username, password, base_url=base_url))
    step(TokenRequest(
        browser, task, base_url=base_url, submission_num=submission_num))


def main():
    parser = optparse.OptionParser(
        usage="usage: %prog [options] <user name> <task name> <files>")
    parser.add_option("-c", "--contest",
                      help="contest ID to export", dest="contest_id",
                      action="store", type="int", default=None)
    parser.add_option("-u", "--base-url",
                      help="base URL for placing HTTP requests",
                      action="store", default=None, dest="base_url")
    options, args = parser.parse_args()

    if len(args) < 3:
        parser.error("Not enough arguments.")
    username = args[0]
    taskname = args[1]
    files = args[2:]

    users, tasks = harvest_contest_data(options.contest_id)
    if username not in users:
        parser.error("User '%s' unknown." % username)

    task = [(tid, tname) for tid, tname in tasks if tname == taskname]
    if len(task) != 1:
        parser.error("Task '%s' does not identify a unique task." % taskname)
    task = task[0]

    password = users[username]['password']

    submit_solution(username, password, task, files, base_url=options.base_url)


if __name__ == '__main__':
    main()
