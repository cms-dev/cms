#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
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

"""Utility to add a user to a contest.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import sys

from cms import utf8_decoder
from cms.db import SessionGen, User, Contest, ask_for_contest


def add_user(contest_id, first_name, last_name, username,
             password, ip_address, email, hidden):
    with SessionGen() as session:
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
        session.commit()


def main():
    """Parse arguments and launch process.

    """
    parser = argparse.ArgumentParser(
        description="Adds a user to a contest in CMS.")
    parser.add_argument("first_name", action="store", type=utf8_decoder,
                        help="first name of the user")
    parser.add_argument("last_name", action="store", type=utf8_decoder,
                        help="last name of the user")
    parser.add_argument("username", action="store", type=utf8_decoder,
                        help="username of the user")
    parser.add_argument("-c", "--contest-id", action="store", type=int,
                        help="id of contest where to add the user")
    parser.add_argument("-p", "--password", action="store", type=utf8_decoder,
                        help="password of the user")
    parser.add_argument("-i", "--ip-address", action="store",
                        type=utf8_decoder, help="ip address of the user")
    parser.add_argument("-e", "--email", action="store", type=utf8_decoder,
                        help="email address of the user")
    parser.add_argument("-H", "--hidden", action="store_true",
                        help="if the user is hidden")
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
