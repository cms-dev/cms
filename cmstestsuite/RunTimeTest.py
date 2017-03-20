#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2016 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import json
import logging
import os
import sys

import cmstestsuite.tasks.batch_50 as batch_50

from cmstestsuite import CONFIG, cws_submit, get_evaluation_result
from cmstestsuite.Test import Test
from cmstestsuite.Tests import LANG_C

from testrunner import TestRunner


logger = logging.getLogger(__name__)


class TimeTest(object):
    def __init__(self, name, task, filename, languages, repetitions):
        self.name = name
        self.task_module = task
        self.filename = filename
        self.languages = languages
        self.repetitions = repetitions
        submission_format = json.loads(task.task_info["submission_format"])
        self.submission_format_element = submission_format[0]
        self.submission_ids = []

    def submit(self, contest_id, task_id, user_id, language):
        # Source files are stored under cmstestsuite/code/.
        path = os.path.join(os.path.dirname(__file__), 'code')

        # Choose the correct file to submit.
        filename = self.filename.replace("%l", language)

        full_path = os.path.join(path, filename)

        # Submit our code.
        self.submission_ids = [
            cws_submit(contest_id, task_id, user_id,
                       self.submission_format_element,
                       full_path, language)
            for _ in range(self.repetitions)]

    def wait(self, contest_id, unused_language):
        # Wait for evaluation to complete.
        for submission_id in self.submission_ids:
            get_evaluation_result(contest_id, submission_id)


def main():
    parser = argparse.ArgumentParser(
        description="Runs the CMS functional test suite.")
    parser.add_argument(
        "-s", "--submissions", action="store", type=int, default=50,
        help="set the number of submissions to submit (default 50)")
    parser.add_argument(
        "-w", "--workers", action="store", type=int, default=4,
        help="set the number of workers to use (default 4)")
    parser.add_argument(
        "-v", "--verbose", action="count",
        help="print debug information (use multiple times for more)")
    args = parser.parse_args()

    CONFIG["VERBOSITY"] = args.verbose
    CONFIG["COVERAGE"] = False

    test_list = [Test('batch',
                      task=batch_50, filenames=['correct-stdio.%l'],
                      languages=(LANG_C, ), checks=[])
                 for _ in range(args.submissions)]

    runner = TestRunner(test_list, workers=args.workers)
    runner.submit_tests()
    runner.log_elapsed_time()

    failures = runner.wait_for_evaluation()
    runner.log_elapsed_time()

    if failures == []:
        logger.info("All tests passed!")
        return 0
    else:
        logger.error("Some test failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
