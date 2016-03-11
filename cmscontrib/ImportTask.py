#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014-2016 William Di Luigi <williamdiluigi@gmail.com>
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

"""This script imports a task from disk using one of the available
loaders.

The data parsed by the loader is used to create a new Task in the
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
from cms.db import Contest, SessionGen, Task
from cms.db.filecacher import FileCacher

from cmscontrib import BaseImporter
from cmscontrib.loaders import choose_loader, build_epilog


logger = logging.getLogger(__name__)


class TaskImporter(BaseImporter):

    """This script creates a task

    """

    def __init__(self, path, prefix, update, no_statement, contest_id, loader_class):
        self.file_cacher = FileCacher()
        self.prefix = prefix
        self.update = update
        self.no_statement = no_statement
        self.contest_id = contest_id
        self.loader = loader_class(os.path.abspath(path), self.file_cacher)

    def do_import(self):
        """Get the task from the TaskLoader and store it."""

        # We need to check whether the task has changed *before* calling
        # get_task() as that method might reset the "has_changed" bit..
        if self.update:
            task_has_changed = self.loader.task_has_changed()

        # Get the task
        task = self.loader.get_task(get_statement=not self.no_statement)
        if task is None:
            return

        # Apply the prefix, if there is one
        if self.prefix:
            task.name = self.prefix + task.name

        # Store
        logger.info("Creating task on the database.")
        with SessionGen() as session:
            # Check whether the task already exists
            old_task = session.query(Task) \
                              .filter(Task.name == task.name) \
                              .first()
            if old_task is not None:
                if self.update:
                    if task_has_changed:
                        ignore = set(("num",))
                        if self.no_statement:
                            ignore.update(("primary_statements",
                                           "statements"))
                        self._update_object(old_task, task, ignore)
                    task = old_task
                else:
                    logger.critical("Task \"%s\" already exists in database.",
                                    task.name)
                    return
            else:
                if self.contest_id is not None:
                    contest = session.query(Contest) \
                                     .filter(Contest.id == self.contest_id) \
                                     .first()

                    if contest is None:
                        logger.critical(
                            "The specified contest (id %s) does not exist. "
                            "Aborting, no task imported.",
                            self.contest_id)
                        return
                    else:
                        logger.info(
                            "Attaching task to contest with id %s.",
                            self.contest_id)
                        task.num = len(contest.tasks)
                        task.contest = contest

                session.add(task)

            session.commit()
            task_id = task.id

        logger.info("Import finished (task id: %s).", task_id)


def main():
    """Parse arguments and launch process."""

    parser = argparse.ArgumentParser(
        description="Import a new task or update an existing one in CMS.",
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
        "-u", "--update",
        action="store_true",
        help="update an existing task"
    )
    parser.add_argument(
        "-S", "--no-statement",
        action="store_true",
        help="do not import / update task statement"
    )
    parser.add_argument(
        "-c", "--contest-id",
        action="store", type=int,
        help="id of the contest the task will be attached to"
    )
    parser.add_argument(
        "-p", "--prefix",
        action="store", type=utf8_decoder,
        help="the prefix to be added before the task name"
    )
    parser.add_argument(
        "target",
        action="store", type=utf8_decoder,
        help="target file/directory from where to import task(s)"
    )

    args = parser.parse_args()

    loader_class = choose_loader(
        args.loader,
        args.target,
        parser.error
    )

    TaskImporter(
        path=args.target,
        update=args.update,
        no_statement=args.no_statement,
        contest_id=args.contest_id,
        prefix=args.prefix,
        loader_class=loader_class
    ).do_import()


if __name__ == "__main__":
    main()
