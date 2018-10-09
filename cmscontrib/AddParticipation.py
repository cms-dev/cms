#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2017 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
# Copyright © 2017 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""This script creates a new participation in the database.

"""

# We enable monkey patching to make many libraries gevent-friendly
# (for instance, urllib3, used by requests)
import gevent.monkey
gevent.monkey.patch_all()  # noqa

import argparse
import datetime
import ipaddress
import logging
import sys

from sqlalchemy.exc import IntegrityError

from cms import utf8_decoder
from cms.db import Contest, Participation, SessionGen, Team, User, \
    ask_for_contest
from cmscommon.crypto import build_password, hash_password


logger = logging.getLogger(__name__)


def add_participation(username, contest_id, ip, delay_time, extra_time,
                      password, method, is_hashed, team_code, hidden,
                      unrestricted):
    logger.info("Creating the user's participation in the database.")
    delay_time = delay_time if delay_time is not None else 0
    extra_time = extra_time if extra_time is not None else 0

    if hidden:
        logger.warning("The participation will be hidden")
    if unrestricted:
        logger.warning("The participation will be unrestricted")

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
            if password is not None:
                if is_hashed:
                    password = build_password(password, method)
                else:
                    password = hash_password(password, method)

            participation = Participation(
                user=user,
                contest=contest,
                ip=[ipaddress.ip_network(ip)] if ip is not None else None,
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
    parser.add_argument("-t", "--team", action="store", type=utf8_decoder,
                        help="code of the team for this participation")
    parser.add_argument("--hidden", action="store_true",
                        help="if the participation is hidden")
    parser.add_argument("--unrestricted", action="store_true",
                        help="if the participation is unrestricted")
    password_group = parser.add_mutually_exclusive_group()
    password_group.add_argument(
        "-p", "--plaintext-password", action="store", type=utf8_decoder,
        help="password of the user in plain text")
    password_group.add_argument(
        "-H", "--hashed-password", action="store", type=utf8_decoder,
        help="password of the user, already hashed using the given algorithm "
             "(currently only --bcrypt)")
    method_group = parser.add_mutually_exclusive_group()
    method_group.add_argument(
        "--bcrypt", dest="method", action="store_const", const="bcrypt",
        help="whether the password will be stored in bcrypt-hashed format "
             "(if omitted it will be stored in plain text)")

    args = parser.parse_args()

    if args.hashed_password is not None and args.method is None:
        parser.error("hashed password given but no method specified")

    if args.contest_id is None:
        args.contest_id = ask_for_contest()

    success = add_participation(
        args.username, args.contest_id,
        args.ip, args.delay_time, args.extra_time,
        args.plaintext_password or args.hashed_password,
        args.method or "plaintext",
        args.hashed_password is not None, args.team,
        args.hidden, args.unrestricted)
    return 0 if success is True else 1


if __name__ == "__main__":
    sys.exit(main())
