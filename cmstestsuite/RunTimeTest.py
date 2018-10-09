#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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

import argparse
import logging
import os
import sys

import cmstestsuite.tasks.batch_50 as batch_50
from cmstestsuite import CONFIG
from cmstestsuite.Test import Test
from cmstestsuite.Tests import LANG_C
from cmstestsuite.functionaltestframework import FunctionalTestFramework
from cmstestsuite.profiling import \
    PROFILER_KERNPROF, PROFILER_NONE, PROFILER_YAPPI
from cmstestsuite.testrunner import TestRunner


logger = logging.getLogger(__name__)


class TimeTest:
    def __init__(self, name, task, filename, languages, repetitions):
        self.framework = FunctionalTestFramework()

        self.name = name
        self.task_module = task
        self.filename = filename
        self.languages = languages
        self.repetitions = repetitions
        submission_format = list(
            e.strip() for e in task.task_info["submission_format"].split())
        self.submission_format_element = submission_format[0]
        self.submission_ids = []

    def submit(self, task_id, user_id, language):
        # Source files are stored under cmstestsuite/code/.
        path = os.path.join(os.path.dirname(__file__), 'code')

        # Choose the correct file to submit.
        filename = self.filename.replace("%l", language)

        full_path = os.path.join(path, filename)

        # Submit our code.
        self.submission_ids = [
            self.framework.cws_submit(
                task_id, user_id,
                self.submission_format_element, full_path, language)
            for _ in range(self.repetitions)]

    def wait(self, contest_id, unused_language):
        # Wait for evaluation to complete.
        for submission_id in self.submission_ids:
            self.framework.get_evaluation_result(contest_id, submission_id)


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
        "-l", "--cpu_limits", action="append", default=[],
        help="set maximum CPU percentage for a set of services, for example: "
             "'-l .*Server:40' limits servers to use 40%% of a CPU or less; "
             "can be specified multiple times (requires cputool)")
    parser.add_argument(
        "-v", "--verbose", action="count", default=0,
        help="print debug information (use multiple times for more)")
    parser.add_argument(
        "--profiler", choices=[PROFILER_YAPPI, PROFILER_KERNPROF],
        default=PROFILER_NONE, help="set profiler")
    args = parser.parse_args()

    CONFIG["VERBOSITY"] = args.verbose
    CONFIG["COVERAGE"] = False
    CONFIG["PROFILER"] = args.profiler

    test_list = [Test('batch',
                      task=batch_50, filenames=['correct-stdio.%l'],
                      languages=(LANG_C, ), checks=[])
                 for _ in range(args.submissions)]

    cpu_limits = []
    for l in args.cpu_limits:
        if ":" not in l:
            parser.error("CPU limit must be in the form <regex>:<limit>.")
        regex, _, limit = l.rpartition(":")
        try:
            limit = int(limit)
        except ValueError:
            parser.error("CPU limit must be an integer.")
        cpu_limits.append((regex, limit))

    runner = TestRunner(test_list, workers=args.workers,
                        cpu_limits=cpu_limits)
    runner.submit_tests(concurrent_submit_and_eval=False)
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
