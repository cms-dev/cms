#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2016 Peyman Jabbarzade Ganje <peyman.jabarzade@gmail.com>
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

"""This script add multiple testcases.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import logging
import sys
import re
import zipfile

from cms import utf8_decoder
from cms.db import SessionGen, Dataset, Testcase, Task, Contest
from cms.db.filecacher import FileCacher

logger = logging.getLogger(__name__)


def main():
    """Parse arguments and launch process.

    """
    parser = argparse.ArgumentParser(description="Add an admin to CMS.")
    parser.add_argument("task_name", action="store", type=utf8_decoder,
                        help="name of task which tests will be attached to")
    parser.add_argument("file", action="store", type=utf8_decoder,
                        help="a zip file which contains tests")
    parser.add_argument("inputtemplate", action="store", type=utf8_decoder,
                        help="format of input")
    parser.add_argument("outputtemplate", action="store", type=utf8_decoder,
                        help="format of output")
    parser.add_argument("-p", "--public", action="store_true",
                        help="if tests should be public")
    parser.add_argument("-o", "--overwrite", action="store_true",
                        help="if tests can overwrite existing tests")
    parser.add_argument("-c", "--contest_name", action="store",
                        help="name of contest which tests will be attached to")
    args = parser.parse_args()

    with SessionGen() as session:
        dataset = session.query(Dataset)\
            .join(Dataset.task)\
            .filter(Task.name == args.task_name).first()
        if not dataset:
            print("No task called %s found." % args.task_name)
            return
        task = dataset.task
        if args.contest_name is not None:
            contest = session.query(Contest)\
                .filter(Contest.name == args.contest_name).first()
            if task.contest != contest:
                print("%s is not in %s" % (args.task_name, args.contest_name))
                return False
        archive = args.file

        # Get input/output file names templates
        input_template = args.inputtemplate
        output_template = args.outputtemplate
        input_re = re.compile(re.escape(input_template).replace("\\*",
                              "(.*)") + "$")
        output_re = re.compile(re.escape(output_template).replace("\\*",
                               "(.*)") + "$")

        task_name = task.name

        with zipfile.ZipFile(archive, "r") as archive_zfp:
            tests = dict()
            # Match input/output file names to testcases' codenames.
            for filename in archive_zfp.namelist():
                match = input_re.match(filename)
                if match:
                    codename = match.group(1)
                    if codename not in tests:
                        tests[codename] = [None, None]
                    tests[codename][0] = filename
                else:
                    match = output_re.match(filename)
                    if match:
                        codename = match.group(1)
                        if codename not in tests:
                            tests[codename] = [None, None]
                        tests[codename][1] = filename

            skipped_tc = []
            overwritten_tc = []
            added_tc = []
            for codename, testdata in tests.iteritems():
                # If input or output file isn't found, skip it.
                if not testdata[0] or not testdata[1]:
                    continue

                # Check, whether current testcase already exists.
                if codename in dataset.testcases:
                    # If we are allowed, remove existing testcase.
                    # If not - skip this testcase.
                    if args.overwrite:
                        testcase = dataset.testcases[codename]
                        session.delete(testcase)
                        session.commit()
                        overwritten_tc.append(codename)
                    else:
                        skipped_tc.append(codename)
                        continue

                # Add current testcase.
                input_ = archive_zfp.read(testdata[0])
                output = archive_zfp.read(testdata[1])
                file_cacher = FileCacher()
                input_digest = file_cacher.put_file_content(
                        input_,
                        "Testcase input for task %s" % task_name)
                output_digest = file_cacher.put_file_content(
                        output,
                        "Testcase output for task %s" % task_name)

                testcase = Testcase(codename, args.public, input_digest,
                                    output_digest, dataset=dataset)
                session.add(testcase)
                session.commit()

                if codename not in overwritten_tc:
                    added_tc.append(codename)

    return True


if __name__ == "__main__":
    sys.exit(0 if main() is True else 1)
