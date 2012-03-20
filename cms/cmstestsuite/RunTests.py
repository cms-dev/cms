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
import subprocess
import datetime

from cmstestsuite.util import read_cms_config, CONFIG, info, sh
from cmstestsuite.util import add_contest, add_user, add_task, add_testcase, \
     combine_coverage, start_service, start_server, start_ranking_web_server, \
     shutdown_services, restart_service
from cmstestsuite.Test import TestFailure


def start_generic_services():
    start_service("LogService")
    start_service("ResourceService")
    start_service("Checker")
    start_service("Worker")
    start_server("AdminWebServer")
    start_ranking_web_server()


def create_contest():
    info("Creating contest.")
    start_time = datetime.datetime.now()
    end_time = start_time + datetime.timedelta(1, 0, 0)
    contest_id = add_contest(
        name="testcontest1",
        description="A test contest #1.",
        start=start_time.strftime("%d/%m/%Y %H:%M:%S"),
        end=end_time.strftime("%d/%m/%Y %H:%M:%S"),
        token_initial="100",
        #token_max="",
        #token_total="",
        #token_min_interval="",
        #token_gen_time="",
        #token_gen_number="",
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


def run_testcases(contest_id, user_id):
    info("Running test cases ...")

    import Tests
    task_id_map = {}

    failures = []

    for i, test in enumerate(Tests.ALL_TESTS):
        # Create a task in the contest if we haven't already.
        if test.task_module not in task_id_map:

            # add the task itself.
            task_id = add_task(
                contest_id=contest_id,
                **test.task_module.task_info)

            # add the task's test data.
            data_path = os.path.join(
                os.path.dirname(test.task_module.__file__),
                "data")
            for input_file, output_file, public in test.task_module.test_cases:
                ipath = os.path.join(data_path, input_file)
                opath = os.path.join(data_path, output_file)
                add_testcase(task_id, ipath, opath, public)

            task_id_map[test.task_module] = task_id

            # We need to restart ScoringService to ensure it has picked up the
            # new task.
            restart_service("ScoringService", contest=contest_id)
        else:
            task_id = task_id_map[test.task_module]

        info("Creating task %s as id %d" % (
            test.task_module.task_info['name'], task_id))

        # For each language supported by the test, run it.
        for lang in test.languages:
            try:
                test.run(contest_id, task_id, user_id, lang)
            except TestFailure as f:
                # Add this case to our list of failures, if we haven't already.
                if not (failures and failures[-1][0] == i):
                    failures.append((i, test, []))
                # Mark that it failed for this language.
                failures[-1][2].append((lang, f.message))

    return failures


def print_results(results):
    print "\n\n"
    if not results:
        print "================== ALL TESTS PASSED! =================="
    else:
        print "------ TESTS FAILED: ------"
        for _, test, lang_failures in results:
            for lang, msg in lang_failures:
                print " %s (%s): %s" % (test.name, lang, msg)
    print "\n"


if __name__ == "__main__":
    # Load config from cms.conf.
    git_root = subprocess.check_output(
        "git rev-parse --show-toplevel", shell=True).strip()
    CONFIG["TEST_DIR"] = git_root
    CONFIG["CONFIG_PATH"] = "cms/examples/cms.conf"
    read_cms_config()

    # Set up our expected environment.
    os.chdir("%(TEST_DIR)s/cms" % CONFIG)
    os.environ["PYTHONPATH"] = "%(TEST_DIR)s/cms" % CONFIG

    # Clear out any old coverage data.
    info("Clearing old coverage data.")
    sh("python-coverage erase")

    # Fire us up!
    start_generic_services()
    contest_id = create_contest()
    user_id = create_a_user(contest_id)

    # Run all of our test cases.
    test_results = run_testcases(contest_id, user_id)

    # And good night!
    shutdown_services()
    combine_coverage()

    print_results(test_results)
