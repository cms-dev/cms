#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa

import argparse
import logging
import sys
import os

from cms import utf8_decoder
from cms.db import SessionGen, Statement
from cms.db.filecacher import FileCacher
from cmscontrib.importing import ImportDataError, task_from_db


logger = logging.getLogger(__name__)


def add_statement(task_name, task_id, language_code, statement_file,
                  overwrite):
    logger.info("Adding the statement(language: %s) of task %s "
                "in the database.", language_code, task_name)

    if not os.path.exists(statement_file):
        raise ImportDataError("Statement file (path: %s) does not exist."
                              % statement_file)

    if not statement_file.endswith(".pdf"):
        raise ImportDataError("Statement file should be a pdf file.")

    with SessionGen() as session:
        task = task_from_db(session, task_name, task_id)

        try:
            file_cacher = FileCacher()
            digest = file_cacher.put_file_from_path(
                statement_file,
                "Statement for task %s (lang: %s)" %
                (task_name, language_code))
        except Exception:
            logger.error("Task statement storage failed.", exc_info=True)
        arr = session.query(Statement)\
            .filter(Statement.language == language_code)\
            .filter(Statement.task == task)\
            .all()
        if arr:  # Statement already exists
            if overwrite:
                logger.info("Overwriting already existing statement.")
                session.delete(arr[0])
                session.commit()
            else:
                raise ImportDataError("A statement with given language "
                                      "already exists. Not overwriting.")

        statement = Statement(language_code, digest, task=task)
        session.add(statement)
        session.commit()

    logger.info("Statement added.")
    return True


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
    parser.add_argument("-t", "--task-id", action="store", type=int,
                        help="optional task ID used for disambiguation")
    parser.add_argument("-o", "--overwrite", dest="overwrite",
                        action="store_true",
                        help="overwrite existing statement")
    parser.set_defaults(overwrite=False)

    args = parser.parse_args()

    try:
        success = add_statement(
            args.task_name, args.task_id, args.language_code,
            args.statement_file, args.overwrite)
    except ImportDataError as e:
        logger.error(str(e))
        logger.info("Error while importing, no changes were made.")
        return 1

    return 0 if success is True else 1


if __name__ == "__main__":
    sys.exit(main())
