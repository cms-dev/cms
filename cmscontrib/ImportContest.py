#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2016 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014-2015 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2015-2016 Luca Chiodini <luca@chiodini.org>
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
import ipaddress
import logging
import os
import sys

from cms import utf8_decoder
from cms.db import SessionGen, User, Team, Participation, Task, Contest
from cms.db.filecacher import FileCacher

from cmscontrib.loaders import choose_loader, build_epilog

from . import BaseImporter

logger = logging.getLogger(__name__)


class ContestImporter(BaseImporter):

    """This script creates a contest and all its associations to users
    and tasks.

    """

    def __init__(self, path, test, zero_time, user_number, import_tasks,
                 update_contest, update_tasks, no_statements, loader_class):
        self.test = test
        self.zero_time = zero_time
        self.user_number = user_number
        self.import_tasks = import_tasks
        self.update_contest = update_contest
        self.update_tasks = update_tasks
        self.no_statements = no_statements
        self.file_cacher = FileCacher()

        self.loader = loader_class(os.path.abspath(path), self.file_cacher)

    def do_import(self):
        """Get the contest from the Loader and store it."""

        # We need to check whether the contest has changed *before* calling
        # get_contest() as that method might reset the "has_changed" bit.
        if self.update_contest:
            contest_has_changed = self.loader.contest_has_changed()

        # Get the contest
        contest, tasks, participations = self.loader.get_contest()

        # Apply the modification flags
        if self.zero_time:
            contest.start = datetime.datetime(1970, 1, 1)
            contest.stop = datetime.datetime(1970, 1, 1)
        elif self.test:
            contest.start = datetime.datetime(1970, 1, 1)
            contest.stop = datetime.datetime(2100, 1, 1)

        with SessionGen() as session:
            # Check whether the contest already exists
            old_contest = session.query(Contest) \
                                 .filter(Contest.name == contest.name).first()
            if old_contest is not None:
                if self.update_contest:
                    if contest_has_changed:
                        self._update_object(old_contest, contest)
                    contest = old_contest
                elif self.update_tasks:
                    contest = old_contest
                else:
                    logger.critical(
                        "Contest \"%s\" already exists in database.",
                        contest.name)
                    return False

            # Check needed tasks
            for tasknum, taskname in enumerate(tasks):
                task = session.query(Task) \
                              .filter(Task.name == taskname).first()
                if task is None:
                    if self.import_tasks:
                        task = self.loader.get_task_loader(taskname).get_task(
                            get_statement=not self.no_statements)
                        if task:
                            session.add(task)
                        else:
                            logger.critical("Could not import task \"%s\".",
                                            taskname)
                            return False
                    else:
                        logger.critical("Task \"%s\" not found in database.",
                                        taskname)
                        return False
                elif self.update_tasks:
                    task_loader = self.loader.get_task_loader(taskname)
                    if task_loader.task_has_changed():
                        new_task = task_loader.get_task(
                            get_statement=not self.no_statements)
                        if new_task:
                            ignore = set(("num",))
                            if self.no_statements:
                                ignore.update(("primary_statements",
                                               "statements"))
                            self._update_object(task, new_task,
                                                ignore=ignore)
                        else:
                            logger.critical("Could not reimport task \"%s\".",
                                            taskname)
                            return False

                if task.contest is not None \
                   and task.contest.name != contest.name:
                    logger.critical("Task \"%s\" is already tied to a "
                                    "contest.", taskname)
                    return False
                else:
                    # We should tie this task to the contest
                    task.num = tasknum
                    task.contest = contest

            # Check needed participations
            if participations is None:
                participations = []

            for p in participations:
                user = session.query(User) \
                              .filter(User.username == p["username"]).first()

                team = session.query(Team) \
                              .filter(Team.code == p.get("team")).first()

                if user is None:
                    # FIXME: it would be nice to automatically try to
                    # import.
                    logger.critical("User \"%s\" not found in database.",
                                    p["username"])
                    return False

                if team is None and p.get("team") is not None:
                    # FIXME: it would be nice to automatically try to
                    # import.
                    logger.critical("Team \"%s\" not found in database.",
                                    p.get("team"))
                    return False

                # Check that the participation is not already defined.
                participation = session.query(Participation) \
                    .filter(Participation.user_id == user.id) \
                    .filter(Participation.contest_id == contest.id) \
                    .first()

                # FIXME: detect if some details of the participation have been
                # updated and thus the existing participation needs to be
                # changed.
                if participation is None:
                    # Prepare new participation
                    args = {
                        "user": user,
                        "team": team,
                        "contest": contest,
                    }

                    if "hidden" in p:
                        args["hidden"] = p["hidden"]
                    if "ip" in p and p["ip"] is not None:
                        args["ip"] = [ipaddress.ip_network(p["ip"])]
                    if "password" in p:
                        args["password"] = p["password"]

                    session.add(Participation(**args))
                else:
                    logger.warning("Participation of user %s in this contest "
                                   "already exists, not going to update it.",
                                   p["username"])

            # Here we could check if there are actually some tasks or
            # users to add: if there are not, then don't create the
            # contest. However, I would like to be able to create it
            # anyway (and later tie to it some tasks and users).

            if old_contest is None:
                logger.info("Creating contest on the database.")
                session.add(contest)

            # Final commit
            session.commit()
            logger.info("Import finished (new contest id: %s).", contest.id)

        return True


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
        "-i", "--import-tasks",
        action="store_true",
        help="import tasks if they do not exist"
    )
    parser.add_argument(
        "-u", "--update-contest",
        action="store_true",
        help="update an existing contest"
    )
    parser.add_argument(
        "-U", "--update-tasks",
        action="store_true",
        help="update existing tasks"
    )
    parser.add_argument(
        "-S", "--no-statements",
        action="store_true",
        help="do not import / update task statements"
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

    importer = ContestImporter(path=args.import_directory,
                               test=args.test,
                               zero_time=args.zero_time,
                               user_number=args.user_number,
                               import_tasks=args.import_tasks,
                               update_contest=args.update_contest,
                               update_tasks=args.update_tasks,
                               no_statements=args.no_statements,
                               loader_class=loader_class)
    success = importer.do_import()
    return 0 if success is True else 1


if __name__ == "__main__":
    sys.exit(main())
