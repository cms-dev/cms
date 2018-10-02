#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2013-2016 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Utility to remove a user.

"""

import argparse
import logging
import sys

from cms import utf8_decoder
from cms.db import SessionGen, User


logger = logging.getLogger(__name__)


def remove_user(username):
    with SessionGen() as session:
        user = session.query(User)\
            .filter(User.username == username).first()
        if user is None:
            logger.error("User %s does not exist.", username)
            return False

        session.delete(user)
        session.commit()

    return True


def main():
    """Parse arguments and launch process.

    """
    parser = argparse.ArgumentParser(
        description="Remove a user from a contest in CMS.")
    parser.add_argument("username", action="store", type=utf8_decoder,
                        help="username of the user")
    args = parser.parse_args()

    success = remove_user(username=args.username)
    return 0 if success is True else 1


if __name__ == "__main__":
    sys.exit(main())
