#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""This script imports a contest from disk using one of the available
loaders.

The data parsed by the loader is used to create a new Contest in the
database.

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
import os
import os.path

from cms import utf8_decoder
from cms.db import SessionGen, User, init_db, drop_db
from cms.db.filecacher import FileCacher

from cmscontrib.Loaders import choose_loader, build_epilog


logger = logging.getLogger(__name__)


class Importer(object):

    """This script imports a contest from disk using one of the
    available loaders.

    The data parsed by the loader is used to create a new Contest in
    the database.

    """

    def __init__(self, path, drop, test, zero_time, user_number, loader_class):
        self.drop = drop
        self.test = test
        self.zero_time = zero_time
        self.user_number = user_number

        self.file_cacher = FileCacher()

        self.loader = loader_class(os.path.realpath(path), self.file_cacher)

    def _prepare_db(self):
        logger.info("Creating database structure.")
        if self.drop:
            try:
                if not (drop_db() and init_db()):
                    logger.critical("Unexpected error while dropping and "
                                    "recreating the database.",
                                    exc_info=True)
                    return False
            except Exception:
                logger.critical("Unable to access DB.", exc_info=True)
                return False
        return True

    def do_import(self):
        """Get the contest from the Loader and store it."""
        if not self._prepare_db():
            return False

        # Get the contest
        contest, tasks, users = self.loader.get_contest()

        # Get the tasks
        for task in tasks:
            contest.tasks.append(self.loader.get_task(task))

        # Get the users or, if asked, generate them
        if self.user_number is None:
            for user in users:
                contest.users.append(self.loader.get_user(user))
        else:
            logger.info("Generating %s random users.", self.user_number)
            contest.users = [User("User %d" % i,
                                  "Last name %d" % i,
                                  "user%03d" % i)
                             for i in xrange(self.user_number)]

        # Apply the modification flags
        if self.zero_time:
            contest.start = datetime.datetime(1970, 1, 1)
            contest.stop = datetime.datetime(1970, 1, 1)
        elif self.test:
            contest.start = datetime.datetime(1970, 1, 1)
            contest.stop = datetime.datetime(2100, 1, 1)

            for user in contest.users:
                user.password = 'a'
                user.ip = None

        # Store
        logger.info("Creating contest on the database.")
        with SessionGen() as session:
            session.add(contest)
            session.commit()
            contest_id = contest.id

        logger.info("Import finished (new contest id: %s).", contest_id)


def main():
    """Parse arguments and launch process."""

    parser = argparse.ArgumentParser(
        description="Import a contest from disk",
        epilog=build_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-z", "--zero-time", action="store_true",
                       help="set to zero contest start and stop time")
    group.add_argument("-t", "--test", action="store_true",
                       help="setup a contest for testing "
                       "(times: 1970, 2100; ips: unset, passwords: a)")
    parser.add_argument("-d", "--drop", action="store_true",
                        help="drop everything from the database "
                        "before importing")
    parser.add_argument("-n", "--user-number", action="store", type=int,
                        help="put N random users instead of importing them")
    parser.add_argument("-L", "--loader",
                        action="store", type=utf8_decoder, default=None,
                        help="use the specified loader (default: autodetect)")
    parser.add_argument("import_directory", action="store", type=utf8_decoder,
                        help="source directory from where import")

    args = parser.parse_args()
    loader_class = choose_loader(args.loader,
                                 args.import_directory,
                                 parser.error)

    Importer(path=args.import_directory,
             drop=args.drop,
             test=args.test,
             zero_time=args.zero_time,
             user_number=args.user_number,
             loader_class=loader_class).do_import()


if __name__ == "__main__":
    main()
