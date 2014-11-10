#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2014 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Utility to remove one or more submissions.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import sys

from cms import utf8_decoder
from cms.db import SessionGen, Submission, Task, User, ask_for_contest


def ask_and_remove(session, submissions):
    print("This will delete %d submissions. Are you sure? [y/N] "
          % len(submissions), end='')
    ans = sys.stdin.readline().strip().lower()
    if ans in ["y", "yes"]:
        for submission in submissions:
            session.delete(submission)
        session.commit()
        print("Deleted.")
    else:
        print("Will not delete.")


def remove_submissions_for_user(contest_id, username):
    with SessionGen() as session:
        user = session.query(User)\
            .filter(User.contest_id == contest_id)\
            .filter(User.username == username).first()
        if user is None:
            print("Unable to find user.")
            return
        submissions = session.query(Submission)\
            .filter(Submission.user_id == user.id)\
            .all()
        ask_and_remove(session, submissions)


def remove_submissions_for_task(contest_id, task_name):
    with SessionGen() as session:
        task = session.query(Task)\
            .filter(Task.contest_id == contest_id)\
            .filter(Task.name == task_name).first()
        if task is None:
            print("Unable to find task.")
            return
        submissions = session.query(Submission)\
            .filter(Submission.task_id == task.id)\
            .all()
        ask_and_remove(session, submissions)


def remove_submission(submission_id):
    with SessionGen() as session:
        submission = session.query(Submission)\
            .filter(Submission.id == submission_id)\
            .first()
        ask_and_remove(session, [submission])


def main():
    """Parse arguments and launch process.

    """
    parser = argparse.ArgumentParser(
        description="Remove one or more submissions.")
    parser.add_argument("-c", "--contest-id", action="store", type=int,
                        help="id of contest the user is in")
    parser.add_argument("-u", "--username", action="store", type=utf8_decoder,
                        help="username of the user")
    parser.add_argument("-t", "--task_name", action="store", type=utf8_decoder,
                        help="short name of the task")
    parser.add_argument("-s", "--submission_id", action="store",
                        type=utf8_decoder, help="submission id")
    args = parser.parse_args()

    # We have a submission id, we do not need anything else.
    if args.submission_id is not None:
        if args.contest_id is not None \
                or args.username is not None or args.task_name is not None:
            print("Submission id require no other parameters.")
            return 1
        remove_submission(args.submission_id)
        return 0

    # Otherwise, it's either user or task, but not both.
    if args.username is not None and args.task_name is not None:
        print("Cannot set both task and user.")
        return 1
    elif args.username is None and args.task_name is None:
        print("Please set some filter.")
        return 1

    # In any case, we require a contest.
    if args.contest_id is None:
        args.contest_id = ask_for_contest()

    if args.username is not None:
        remove_submissions_for_user(contest_id=args.contest_id,
                                    username=args.username)
    elif args.task_name is not None:
        remove_submissions_for_task(contest_id=args.contest_id,
                                    task_name=args.task_name)

    return 0


if __name__ == "__main__":
    sys.exit(main())
