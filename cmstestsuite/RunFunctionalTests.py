#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2012 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2013-2014 Stefano Maggiolo <s.maggiolo@gmail.com>
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
import re

from argparse import ArgumentParser

from cms import LANGUAGES, utf8_decoder
from cmstestsuite import get_cms_config, CONFIG, info, sh
from cmstestsuite import add_contest, add_existing_user, add_existing_task, \
    add_user, add_task, add_testcase, add_manager, combine_coverage, \
    get_tasks, get_users, start_service, start_server, \
    start_ranking_web_server, shutdown_services, restart_service
from cmstestsuite.Test import TestFailure
import cmstestsuite.Tests
from cmscommon.datetime import get_system_timezone


FAILED_TEST_FILENAME = '.testfailures'

# This stores a mapping from task name to (task id, task_module)
task_id_map = {}


def start_generic_services():
    start_service("LogService")
    start_service("ResourceService")
    start_service("Checker")
    start_service("Worker")
    start_service("ScoringService")
    start_server("AdminWebServer")
    # Just to verify it starts successfully.
    start_ranking_web_server()


def create_contest():
    start_time = datetime.datetime.utcnow()
    stop_time = start_time + datetime.timedelta(1, 0, 0)
    contest_id = add_contest(
        name="testcontest1",
        description="A test contest #1.",
        languages=LANGUAGES,
        start=start_time.strftime("%Y-%m-%d %H:%M:%S.%f"),
        stop=stop_time.strftime("%Y-%m-%d %H:%M:%S.%f"),
        timezone=get_system_timezone(),
        token_mode="finite",
        token_max_number="100",
        token_min_interval="0",
        token_gen_initial="100",
        token_gen_number="0",
        token_gen_interval="1",
        token_gen_max="100",
    )

    info("Created contest %d." % contest_id)

    return contest_id


def start_contest(contest_id):
    start_service("EvaluationService", contest=contest_id)
    start_server("ContestWebServer", contest=contest_id)
    # Just to verify it starts successfully.
    start_service("ProxyService", contest=contest_id)


global num_users
num_users = 0


def create_or_get_user(contest_id):
    global num_users
    num_users += 1

    def enumerify(x):
        if 11 <= x <= 13:
            return 'th'
        return {1: 'st', 2: 'nd', 3: 'rd'}.get(x % 10, 'th')

    username = "testrabbit%d" % num_users

    # Find a user that may already exist (from a previous contest).
    users = get_users(contest_id)
    user_create_args = {
        "username": username,
        "password": "kamikaze",
        "first_name": "Ms. Test",
        "last_name": "Wabbit the %d%s" % (num_users, enumerify(num_users)),
    }
    if username in users:
        user_id = users[username]['id']
        add_existing_user(contest_id, user_id, **user_create_args)
        info("Using existing user with id %d." % user_id)
    else:
        user_id = add_user(contest_id, **user_create_args)
        info("Created user with id %d." % user_id)
    return user_id


def get_task_id(contest_id, user_id, task_module):
    name = task_module.task_info['name']

    # Have we done this before? Pull it out of our cache if so.
    if task_module in task_id_map:
        # Ensure we don't have multiple modules with the same task name.
        assert task_id_map[task_module][1] == task_module

        return task_id_map[name][0]

    task_create_args = {
        "token_mode": "finite",
        "token_max_number": "100",
        "token_min_interval": "0",
        "token_gen_initial": "100",
        "token_gen_number": "0",
        "token_gen_interval": "1",
        "token_gen_max": "100",
        "max_submission_number": "100",
        "max_user_test_number": "100",
        "min_submission_interval": None,
        "min_user_test_interval": None,
    }
    task_create_args.update(task_module.task_info)

    # Find if the task already exists in the contest.
    tasks = get_tasks(contest_id)
    if name in tasks:
        # Then just use the existing one.
        task = tasks[name]
        task_id = task['id']
        task_id_map[name] = (task_id, task_module)
        add_existing_task(contest_id, task_id, **task_create_args)
        return task_id

    # Otherwise, we need to add the task ourselves.
    task_id = add_task(contest_id, **task_create_args)

    # add any managers
    code_path = os.path.join(
        os.path.dirname(task_module.__file__),
        "code")
    if hasattr(task_module, 'managers'):
        for manager in task_module.managers:
            mpath = os.path.join(code_path, manager)
            add_manager(task_id, mpath)

    # add the task's test data.
    data_path = os.path.join(
        os.path.dirname(task_module.__file__),
        "data")
    for num, (input_file, output_file, public) \
            in enumerate(task_module.test_cases):
        ipath = os.path.join(data_path, input_file)
        opath = os.path.join(data_path, output_file)
        add_testcase(task_id, num, ipath, opath, public)

    task_id_map[name] = (task_id, task_module)

    info("Created task %s as id %d" % (name, task_id))

    # We need to restart ProxyService to ensure it reinitializes,
    # picking up the new task and sending it to RWS.
    restart_service("ProxyService", contest=contest_id)

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
    if not os.path.exists(filename):
        return []
    try:
        with io.open(filename, "rt", encoding="utf-8") as f:
            lines = f.readlines()
    except (IOError, OSError) as e:
        print("Failed to read test list. %s." % (e))
        return None

    errors = False

    name_to_test_map = {}
    for test in cmstestsuite.Tests.ALL_TESTS:
        if test.name in name_to_test_map:
            print("ERROR: Multiple tests with the same name `%s'." % test.name)
            errors = True
        name_to_test_map[test.name] = test

    tests = []
    for i, line in enumerate(lines):
        bits = [x.strip() for x in line.split()]
        if len(bits) != 2:
            print("ERROR: %s:%d invalid line: %s" % (filename, i + 1, line))
            errors = True
            continue

        name, lang = bits

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
    list = load_test_list_from_file(FAILED_TEST_FILENAME)
    if list is None:
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
    with io.open(filename, 'wt', encoding="utf-8") as f:
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

    return len(failures) == 0, results


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
    parser = ArgumentParser(description="Runs the CMS functional test suite.")
    parser.add_argument(
        "regex", action="store", type=utf8_decoder, nargs='*', metavar="regex",
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
        "-v", "--verbose", action="count",
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

    if args.dry_run:
        for t in test_list:
            print(t[0].name, t[1])
        return 0

    if args.retry_failed:
        info("Re-running %d failed tests from last run." % len(test_list))

    # Load config from cms.conf.
    try:
        git_root = subprocess.check_output(
            "git rev-parse --show-toplevel", shell=True,
            stderr=io.open(os.devnull, "wb")).strip()
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
    if args.contest is None:
        contest_id = create_contest()
    else:
        contest_id = int(args.contest)
    user_id = create_or_get_user(contest_id)

    start_contest(contest_id)

    # Run all of our test cases.
    passed, test_results = run_testcases(contest_id, user_id, test_list)

    # And good night!
    shutdown_services()
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
