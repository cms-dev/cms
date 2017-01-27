#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2012 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2010-2011 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2016 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2011 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2014-2015 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2015 Luca Chiodini <luca@chiodini.org>
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

"""This script imports a user from disk using one of the available
loaders.

The data parsed by the loader is used to create a new User in the
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
import logging
import os
import sys

from cms import utf8_decoder
from cms.db import Contest, Participation, SessionGen, User
from cms.db.filecacher import FileCacher

from cmscontrib.loaders import choose_loader, build_epilog


logger = logging.getLogger(__name__)


class UserImporter(object):

    """This script creates a user

    """

    def __init__(self, path, contest_id, loader_class):
        self.file_cacher = FileCacher()
        self.contest_id = contest_id
        self.loader = loader_class(os.path.abspath(path), self.file_cacher)

    def do_import(self):
        """Get the user from the UserLoader and store it."""

        # Get the user
        user = self.loader.get_user()
        if user is None:
            return False

        # Store
        logger.info("Creating user %s on the database.", user.username)
        with SessionGen() as session:
            if self.contest_id is not None:
                contest = session.query(Contest)\
                                 .filter(Contest.id == self.contest_id)\
                                 .first()

                if contest is None:
                    logger.critical(
                        "The specified contest (id %s) does not exist. "
                        "Aborting.",
                        self.contest_id)
                    return False

            # Check whether the user already exists
            old_user = session.query(User) \
                              .filter(User.username == user.username) \
                              .first()
            if old_user is not None:
                logger.critical("The user already exists.")
                return False

            session.add(user)

            if self.contest_id is not None:
                logger.info("Creating participation of user %s in contest %s.",
                            user.username, contest.name)
                participation = Participation(user=user, contest=contest)
                session.add(participation)

            session.commit()
            user_id = user.id

        logger.info("Import finished (new user id: %s).", user_id)
        return True

    def do_import_all(self, base_path, get_loader):
        """Get the participation list from the ContestLoader and then
        try to import the corresponding users.

        """
        _, _, participations = self.loader.get_contest()
        for p in participations:
            user_path = os.path.join(base_path, p["username"])
            importer = UserImporter(
                path=user_path,
                contest_id=self.contest_id,
                loader_class=get_loader(user_path)
            )
            importer.do_import()

        return True


def main():
    """Parse arguments and launch process.

    """
    parser = argparse.ArgumentParser(
        description="Import a user to the database.",
        epilog=build_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "-L", "--loader",
        action="store", type=utf8_decoder,
        default=None,
        help="use the specified loader (default: autodetect)"
    )
    parser.add_argument(
        "target",
        action="store", type=utf8_decoder, nargs="?",
        default=os.getcwd(),
        help="target file/directory from where to import user(s)"
    )
    parser.add_argument(
        "-A", "--all",
        action="store_const", const="a",
        default=None,
        help="try to import all users inside target"
    )
    parser.add_argument(
        "-c", "--contest-id",
        action="store", type=int,
        help="id of the contest the users will be attached to"
    )

    args = parser.parse_args()

    def get_loader(path):
        return choose_loader(args.loader, path, parser.error)

    importer = UserImporter(
        path=args.target,
        contest_id=args.contest_id,
        loader_class=get_loader(args.target)
    )

    if args.all:
        success = importer.do_import_all(args.target, get_loader)
    else:
        success = importer.do_import()
    return 0 if success is True else 1


if __name__ == "__main__":
    sys.exit(main())
