#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2026 Pasit Sangprachathanarak <ouipingpasit@gmail.com>
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

"""Utility to remove a team.

"""

import argparse
import logging
import sys

from cms import utf8_decoder
from cms.db import SessionGen, Team


logger = logging.getLogger(__name__)


def remove_team(code: str) -> bool:
    with SessionGen() as session:
        if team is None:
            logger.error("Team %s does not exist.", code)
            return False

        session.delete(team)
        session.commit()

    return True


def main():
    """Parse arguments and launch process.

    """
    parser = argparse.ArgumentParser(
        description="Remove a team from CMS.")
    parser.add_argument("code", action="store", type=utf8_decoder,
                        help="code of the team, e.g. country code")
    args = parser.parse_args()

    success = remove_team(code=args.code)
    return 0 if success is True else 1


if __name__ == "__main__":
    sys.exit(main())
