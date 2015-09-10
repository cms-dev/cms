#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2012 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2010-2011 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2011 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2011 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2014 William Di Luigi <williamdiluigi@gmail.com>
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

from cms import utf8_decoder
from cms.db import SessionGen
from cms.db.filecacher import FileCacher
from sqlalchemy.exc import IntegrityError

from cmscontrib.loaders import choose_loader, build_epilog


logger = logging.getLogger(__name__)


class UserImporter(object):

    """This script creates a user

    """

    def __init__(self, path, loader_class):
        self.file_cacher = FileCacher()
        self.loader = loader_class(os.path.realpath(path), self.file_cacher)

    def do_import(self):
        """Get the user from the UserLoader and store it."""

        # Get the user
        user = self.loader.get_user()
        if user is None:
            return

        # Store
        try:
            logger.info("Creating user on the database.")
            with SessionGen() as session:
                session.add(user)
                session.commit()
                user_id = user.id
        except IntegrityError:
                logger.critical("The user already exists.")
                return

        logger.info("Import finished (new user id: %s)." % user_id)

    def do_import_all(self, base_path, get_loader):
        """Get the users list from the ContestLoader and then try to
        import the corresponding users."""

        contest, tasks, users = self.loader.get_contest()
        for username in users:
            user_path = os.path.join(base_path, username)
            UserImporter(
                path=user_path,
                loader_class=get_loader(user_path)
            ).do_import()


def main():
    """Parse arguments and launch process.

    """
    parser = argparse.ArgumentParser(
        description="Add a user to a contest in CMS.",
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

    args = parser.parse_args()

    def get_loader(path):
        return choose_loader(args.loader, path, parser.error)

    importer = UserImporter(
        path=args.target,
        loader_class=get_loader(args.target)
    )

    if args.all:
        importer.do_import_all(args.target, get_loader)
    else:
        importer.do_import()

if __name__ == "__main__":
    main()
