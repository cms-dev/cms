#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015 Stefano Maggiolo <s.maggiolo@gmail.com>
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

import datetime
import json
import logging
import os
import sys

import cmstestsuite.tasks.batch_100 as batch_100

from cms import LANG_C
from cmstestsuite import cws_submit, get_evaluation_result
from cmstestsuite.Test import Test

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
            for i in range(self.repetitions)]

    def wait(self, contest_id, language):
        # Wait for evaluation to complete.
        for submission_id in self.submission_ids:
            get_evaluation_result(contest_id, submission_id)


def time_difference(start_time, end_time):
    secs = int((end_time - start_time).total_seconds())
    mins = secs / 60
    secs = secs % 60
    hrs = mins / 60
    mins = mins % 60
    return "Time elapsed: %02d:%02d:%02d" % (hrs, mins, secs)


def main():
    test_list = [Test('batch',
                      task=batch_100, filename='correct-stdio.%l',
                      languages=LANG_C, checks=[]) for _ in range(50)]

    runner = TestRunner(test_list)
    runner.startup()

    start_time = datetime.datetime.now()
    runner.submit_tests()
    runner.start_generic_services()
    end_time = datetime.datetime.now()
    logger.info(time_difference(start_time, end_time))

    start_time = datetime.datetime.now()
    failures = runner.wait_for_evaluation()
    end_time = datetime.datetime.now()
    logger.info(time_difference(start_time, end_time))

    if failures == []:
        logger.info("All tests passed!")
        return 0
    else:
        logger.error("Some test failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
