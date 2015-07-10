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
from cms.db import SessionGen, Task
from cms.db.filecacher import FileCacher

from cmscontrib.loaders import choose_loader, build_epilog

from . import BaseImporter

logger = logging.getLogger(__name__)


class TaskImporter(BaseImporter):

    """This script creates a task

    """

    def __init__(self, path, update, no_statement, loader_class):
        self.file_cacher = FileCacher()
        self.update = update
        self.no_statement = no_statement
        self.loader = loader_class(os.path.realpath(path), self.file_cacher)

    def do_import(self):
        """Get the task from the TaskLoader and store it."""

        # Get the task
        task = self.loader.get_task(get_statement=not self.no_statement)
        if task is None:
            return

        # Store
        logger.info("Creating task on the database.")
        with SessionGen() as session:
            # Check whether the task already exists
            old_task = session.query(Task) \
                              .filter(Task.name == task.name) \
                              .first()
            if old_task is not None:
                if self.update:
                    if self.loader.task_has_changed():
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
                session.add(task)
            session.commit()
            task_id = task.id

        logger.info("Import finished (task id: %s).", task_id)


def main():
    """Parse arguments and launch process."""

    parser = argparse.ArgumentParser(
        description="Create a new or update an existing task in CMS.",
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
        loader_class=loader_class
    ).do_import()


if __name__ == "__main__":
    main()
