#!/usr/bin/env python3

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

import argparse
import sys

from cms import utf8_decoder
from cms.db import SessionGen, Task


def ask(task_name):
    ans = input("This will delete task `%s' and all related data, including "
                "submissions. Are you sure? [y/N] "
                % task_name).strip().lower()
    return ans in ["y", "yes"]


def remove_task(task_name):
    with SessionGen() as session:
        task = session.query(Task)\
            .filter(Task.name == task_name).first()
        if not task:
            print("No task called `%s' found." % task_name)
            return False
        if not ask(task_name):
            print("Not removing task `%s'." % task_name)
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
        print("Task `%s' removed." % task_name)

    return True


def main():
    """Parse arguments and launch process.

    """
    parser = argparse.ArgumentParser(
        description="Remove a task from the database."
    )

    parser.add_argument(
        "task_name",
        action="store", type=utf8_decoder,
        help="short name of the task"
    )

    args = parser.parse_args()

    success = remove_task(task_name=args.task_name)
    return 0 if success is True else 1


if __name__ == "__main__":
    sys.exit(main())
