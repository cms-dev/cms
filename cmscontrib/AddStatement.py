#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
# Copyright © 2016 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2018 William Di Luigi <williamdiluigi@gmail.com>
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

"""This script adds a statement to a specific task in the database.

"""

import argparse
import logging
import os
import sys

from cms import utf8_decoder, STATEMENT_TYPE_PDF, STATEMENT_TYPE_HTML, \
    STATEMENT_TYPE_MD
from cms.db import SessionGen, Statement, Task
from cms.db.filecacher import FileCacher


logger = logging.getLogger(__name__)


def add_statement(task_name, language_code, statement_type, statement_file,
                  overwrite):
    logger.info("Adding the statement(language: %s) of task %s "
                "in the database.", language_code, task_name)

    if statement_type is None:
        return False
    if not os.path.exists(statement_file):
        logger.error("Statement file (path: %s) does not exist.",
                     statement_file)
        return False

    with SessionGen() as session:
        task = session.query(Task)\
            .filter(Task.name == task_name).first()
        if not task:
            logger.error("No task named %s", task_name)
            return False
        try:
            file_cacher = FileCacher()
            digest = file_cacher.put_file_from_path(
                statement_file,
                "%s Statement (lang: %s) for task %s" % (
                    statement_type.upper(), language_code, task_name))
        except Exception:
            logger.error("Task statement storage failed.", exc_info=True)
        arr = session.query(Statement)\
            .filter(Statement.language == language_code)\
            .filter(Statement.statement_type == statement_type)\
            .filter(Statement.task == task)\
            .all()
        if arr:  # Statement already exists
            if overwrite:
                logger.info("Overwriting already existing statement.")
                session.delete(arr[0])
                session.commit()
            else:
                logger.error("A statement of the given type and language "
                             "already exists. Not overwriting.")
                return False
        statement = Statement(language_code, statement_type, digest, task=task)
        session.add(statement)
        session.commit()

    logger.info("Statement added.")
    return True


def get_statement_type(statement_file):
    if statement_file.endswith(".pdf"):
        return STATEMENT_TYPE_PDF
    elif statement_file.endswith(".html"):
        return STATEMENT_TYPE_HTML
    elif statement_file.endswith(".md"):
        return STATEMENT_TYPE_MD
    else:
        logger.error("Statement file should be a pdf / html / md file.")
        return None


def main():
    """Parse arguments and launch process.

    """
    parser = argparse.ArgumentParser(description="Add a statement to CMS.")
    parser.add_argument("task_name", action="store", type=utf8_decoder,
                        help="short name of the task")
    parser.add_argument("language_code", action="store", type=utf8_decoder,
                        help="language code of statement, e.g. en")
    parser.add_argument("statement_file", action="store", type=utf8_decoder,
                        help="absolute/relative path of statement file")
    parser.add_argument("-o", "--overwrite", dest="overwrite",
                        action="store_true",
                        help="overwrite existing statement")
    parser.set_defaults(overwrite=False)

    args = parser.parse_args()

    success = add_statement(args.task_name, args.language_code,
                            get_statement_type(args.statement_file),
                            args.statement_file, args.overwrite)
    return 0 if success is True else 1


if __name__ == "__main__":
    sys.exit(main())
