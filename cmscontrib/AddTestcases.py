#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2016 Peyman Jabbarzade Ganje <peyman.jabarzade@gmail.com>
# Copyright © 2016 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""This script adds multiple testcases from the filesystem to an
existing dataset.

"""

import argparse
import logging
import re
import sys

from cms import utf8_decoder
from cms.db import Contest, Dataset, SessionGen, Task
from cms.db.filecacher import FileCacher
from cmscommon.importers import import_testcases_from_zipfile


logger = logging.getLogger(__name__)


def add_testcases(archive, input_template, output_template,
                  task_name, dataset_description=None, contest_name=None,
                  public=False, overwrite=False):
    with SessionGen() as session:
        task = session.query(Task)\
            .filter(Task.name == task_name).first()
        if not task:
            logger.error("No task called %s found." % task_name)
            return False
        dataset = task.active_dataset
        if dataset_description is not None:
            dataset = session.query(Dataset)\
                .filter(Dataset.task_id == task.id)\
                .filter(Dataset.description == dataset_description)\
                .first()
            if not dataset:
                logger.error("No dataset called %s found."
                             % dataset_description)
                return False
        if contest_name is not None:
            contest = session.query(Contest)\
                .filter(Contest.name == contest_name).first()
            if task.contest != contest:
                logger.error("%s is not in %s" %
                             (task_name, contest_name))
                return False

        file_cacher = FileCacher()

        # Get input/output file names templates
        input_re = re.compile(
            re.escape(input_template).replace("\\*", "(.*)") + "$")
        output_re = re.compile(
            re.escape(output_template).replace("\\*", "(.*)") + "$")

        try:
            successful_subject, successful_message = \
                import_testcases_from_zipfile(
                    session, file_cacher, dataset,
                    archive, input_re, output_re, overwrite, public)
        except Exception as error:
            logger.error(str(error))
            return False

        logger.info(successful_subject)
        logger.info(successful_message)
    return True


def main():
    """Parse arguments and launch process."""
    parser = argparse.ArgumentParser(description="Add testcases to CMS.")
    parser.add_argument("task_name", action="store", type=utf8_decoder,
                        help="task testcases will be attached to")
    parser.add_argument("file", action="store", type=utf8_decoder,
                        help="a zip file which contains testcases")
    parser.add_argument("inputtemplate", action="store", type=utf8_decoder,
                        help="format of input")
    parser.add_argument("outputtemplate", action="store", type=utf8_decoder,
                        help="format of output")
    parser.add_argument("-p", "--public", action="store_true",
                        help="if testcases should be public")
    parser.add_argument("-o", "--overwrite", action="store_true",
                        help="if testcases can overwrite existing testcases")
    parser.add_argument("-c", "--contest_name", action="store",
                        help="contest which testcases will be attached to")
    parser.add_argument("-d", "--dataset_description", action="store",
                        help="dataset testcases will be attached to")
    args = parser.parse_args()

    success = add_testcases(
        args.file, args.inputtemplate, args.outputtemplate,
        args.task_name, args.dataset_description, args.contest_name,
        args.public, args.overwrite)
    return 0 if success is True else 1


if __name__ == "__main__":
    sys.exit(main())
