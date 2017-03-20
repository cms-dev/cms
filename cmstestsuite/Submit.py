#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2012 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2016 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

import argparse

from cms.db import Contest, SessionGen

from cmstestsuite.web import Browser
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


def submit_solution(
        username, password, task, files, language=None, base_url=None):
    browser = Browser()

    LoginRequest(browser, username, password, base_url=base_url).execute()
    SubmitRequest(browser, task, base_url=base_url,
                  filename=files[0], language=language)\
        .execute()


def release_test(username, password, task, submission_num, base_url=None):
    browser = Browser()

    LoginRequest(browser, username, password, base_url=base_url).execute()
    TokenRequest(browser, task, base_url=base_url,
                 submission_num=submission_num).execute()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c", "--contest", action="store", type=int, dest="contest_id",
        help="contest ID to export")
    parser.add_argument(
        "-l", "--language", action="store", type=utf8_decoder,
        help="submission language")
    parser.add_argument(
        "-u", "--base-url", action="store", type=utf8_decoder,
        help="base URL for placing HTTP requests")
    parser.add_argument(
        "username", action="store", type=utf8_decoder,
        help="")
    parser.add_argument(
        "taskname", action="store", type=utf8_decoder,
        help="")
    parser.add_argument(
        "files", action="store", type=utf8_decoder, nargs="+",
        help="")
    args = parser.parse_args()

    users, tasks = harvest_contest_data(args.contest_id)
    if args.username not in users:
        parser.error("User '%s' unknown." % args.username)

    task = [(tid, tname) for tid, tname in tasks if tname == args.taskname]
    if len(task) != 1:
        parser.error("Task '%s' does not identify a unique task."
                     % args.taskname)
    task = task[0]

    password = users[args.username]['password']

    submit_solution(args.username, password, task, args.files, args.language,
                    base_url=args.base_url)


if __name__ == '__main__':
    main()
