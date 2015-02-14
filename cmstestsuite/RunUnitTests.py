#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2013 Stefano Maggiolo <s.maggiolo@gmail.com>
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

import io
import os
import sys
import subprocess
import datetime
from argparse import ArgumentParser

from cms import utf8_decoder
from cmstestsuite import CONFIG, FrameworkException, info, sh
from cmstestsuite import combine_coverage


FAILED_UNITTEST_FILENAME = '.unittestfailures'


def run_unittests(test_list):
    """Run all needed unit tests.

    test_list ([(string, string)]): a list of test to run in the
                                    format (path, filename.py).
    return (int):
    """
    info("Running unit tests...")

    failures = []
    num_tests_to_execute = len(test_list)

    # For all tests...
    for i, (path, filename) in enumerate(test_list):
        info("Running test %d/%d: %s.%s" % (
            i + 1, num_tests_to_execute,
            path, filename))
        try:
            sh('python-coverage run -p --source=cms %s' %
               os.path.join(path, filename))
        except FrameworkException:
            info("  (FAILED: %s)" % filename)

            # Add this case to our list of failures, if we haven't already.
            failures.append((path, filename))

    results = "\n\n"
    if not failures:
        results += "================== ALL TESTS PASSED! ==================\n"
    else:
        results += "------ TESTS FAILED: ------\n"

    results += " Executed: %d\n" % num_tests_to_execute
    results += "   Failed: %d\n" % len(failures)
    results += "\n"

    for path, filename in failures:
        results += " %s.%s\n" % (path, filename)

    if failures:
        with io.open(FAILED_UNITTEST_FILENAME,
                     "wt", encoding="utf-8") as failed_filename:
            for path, filename in failures:
                failed_filename.write("%s %s\n" % (path, filename))
        results += "\n"
        results += "Failed tests stored in %s.\n" % FAILED_UNITTEST_FILENAME
        results += "Run again with --retry-failed (or -r) to retry.\n"

    return len(failures) == 0, results


def load_test_list_from_file(filename):
    """Load path and names of unittest files from a filename.

    filename (string): the file to load, containing strings in the
                       format <path> <test_filename>.
    return ([(string, string)]): the content of the file.
    """
    if not os.path.exists(filename):
        return []
    try:
        lines = io.open(filename, "rt", encoding="utf-8").readlines()
        return [line.strip().split(" ") for line in lines]
    except (IOError, OSError) as error:
        print("Failed to read test list. %s." % error)
        return None


def get_all_tests():
    tests = []
    for path, _, names in os.walk(os.path.join("cmstestsuite", "unit_tests")):
        for name in names:
            if name.endswith(".py"):
                tests.append((path, name))
    return tests


def load_failed_tests():
    failed_tests = load_test_list_from_file(FAILED_UNITTEST_FILENAME)
    if failed_tests is None:
        sys.exit(1)

    return failed_tests


def time_difference(start_time, end_time):
    secs = int((end_time - start_time).total_seconds())
    mins = secs / 60
    secs = secs % 60
    hrs = mins / 60
    mins = mins % 60
    return "Time elapsed: %02d:%02d:%02d" % (hrs, mins, secs)


def main():
    parser = ArgumentParser(description="Runs the CMS unittest suite.")
    parser.add_argument(
        "-n", "--dry-run", action="store_true",
        help="show what tests would be run, but do not run them")
    parser.add_argument(
        "-v", "--verbose", action="count",
        help="print debug information (use multiple times for more)")
    parser.add_argument(
        "-r", "--retry-failed", action="store_true",
        help="only run failed tests from the previous run (stored in %s)" %
        FAILED_UNITTEST_FILENAME)

    # Unused parameters.
    parser.add_argument(
        "regex", action="store", type=utf8_decoder, nargs='*', metavar="regex",
        help="unused")
    parser.add_argument(
        "-l", "--languages", action="store", type=utf8_decoder, default="",
        help="unused")
    parser.add_argument(
        "-c", "--contest", action="store", type=utf8_decoder,
        help="unused")

    args = parser.parse_args()

    CONFIG["VERBOSITY"] = args.verbose

    start_time = datetime.datetime.now()

    try:
        git_root = subprocess.check_output(
            "git rev-parse --show-toplevel", shell=True,
            stderr=io.open(os.devnull, "wb")).strip()
    except subprocess.CalledProcessError:
        print("Please run the unit tests from the git repository.")
        return 1

    if args.retry_failed:
        test_list = load_failed_tests()
    else:
        test_list = get_all_tests()

    if args.dry_run:
        for t in test_list:
            print(t[0].name, t[1])
        return 0

    if args.retry_failed:
        info("Re-running %d failed tests from last run." % len(test_list))

    # Load config from cms.conf.
    CONFIG["TEST_DIR"] = git_root
    CONFIG["CONFIG_PATH"] = "%s/config/cms.conf" % CONFIG["TEST_DIR"]
    if CONFIG["TEST_DIR"] is None:
        CONFIG["CONFIG_PATH"] = "/usr/local/etc/cms.conf"

    if CONFIG["TEST_DIR"] is not None:
        # Set up our expected environment.
        os.chdir("%(TEST_DIR)s" % CONFIG)
        os.environ["PYTHONPATH"] = "%(TEST_DIR)s" % CONFIG

        # Clear out any old coverage data.
        info("Clearing old coverage data.")
        sh("python-coverage erase")

    # Run all of our test cases.
    passed, test_results = run_unittests(test_list)

    combine_coverage()

    print(test_results)

    end_time = datetime.datetime.now()
    print(time_difference(start_time, end_time))

    if passed:
        return 0
    else:
        return 1

if __name__ == "__main__":
    sys.exit(main())
