#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2016 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Utility to remove a contest.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import sys

from cms.db import Contest, SessionGen, ask_for_contest


def ask(contest):
    print("This will delete contest `%s' (with id %s) and all related data, "
          "including submissions. Are you sure? [y/N] "
          % (contest.name, contest.id), end='')
    ans = sys.stdin.readline().strip().lower()
    return ans in ["y", "yes"]


def remove_contest(contest_id):
    with SessionGen() as session:
        contest = session.query(Contest)\
            .filter(Contest.id == contest_id).first()
        if not contest:
            print("No contest with id %s found." % contest_id)
            return
        contest_name = contest.name
        if not ask(contest):
            print("Not removing contest `%s'." % contest_name)
            return
        session.delete(contest)
        session.commit()
        print("Contest `%s' removed." % contest_name)


def main():
    """Parse arguments and launch process.

    """
    parser = argparse.ArgumentParser(
        description="Remove a contest from CMS.")
    parser.add_argument("-c", "--contest-id", action="store", type=int,
                        help="id of contest the user is in")
    args = parser.parse_args()

    if args.contest_id is None:
        args.contest_id = ask_for_contest()

    remove_contest(contest_id=args.contest_id)


if __name__ == "__main__":
    main()
