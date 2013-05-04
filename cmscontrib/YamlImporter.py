#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
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

"""This script imports a contest from disk using YamlLoader.

The data parsed by YamlLoader is used to create a new Contest in the
database.

"""

import os
import os.path
import argparse
import datetime

import sqlalchemy.exc

from cms import logger
from cms.db.FileCacher import FileCacher
from cms.db.SQLAlchemyAll import metadata, SessionGen, FSObject, User

from cmscontrib.YamlLoader import YamlLoader


class Importer:

    """This script imports a contest from disk using YamlLoader.

    The data parsed by YamlLoader is used to create a new Contest in
    the database.

    """

    def __init__(self, path, drop, test, zero_time, user_number):
        self.drop = drop
        self.test = test
        self.zero_time = zero_time
        self.user_number = user_number

        self.file_cacher = FileCacher()

        self.loader = YamlLoader(os.path.realpath(path), self.file_cacher)

    def _prepare_db(self):
        logger.info("Creating database structure.")
        if self.drop:
            try:
                with SessionGen() as session:
                    FSObject.delete_all(session)
                    session.commit()
                metadata.drop_all()
            except sqlalchemy.exc.OperationalError as error:
                logger.critical("Unable to access DB.\n%r" % error)
                return False
        try:
            metadata.create_all()
        except sqlalchemy.exc.OperationalError as error:
            logger.critical("Unable to access DB.\n%r" % error)
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
            logger.info("Generating %s random users." % self.user_number)
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

        logger.info("Import finished (new contest id: %s)." % contest_id)


def main():
    """Parse arguments and launch process."""
    parser = argparse.ArgumentParser(
        description="Import a contest from disk using YamlLoader")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-z", "--zero-time", action="store_true",
                       help="set to zero contest start and stop time")
    group.add_argument("-t", "--test", action="store_true",
                       help="setup a contest for testing "
                       "(times: 0, 2*10^9; ips: unset, passwords: a)")
    parser.add_argument("-d", "--drop", action="store_true",
                        help="drop everything from the database "
                        "before importing")
    parser.add_argument("-n", "--user-number", action="store", type=int,
                        help="put N random users instead of importing them")
    parser.add_argument("import_directory",
                        help="source directory from where import")

    args = parser.parse_args()

    Importer(path=args.import_directory,
             drop=args.drop,
             test=args.test,
             zero_time=args.zero_time,
             user_number=args.user_number).do_import()


if __name__ == "__main__":
    main()
