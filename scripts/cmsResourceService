#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

# We enable monkey patching to make many libraries gevent-friendly
# (for instance, urllib3, used by requests)
import gevent.monkey
gevent.monkey.patch_all()  # noqa

import argparse
import logging
import sys

from cms import ConfigError, contest_id_from_args, get_safe_shard, utf8_decoder
from cms.db import ask_for_contest, test_db_connection
from cms.service.ResourceService import ResourceService


logger = logging.getLogger(__name__)


RESTART_DISABLED = "RESTART_DISABLED"


def main():
    """Parses arguments and launch service.

    """
    parser = argparse.ArgumentParser(
        description="Resource monitor and service starter for CMS.")
    parser.add_argument("-a", "--autorestart", action="store", nargs="?",
                        type=utf8_decoder, const=None, metavar="CONTEST_ID",
                        dest="contest_id", default=RESTART_DISABLED,
                        help="restart automatically services on its machine; "
                        "a contest id or 'ALL' can be specified")
    parser.add_argument("shard", action="store", type=int, nargs="?")
    args = parser.parse_args()

    try:
        args.shard = get_safe_shard("ResourceService", args.shard)
    except ValueError:
        raise ConfigError("Couldn't autodetect shard number and "
                          "no shard specified for service %s, "
                          "quitting." % ("ResourceService", ))

    test_db_connection()

    autorestart = args.contest_id != RESTART_DISABLED
    contest_id = None
    if autorestart:
        contest_id = contest_id_from_args(args.contest_id, ask_for_contest)
    success = ResourceService(args.shard,
                              contest_id=contest_id,
                              autorestart=autorestart).run()

    return 0 if success is True else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ConfigError as error:
        logger.critical(error)
        sys.exit(1)
