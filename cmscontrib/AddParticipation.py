#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2016 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
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

"""This script creates a new user in the database.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

# We enable monkey patching to make many libraries gevent-friendly
# (for instance, urllib3, used by requests)
import gevent.monkey
gevent.monkey.patch_all()

import argparse
import datetime
import logging
import sys

from cms import utf8_decoder
from cms.db import Contest, Participation, SessionGen, Team, User, \
    ask_for_contest

from sqlalchemy.exc import IntegrityError


logger = logging.getLogger(__name__)


def add_participation(username, contest_id, ip, delay_time, extra_time,
                      password, team_code, hidden, unrestricted):
    logger.info("Creating the user's participation in the database.")
    delay_time = delay_time if delay_time is not None else 0
    extra_time = extra_time if extra_time is not None else 0

    try:
        with SessionGen() as session:
            user = \
                session.query(User).filter(User.username == username).first()
            if user is None:
                logger.error("No user with username `%s' found.", username)
                return False
            contest = Contest.get_from_id(contest_id, session)
            if contest is None:
                logger.error("No contest with id `%s' found.", contest_id)
                return False
            team = None
            if team_code is not None:
                team = \
                    session.query(Team).filter(Team.code == team_code).first()
                if team is None:
                    logger.error("No team with code `%s' found.", team_code)
                    return False
            participation = Participation(
                user=user,
                contest=contest,
                ip=ip,
                delay_time=datetime.timedelta(seconds=delay_time),
                extra_time=datetime.timedelta(seconds=extra_time),
                password=password,
                team=team,
                hidden=hidden,
                unrestricted=unrestricted)

            session.add(participation)
            session.commit()
    except IntegrityError:
        logger.error("A participation for this user in this contest "
                     "already exists.")
        return False

    logger.info("Participation added.")
    return True


def main():
    """Parse arguments and launch process.

    """
    parser = argparse.ArgumentParser(description="Add a participation to CMS.")
    parser.add_argument("username", action="store", type=utf8_decoder,
                        help="username to add to the contest")
    parser.add_argument("-c", "--contest-id", action="store", type=int,
                        help="id of the contest the users will be attached to")
    parser.add_argument("-i", "--ip", action="store", type=utf8_decoder,
                        help="ip address of this user")
    parser.add_argument("-d", "--delay_time", action="store", type=int,
                        help="how much the contest is shifted, in seconds")
    parser.add_argument("-e", "--extra_time", action="store", type=int,
                        help="how much additional time, in seconds")
    parser.add_argument("-p", "--password", action="store", type=utf8_decoder,
                        help="how much additional time, in seconds")
    parser.add_argument("-t", "--team", action="store", type=utf8_decoder,
                        help="code of the team for this participation")
    parser.add_argument("-n", "--hidden", action="store_true",
                        help="if the participation is hidden")
    parser.add_argument("-u", "--unrestricted", action="store_true",
                        help="if the participation is unrestricted")

    args = parser.parse_args()

    if args.contest_id is None:
        args.contest_id = ask_for_contest()

    success = add_participation(args.username, args.contest_id,
                                args.ip, args.delay_time, args.extra_time,
                                args.password, args.team,
                                args.hidden, args.unrestricted)
    return 0 if success is True else 1


if __name__ == "__main__":
    sys.exit(main())
