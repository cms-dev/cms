#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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

# We enable monkey patching to make many libraries gevent-friendly
# (for instance, urllib3, used by requests)
import gevent.monkey
gevent.monkey.patch_all()  # noqa

import argparse
import logging
import os
import sys

from cms import utf8_decoder
from cms.db import SessionGen, Task
from cms.db.filecacher import FileCacher
from cmscontrib.importing import ImportDataError, contest_from_db, update_task
from cmscontrib.loaders import choose_loader, build_epilog


logger = logging.getLogger(__name__)


class TaskImporter:

    """This script creates a task

    """

    def __init__(self, path, prefix, override_name, update, no_statement,
                 contest_id, loader_class):
        """Create the importer object for a task.

        path (string): the path to the file or directory to import.
        prefix (string|None): an optional prefix added to the task name.
        override_name (string|None): an optional new name for the task.
        update (bool): if the task already exists, try to update it.
        no_statement (bool): do not try to import the task statement.
        contest_id (int|None): if set, the new task will be tied to this
            contest; if not set, the task will not be tied to any contest, or
            if this was an update, will remain tied to the previous contest.

        """
        self.file_cacher = FileCacher()
        self.prefix = prefix
        self.override_name = override_name
        self.update = update
        self.no_statement = no_statement
        self.contest_id = contest_id
        self.loader = loader_class(os.path.abspath(path), self.file_cacher)

    def do_import(self):
        """Get the task from the TaskLoader and store it."""

        # We need to check whether the task has changed *before* calling
        # get_task() as that method might reset the "has_changed" bit..
        task_has_changed = False
        if self.update:
            task_has_changed = self.loader.task_has_changed()

        # Get the task
        task = self.loader.get_task(get_statement=not self.no_statement)
        if task is None:
            return False

        # Override name, if necessary
        if self.override_name:
            task.name = self.override_name

        # Apply the prefix, if there is one
        if self.prefix:
            task.name = self.prefix + task.name

        # Store
        logger.info("Creating task on the database.")
        with SessionGen() as session:
            try:
                contest = contest_from_db(self.contest_id, session)
                task = self._task_to_db(
                    session, contest, task, task_has_changed)

            except ImportDataError as e:
                logger.error(str(e))
                logger.info("Error while importing, no changes were made.")
                return False

            session.commit()
            task_id = task.id

        logger.info("Import finished (new task id: %s).", task_id)
        return True

    def _task_to_db(self, session, contest, new_task, task_has_changed):
        """Add the task to the DB

        Return the task, or raise in case of one of these errors:
        - if the task is not in the DB and user did not ask to update it;
        - if the task is already in the DB and attached to another contest.

        """
        task = session.query(Task).filter(Task.name == new_task.name).first()
        if task is None:
            if contest is not None:
                logger.info("Attaching task to contest (id %s.)",
                            self.contest_id)
                new_task.num = len(contest.tasks)
                new_task.contest = contest
            session.add(new_task)
            return new_task

        if not self.update:
            raise ImportDataError(
                "Task \"%s\" already exists in database. "
                "Use --update to update it." % new_task.name)

        if contest is not None and task.contest_id != contest.id:
            raise ImportDataError(
                "Task \"%s\" already tied to another contest." % task.name)

        if task_has_changed:
            logger.info(
                "Task \"%s\" data has changed, updating it.", task.name)
            update_task(task, new_task, get_statements=not self.no_statement)
        else:
            logger.info("Task \"%s\" data has not changed.", task.name)

        return task


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
        "-n", "--name",
        action="store", type=utf8_decoder,
        help="the new name that will override the task name"
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

    importer = TaskImporter(path=args.target,
                            update=args.update,
                            no_statement=args.no_statement,
                            contest_id=args.contest_id,
                            prefix=args.prefix,
                            override_name=args.name,
                            loader_class=loader_class)
    success = importer.do_import()
    return 0 if success is True else 1


if __name__ == "__main__":
    sys.exit(main())
