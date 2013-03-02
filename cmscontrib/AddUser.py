#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system - utility to add a user to a contest.
# Copyright © 2012 Bernard Blackham <bernard@largestprime.net>
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

import argparse
import sys

from cms.db.SQLAlchemyAll import SessionGen, User, Contest
from cms.db import ask_for_contest


def add_user(contest_id, first_name, last_name, username,
             password, ip_address, email, hidden):
    with SessionGen(commit=True) as session:
        contest = Contest.get_from_id(contest_id, session)
        user = User(first_name=first_name,
                    last_name=last_name,
                    username=username,
                    password=password,
                    email=email,
                    ip=ip_address,
                    hidden=hidden,
                    contest=contest)
        session.add(user)


def main():
    """Parse arguments and launch process.

    """
    parser = argparse.ArgumentParser(
        description="Adds a user to a contest in CMS.")
    parser.add_argument("first_name",
                        help="first name of the user")
    parser.add_argument("last_name",
                        help="last name of the user")
    parser.add_argument("username",
                        help="username of the user")
    parser.add_argument("-c", "--contest-id",
                        help="id of contest where to add the user",
                        action="store", type=int)
    parser.add_argument("-p", "--password", help="password of the user",
                        action="store")
    parser.add_argument("-i", "--ip-address", help="ip address of the user",
                        action="store")
    parser.add_argument("-e", "--email", help="email address of the user",
                        action="store")
    parser.add_argument("-H", "--hidden", help="if the user is hidden",
                        action="store_true")
    args = parser.parse_args()

    if args.contest_id is None:
        args.contest_id = ask_for_contest()

    add_user(contest_id=args.contest_id,
             first_name=args.first_name,
             last_name=args.last_name,
             username=args.username,
             password=args.password,
             ip_address=args.ip_address,
             email=args.email,
             hidden=args.hidden)

    return 0


if __name__ == "__main__":
    sys.exit(main())
