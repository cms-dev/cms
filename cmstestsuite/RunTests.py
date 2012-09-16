#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2012 Bernard Blackham <bernard@largestprime.net>
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

import os
import sys
import subprocess
import datetime
import re
from argparse import ArgumentParser

from cmstestsuite import get_cms_config, CONFIG, info, sh
from cmstestsuite import add_contest, add_user, add_task, add_testcase, \
     combine_coverage, start_service, start_server, start_ranking_web_server, \
     shutdown_services, restart_service
from cmstestsuite.Test import TestFailure
import cmstestsuite.Tests
from cmscommon.DateTime import get_system_timezone


FAILED_TEST_FILENAME = '.testfailures'

# This stores a mapping from task module to task id.
task_id_map = {}


def start_generic_services():
    start_service("LogService")
    start_service("ResourceService")
    start_service("Checker")
    start_service("Worker")
    start_server("AdminWebServer")
    start_ranking_web_server()


def create_contest():
    info("Creating contest.")
    start_time = datetime.datetime.utcnow()
    stop_time = start_time + datetime.timedelta(1, 0, 0)
    contest_id = add_contest(
        name="testcontest1",
        description="A test contest #1.",
        start=start_time.strftime("%Y-%m-%d %H:%M:%S.%f"),
        stop=stop_time.strftime("%Y-%m-%d %H:%M:%S.%f"),
        timezone=get_system_timezone(),
        token_initial="100",
        token_max="100",
        token_total="100",
        token_min_interval="0",
        token_gen_time="0",
        token_gen_number="0",
        )

    start_service("ScoringService", contest=contest_id)
    start_service("EvaluationService", contest=contest_id)
    start_server("ContestWebServer", contest=contest_id)

    return contest_id


global num_users
num_users = 0


def create_a_user(contest_id):
    global num_users
    num_users += 1

    def enumerify(x):
        if 11 <= x <= 13:
            return 'th'
        return {1: 'st', 2: 'nd', 3: 'rd'}.get(x % 10, 'th')

    info("Creating user.")
    user_id = add_user(
        contest_id=contest_id,
        username="testrabbit%d" % num_users,
        password="kamikaze",
        first_name="Ms. Test",
        last_name="Wabbit the %d%s" % (num_users,
                                       enumerify(num_users)))
    return user_id


def get_task_id(contest_id, user_id, task_module):
    # Create a task in the contest if we haven't already.
    if task_module not in task_id_map:
        # add the task itself.
        task_id = add_task(
            contest_id=contest_id,
            token_initial="100",
            token_max="100",
            token_total="100",
            token_min_interval="0",
            token_gen_time="0",
            token_gen_number="0",
            max_submission_number="100",
            max_usertest_number="100",
            min_submission_interval="0",
            min_usertest_interval="0",
            **task_module.task_info)

        # add the task's test data.
        data_path = os.path.join(
            os.path.dirname(task_module.__file__),
            "data")
        for input_file, output_file, public in task_module.test_cases:
            ipath = os.path.join(data_path, input_file)
            opath = os.path.join(data_path, output_file)
            add_testcase(task_id, ipath, opath, public)

        task_id_map[task_module] = task_id

        info("Creating task %s as id %d" % (
            task_module.task_info['name'], task_id))

        # We need to restart ScoringService to ensure it has picked up the
        # new task.
        restart_service("ScoringService", contest=contest_id)
    else:
        task_id = task_id_map[task_module]

    return task_id


def get_all_tests():
    tests = []
    for i, test in enumerate(cmstestsuite.Tests.ALL_TESTS):
        for lang in test.languages:
            tests.append((test, lang))

    return tests


def load_test_list_from_file(filename):
    """Load a list of tests to execute from the given file. Each line of the
    file should be of the format:

    testname language1

    """
    try:
        with open(filename) as f:
            lines = f.readlines()
    except (IOError, OSError) as e:
        print "Failed to read test list. %s." % (e)
        return None

    errors = False

    name_to_test_map = {}
    for test in cmstestsuite.Tests.ALL_TESTS:
        if test.name in name_to_test_map:
            print "ERROR: Multiple tests with the same name `%s'." % test.name
            errors = True
        name_to_test_map[test.name] = test

    tests = []
    for i, line in enumerate(lines):
        bits = [x.strip() for x in line.split()]
        if len(bits) != 2:
            print "ERROR: %s:%d invalid line: %s" % (filename, i + 1, line)
            errors = True
            continue

        name, lang = bits

        if name not in name_to_test_map:
            print "ERROR: %s:%d invalid test case: %s" % (
                filename, i + 1, name)
            errors = True
            continue

        test = name_to_test_map[name]
        if lang not in test.languages:
            print "ERROR: %s:%d test `%s' does not have language `%s'" % (
                filename, i + 1, name, lang)
            errors = True
            continue

        tests.append((test, lang))

    if errors:
        sys.exit(1)

    return tests


def load_failed_tests():
    list = load_test_list_from_file(FAILED_TEST_FILENAME)
    if list == None:
        sys.exit(1)

    return list


def filter_testcases(orig_test_list, regexes, languages):
    """Filter out skipped test cases from a list."""
    # Define a function that returns true if the given test case matches the
    # criteria.
    def use(test, lang):
        # No regexes means no constraint on test names.
        ok = not regexes
        for regex in regexes:
            if regex.search(test.name):
                ok = True
                break
        if ok and languages:
            ok = lang in languages
        return ok

    # Select only those (test, language) pairs that pass our checks.
    return [(test, lang) for test, lang in orig_test_list if use(test, lang)]


def write_test_case_list(test_list, filename):
    with open(filename, 'w') as f:
        for test, lang in test_list:
            f.write('%s %s\n' % (test.name, lang))


def run_testcases(contest_id, user_id, test_list):
    """Run all test cases specified by the Tests module.

    contest_id and user_id must specify an already-created contest and user
    under which the tests are submitted.

    test_list should be a list of 2-tuples, each representing a test. The first
    element of each tuple is a Test object, and the second is the language for
    which it should be executed.
    """
    info("Running test cases ...")

    failures = []
    num_tests_to_execute = len(test_list)

    # For all tests...
    for i, (test, lang) in enumerate(test_list):
        # This installs the task into the contest if we haven't already.
        task_id = get_task_id(contest_id, user_id, test.task_module)

        info("Running test %d/%d: %s (%s)" % (
            i + 1, num_tests_to_execute,
            test.name, lang))

        try:
            test.run(contest_id, task_id, user_id, lang)
        except TestFailure as f:
            info("  (FAILED: %s)" % f.message)

            # Add this case to our list of failures, if we haven't already.
            failures.append((test, lang, f.message))

    results = "\n\n"
    if not failures:
        results += "================== ALL TESTS PASSED! ==================\n"
    else:
        results += "------ TESTS FAILED: ------\n"

    results += " Executed: %d\n" % num_tests_to_execute
    results += "   Failed: %d\n" % len(failures)
    results += "\n"

    for test, lang, msg in failures:
        results += " %s (%s): %s\n" % (test.name, lang, msg)

    if failures:
        write_test_case_list(
            [(test, lang) for test, lang, _ in failures],
            FAILED_TEST_FILENAME)
        results += "\n"
        results += "Failed tests stored in %s.\n" % FAILED_TEST_FILENAME
        results += "Run again with --retry-failed (or -r) to retry.\n"

    return results


def time_difference(start_time, end_time):
    secs = int((end_time - start_time).total_seconds())
    mins = secs / 60
    secs = secs % 60
    hrs = mins / 60
    mins = mins % 60
    return "Time elapsed: %02d:%02d:%02d" % (hrs, mins, secs)


def config_is_usable(cms_config):
    """Determine if this configuration is suitable for testing."""

    return True


def main():
    parser = ArgumentParser(description="Runs the CMS test suite.")
    parser.add_argument("regex", metavar="regex",
        type=str, nargs='*',
        help="a regex to match to run a subset of tests")
    parser.add_argument("-l", "--languages",
        type=str, action="store", default="",
        help="a comma-separated list of languages to test")
    parser.add_argument("-r", "--retry-failed", action="store_true",
        help="only run failed tests from the previous run (stored in %s)" %
        FAILED_TEST_FILENAME)
    parser.add_argument("-v", "--verbose", action="count",
        help="print debug information (use multiple times for more)")
    args = parser.parse_args()

    CONFIG["VERBOSITY"] = args.verbose

    start_time = datetime.datetime.now()

    # Pre-process our command-line arugments to figure out which tests to run.
    regexes = [re.compile(s) for s in args.regex]
    if args.languages:
        languages = frozenset(args.languages.split(','))
    else:
        languages = frozenset()
    if args.retry_failed:
        test_list = load_failed_tests()
    else:
        test_list = get_all_tests()
    test_list = filter_testcases(test_list, regexes, languages)

    if not test_list:
        info("There are no tests to run! (was your filter too restrictive?)")
        return 0

    if args.retry_failed:
        info("Re-running %d failed tests from last run." % len(test_list))

    # Load config from cms.conf.
    try:
        git_root = subprocess.check_output(
            "git rev-parse --show-toplevel", shell=True,
            stderr=open(os.devnull, "w")).strip()
    except subprocess.CalledProcessError:
        git_root = None
    CONFIG["TEST_DIR"] = git_root
    CONFIG["CONFIG_PATH"] = "%s/examples/cms.conf" % CONFIG["TEST_DIR"]
    if CONFIG["TEST_DIR"] is None:
        CONFIG["CONFIG_PATH"] = "/usr/local/etc/cms.conf"
    cms_config = get_cms_config()

    if not config_is_usable(cms_config):
        return 1

    if CONFIG["TEST_DIR"] is not None:
        # Set up our expected environment.
        os.chdir("%(TEST_DIR)s" % CONFIG)
        os.environ["PYTHONPATH"] = "%(TEST_DIR)s" % CONFIG

        # Clear out any old coverage data.
        info("Clearing old coverage data.")
        sh("python-coverage erase")

    # Fire us up!
    start_generic_services()
    contest_id = create_contest()
    user_id = create_a_user(contest_id)

    # Run all of our test cases.
    test_results = run_testcases(contest_id, user_id, test_list)

    # And good night!
    shutdown_services()
    combine_coverage()

    print test_results

    end_time = datetime.datetime.now()
    print time_difference(start_time, end_time)


if __name__ == "__main__":
    sys.exit(main())
