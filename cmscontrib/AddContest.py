#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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
from cms.db import SessionGen, User, Participation, Task
from cms.db.filecacher import FileCacher

from cmscontrib.loaders import choose_loader, build_epilog


logger = logging.getLogger(__name__)


class ContestImporter(object):

    """This script creates a contest and all its associations to users
    and tasks.

    """

    def __init__(self, path, test, zero_time, user_number, loader_class):
        self.test = test
        self.zero_time = zero_time
        self.user_number = user_number

        self.file_cacher = FileCacher()

        self.loader = loader_class(os.path.realpath(path), self.file_cacher)

    def do_import(self):
        """Get the contest from the Loader and store it."""

        # Get the contest
        contest, tasks, users = self.loader.get_contest()

        # Apply the modification flags
        if self.zero_time:
            contest.start = datetime.datetime(1970, 1, 1)
            contest.stop = datetime.datetime(1970, 1, 1)
        elif self.test:
            contest.start = datetime.datetime(1970, 1, 1)
            contest.stop = datetime.datetime(2100, 1, 1)

        with SessionGen() as session:
            # Check needed tasks
            for (taskname, tasknum) in tasks.iteritems():
                task = session.query(Task) \
                              .filter(Task.name == taskname).first()
                if task is None:
                    logger.critical("Task \"%s\" not found in database."
                                    % taskname)
                    return
                if task.contest is not None:
                    logger.critical("Task \"%s\" is already tied to a "
                                    "contest." % taskname)
                    return
                else:
                    # We should tie this task to the contest
                    task.num = tasknum
                    task.contest = contest

            # Check needed users
            for username in users:
                user = session.query(User) \
                              .filter(User.username == username).first()
                if user is None:
                    logger.critical("User \"%s\" not found in database."
                                    % username)
                    return
                # We should tie this user to a new contest
                session.add(Participation(
                    user=user,
                    contest=contest
                ))

            # Here we could check if there are actually some tasks or
            # users to add: if there are not, then don't create the
            # contest. However, I would like to be able to create it
            # anyway (and later tie to it some tasks and users).

            logger.info("Creating contest on the database.")
            session.add(contest)

            # Final commit
            session.commit()
            logger.info("Import finished (new contest id: %s)." % contest.id)


def main():
    """Parse arguments and launch process."""

    parser = argparse.ArgumentParser(
        description="Import a contest from disk",
        epilog=build_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    group = parser.add_mutually_exclusive_group()

    group.add_argument(
        "-z", "--zero-time",
        action="store_true",
        help="set to zero contest start and stop time"
    )
    group.add_argument(
        "-t", "--test",
        action="store_true",
        help="setup a contest for testing "
             "(times: 1970, 2100; ips: unset, passwords: a)"
    )
    parser.add_argument(
        "-n", "--user-number",
        action="store", type=int,
        help="put N random users instead of importing them"
    )
    parser.add_argument(
        "-L", "--loader",
        action="store", type=utf8_decoder,
        default=None,
        help="use the specified loader (default: autodetect)"
    )
    parser.add_argument(
        "import_directory",
        action="store", type=utf8_decoder,
        help="source directory from where import"
    )

    args = parser.parse_args()

    loader_class = choose_loader(
        args.loader,
        args.import_directory,
        parser.error
    )

    ContestImporter(
        path=args.import_directory,
        test=args.test,
        zero_time=args.zero_time,
        user_number=args.user_number,
        loader_class=loader_class
    ).do_import()


if __name__ == "__main__":
    main()
