#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2012 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2013-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2014 Luca Versari <veluca93@gmail.com>
# Copyright © 2016 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2022 William Di Luigi <williamdiluigi@gmail.com>
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
import re
import sys

from cms import utf8_decoder
from cmstestsuite import CONFIG
from cmstestsuite.Tests import ALL_TESTS
from cmstestsuite.coverage import clear_coverage, combine_coverage
from cmstestsuite.profiling import \
    PROFILER_KERNPROF, PROFILER_NONE, PROFILER_YAPPI
from cmstestsuite.testrunner import TestRunner


logger = logging.getLogger(__name__)


FAILED_TEST_FILENAME = '.testfailures'


def load_test_list_from_file(filename):
    """Load a list of tests to execute from the given file. Each line of the
    file should be of the format:

    testname language1

    """
    if not os.path.exists(filename):
        return []
    try:
        with open(filename, "rt", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as e:
        print("Failed to read test list. %s." % (e))
        return None

    errors = False

    name_to_test_map = {}
    for test in ALL_TESTS:
        if test.name in name_to_test_map:
            print("ERROR: Multiple tests with the same name `%s'." % test.name)
            errors = True
        name_to_test_map[test.name] = test

    tests = []
    for i, line in enumerate(lines):
        bits = [x.strip() for x in line.split(" ", 1)]
        if len(bits) != 2:
            print("ERROR: %s:%d invalid line: %s" % (filename, i + 1, line))
            errors = True
            continue

        name, lang = bits
        if lang == "None":
            lang = None

        if name not in name_to_test_map:
            print("ERROR: %s:%d invalid test case: %s" %
                  (filename, i + 1, name))
            errors = True
            continue

        test = name_to_test_map[name]
        if lang not in test.languages:
            print("ERROR: %s:%d test `%s' does not have language `%s'" %
                  (filename, i + 1, name, lang))
            errors = True
            continue

        tests.append((test, lang))

    if errors:
        sys.exit(1)

    return tests


def load_failed_tests():
    test_lang_list = load_test_list_from_file(FAILED_TEST_FILENAME)
    if test_lang_list is None:
        sys.exit(1)

    tests = set(test_lang[0] for test_lang in test_lang_list)
    test_list = []
    for new_test in tests:
        langs = new_test.languages
        new_test.languages = []
        for test, lang in test_lang_list:
            if new_test == test and lang in langs:
                new_test.languages.append(lang)
        test_list.append(new_test)

    return test_list


def filter_tests(orig_test_list, regexes, languages):
    """Filter out skipped test cases from a list."""
    # Select only those (test, language) pairs that pass our checks.
    new_test_list = []
    for test in orig_test_list:
        # No regexes means no constraint on test names.
        ok = not regexes
        for regex in regexes:
            if regex.search(test.name):
                ok = True
                break
        if ok:
            remaining_languages = test.languages
            if languages:
                remaining_languages = tuple(lang
                                            for lang in test.languages
                                            if lang in languages)
            if remaining_languages != ():
                test.languages = remaining_languages
                new_test_list.append(test)
    return new_test_list


def write_test_case_list(test_list, filename):
    with open(filename, 'wt', encoding="utf-8") as f:
        for test, lang in test_list:
            f.write('%s %s\n' % (test.name, lang))


def main():
    parser = argparse.ArgumentParser(
        description="Runs the CMS functional test suite.")
    parser.add_argument(
        "regex", action="store", type=utf8_decoder, nargs='*',
        help="a regex to match to run a subset of tests")
    parser.add_argument(
        "-l", "--languages", action="store", type=utf8_decoder, default="",
        help="a comma-separated list of languages to test")
    parser.add_argument(
        "-c", "--contest", action="store", type=utf8_decoder,
        help="use an existing contest (and the tasks in it)")
    parser.add_argument(
        "-r", "--retry-failed", action="store_true",
        help="only run failed tests from the previous run (stored in %s)" %
        FAILED_TEST_FILENAME)
    parser.add_argument(
        "-n", "--dry-run", action="store_true",
        help="show what tests would be run, but do not run them")
    parser.add_argument(
        "-v", "--verbose", action="count", default=0,
        help="print debug information (use multiple times for more)")
    g = parser.add_mutually_exclusive_group()
    g.add_argument(
        "--coverage", action="store", type=utf8_decoder,
        help="path to the XML coverage report file (if not specified, "
             "coverage is not computed)")
    g.add_argument(
        "--profiler", choices=[PROFILER_YAPPI, PROFILER_KERNPROF],
        default=PROFILER_NONE, help="set profiler")

    args = parser.parse_args()

    CONFIG["VERBOSITY"] = args.verbose
    CONFIG["COVERAGE"] = args.coverage
    CONFIG["PROFILER"] = args.profiler

    # Pre-process our command-line arguments to figure out which tests to run.
    regexes = [re.compile(s) for s in args.regex]
    if args.languages:
        languages = frozenset(args.languages.split(','))
    else:
        languages = frozenset()
    if args.retry_failed:
        test_list = load_failed_tests()
    else:
        test_list = ALL_TESTS
    test_list = filter_tests(test_list, regexes, languages)

    if not test_list:
        logger.info(
            "There are no tests to run! (was your filter too restrictive?)")
        return 0

    tests = 0
    for test in test_list:
        for language in test.languages:
            if args.dry_run:
                logger.info("Test %s in %s.", test.name, language)
            tests += 1
        if test.user_tests:
            for language in test.languages:
                if args.dry_run:
                    logger.info("Test %s in %s (for usertest).",
                                test.name, language)
                tests += 1
    if args.dry_run:
        return 0

    if args.retry_failed:
        logger.info(
            "Re-running %s failed tests from last run.", len(test_list))

    clear_coverage()

    # Startup the test runner.
    runner = TestRunner(test_list, contest_id=args.contest, workers=4)

    # Submit and wait for all tests to complete.
    runner.submit_tests()
    failures = runner.wait_for_evaluation()
    write_test_case_list(
        [(test, lang) for test, lang, _ in failures],
        FAILED_TEST_FILENAME)

    # And good night!
    runner.shutdown()
    runner.log_elapsed_time()
    combine_coverage()

    logger.info("Executed: %s", tests)
    logger.info("Failed: %s", len(failures))
    if not failures:
        logger.info("All tests passed!")
        return 0
    else:
        logger.error("Some test failed!")
        logger.info("Run again with --retry-failed (or -r) to retry.")
        logger.info("Failed tests:")
        for test, lang, msg in failures:
            logger.info("%s (%s): %s\n", test.name, lang, msg)
        return 1


if __name__ == "__main__":
    sys.exit(main())
