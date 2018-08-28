#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2013-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Utility to remove a task.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa

import argparse
import logging
import sys

from cms import utf8_decoder
from cms.db import SessionGen, Task
from cmscontrib.importing import task_from_db, ImportDataError


logger = logging.getLogger(__name__)


def ask(task_name):
    ans = input("This will delete task `%s' and all related data, including "
                "submissions. Are you sure? [y/N] "
                % task_name).strip().lower()
    return ans in ["y", "yes"]


def remove_task(task_name, task_id=None):
    with SessionGen() as session:
        task = task_from_db(session, task_name, task_id)

        if not ask(task_name):
            logger.info("Not removing task `%s'." % task_name)
            return False

        num = task.num
        contest_id = task.contest_id
        session.delete(task)

        # Keeping the tasks' nums to the range 0... n - 1.
        if contest_id is not None:
            following_tasks = session.query(Task)\
                .filter(Task.contest_id == contest_id)\
                .filter(Task.num > num)\
                .all()
            for task in following_tasks:
                task.num -= 1
        session.commit()

        logger.info("Task `%s' removed." % task_name)

    return True


def main():
    """Parse arguments and launch process.

    """
    parser = argparse.ArgumentParser(
        description="Remove a task from the database."
    )

    parser.add_argument("task_name", action="store", type=utf8_decoder,
                        help="short name of the task")
    parser.add_argument("-t", "--task-id", action="store", type=int,
                        help="optional task ID used for disambiguation")

    args = parser.parse_args()

    try:
        success = remove_task(args.task_name, args.task_id)
    except ImportDataError as e:
        logger.error(str(e))
        logger.info("Error while importing, no changes were made.")
        return 1

    return 0 if success is True else 1


if __name__ == "__main__":
    sys.exit(main())
