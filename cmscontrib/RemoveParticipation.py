#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
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

"""Utility to remove a participation.

"""

import argparse
import logging
import sys

from cms import utf8_decoder
from cms.db import SessionGen, Contest, User, Participation, ask_for_contest


logger = logging.getLogger(__name__)


def remove_participation(contest_id, username):
    with SessionGen() as session:
        user = session.query(User)\
            .filter(User.username == username).first()
        if user is None:
            logger.error("User %s does not exist.", username)
            return False

        contest = session.query(Contest)\
            .filter(Contest.id == contest_id).first()
        if contest is None:
            logger.error("Contest id %d does not exist.", contest_id)
            return False

        participation = session.query(Participation)\
            .filter(Participation.contest_id == contest_id)\
            .filter(Participation.user == user).first()
        if participation is None:
            logger.error("Participation of %s in contest %d does not exists.",
                         username, contest_id)
            return False
        session.delete(participation)
        session.commit()

    return True


def main():
    """Parse arguments and launch process.

    """
    parser = argparse.ArgumentParser(
        description="Remove a participation from a contest in CMS.")
    parser.add_argument("username", action="store", type=utf8_decoder,
                        help="username of the user")
    parser.add_argument("-c", "--contest-id", action="store", type=int,
                        help="id of contest the user is in")
    args = parser.parse_args()

    if args.contest_id is None:
        args.contest_id = ask_for_contest()

    success = remove_participation(contest_id=args.contest_id,
                                   username=args.username)
    return 0 if success is True else 1


if __name__ == "__main__":
    sys.exit(main())
