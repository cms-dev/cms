#!/usr/bin/env python3

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

"""This script creates a new team in the database.

"""

# We enable monkey patching to make many libraries gevent-friendly
# (for instance, urllib3, used by requests)
import gevent.monkey
gevent.monkey.patch_all()  # noqa

import argparse
import logging
import sys

from sqlalchemy.exc import IntegrityError

from cms import utf8_decoder
from cms.db import SessionGen, Team


logger = logging.getLogger(__name__)


def add_team(code, name):
    logger.info("Creating the team in the database.")
    team = Team(code=code, name=name)
    try:
        with SessionGen() as session:
            session.add(team)
            session.commit()
    except IntegrityError:
        logger.error("A team with the given code already exists.")
        return False

    logger.info("Team added.")
    return True


def main():
    """Parse arguments and launch process.

    """
    parser = argparse.ArgumentParser(description="Add a team to CMS.")
    parser.add_argument("code", action="store", type=utf8_decoder,
                        help="code of the team, e.g. country code")
    parser.add_argument("name", action="store", type=utf8_decoder,
                        help="human readable name of the team")

    args = parser.parse_args()

    success = add_team(args.code, args.name)
    return 0 if success is True else 1


if __name__ == "__main__":
    sys.exit(main())
