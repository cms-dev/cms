#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2016 Amir Keivan Mohtashami <akmohtashami97@gmail.com>
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

"""Utility class to run functional-like tests."""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import datetime
import io
import logging
import os
import random
import subprocess

from cmstestsuite import get_cms_config, CONFIG
from cmstestsuite import add_contest, add_existing_user, add_existing_task, \
    add_user, add_task, add_testcase, add_manager, \
    get_tasks, get_users, initialize_aws
from cmstestsuite.Test import TestFailure
from cmstestsuite.Tests import ALL_LANGUAGES
from cmstestsuite.programstarter import ProgramStarter
from cmscommon.datetime import get_system_timezone


logger = logging.getLogger(__name__)


class TestRunner(object):
    def __init__(self, test_list, contest_id=None, workers=1):
        self.start_time = datetime.datetime.now()

        self.ps = ProgramStarter()

        # Map from task name to (task id, task_module).
        self.task_id_map = {}

        # Random bit to append to object's names to avoid collisions.
        self.rand = random.randint(0, 999999999)

        self.num_users = 0
        self.workers = workers

        # Load config from cms.conf.
        TestRunner.load_cms_conf()

        if CONFIG["TEST_DIR"] is not None:
            # Set up our expected environment.
            os.chdir("%(TEST_DIR)s" % CONFIG)
            os.environ["PYTHONPATH"] = "%(TEST_DIR)s" % CONFIG

        self.start_generic_services()
        initialize_aws(self.rand)

        if contest_id is None:
            self.contest_id = self.create_contest()
        else:
            self.contest_id = int(contest_id)
        self.user_id = self.create_or_get_user()

        self.failures = []
        self.test_list = test_list
        self.n_tests = len(test_list)
        self.n_submissions = sum(len(test.languages) for test in test_list)
        self.n_user_tests = sum(len(test.languages) for test in test_list
                                if test.user_tests)
        logging.info("Have %s submissions and %s user_tests in %s tests...",
                     self.n_submissions, self.n_user_tests, self.n_tests)

    @staticmethod
    def load_cms_conf():
        try:
            git_root = subprocess.check_output(
                "git rev-parse --show-toplevel", shell=True,
                stderr=io.open(os.devnull, "wb")).strip()
        except subprocess.CalledProcessError:
            git_root = None
        CONFIG["TEST_DIR"] = git_root
        CONFIG["CONFIG_PATH"] = "%s/config/cms.conf" % CONFIG["TEST_DIR"]
        if CONFIG["TEST_DIR"] is None:
            CONFIG["CONFIG_PATH"] = "/usr/local/etc/cms.conf"
        return get_cms_config()

    def log_elapsed_time(self):
        end_time = datetime.datetime.now()
        secs = int((end_time - self.start_time).total_seconds())
        mins = secs / 60
        secs = secs % 60
        hrs = mins / 60
        mins = mins % 60
        logger.info("Time elapsed: %02d:%02d:%02d", hrs, mins, secs)

    # Service management.

    def start_generic_services(self):
        self.ps.start("LogService")
        self.ps.start("ResourceService")
        self.ps.start("Checker")
        self.ps.start("ScoringService")
        self.ps.start("AdminWebServer")
        # Just to verify it starts successfully.
        self.ps.start("RankingWebServer", shard=None)
        self.ps.wait()

    def shutdown(self):
        self.ps.stop_all()

    # Data creation.

    def create_contest(self):
        """Create a new contest.

        return (int): contest id.

        """
        start_time = datetime.datetime.utcnow()
        stop_time = start_time + datetime.timedelta(1, 0, 0)
        self.contest_id = add_contest(
            name="testcontest" + str(self.rand),
            description="A test contest #%s." % self.rand,
            languages=list(ALL_LANGUAGES),
            allow_password_authentication="checked",
            start=start_time.strftime("%Y-%m-%d %H:%M:%S.%f"),
            stop=stop_time.strftime("%Y-%m-%d %H:%M:%S.%f"),
            timezone=get_system_timezone(),
            allow_user_tests="checked",
            token_mode="finite",
            token_max_number="100",
            token_min_interval="0",
            token_gen_initial="100",
            token_gen_number="0",
            token_gen_interval="1",
            token_gen_max="100",
        )
        logger.info("Created contest %s.", self.contest_id)
        return self.contest_id

    def create_or_get_user(self):
        """Create a new user if it doesn't exists already.

        return (int): user id.

        """
        self.num_users += 1

        def enumerify(x):
            if 11 <= x <= 13:
                return 'th'
            return {1: 'st', 2: 'nd', 3: 'rd'}.get(x % 10, 'th')

        username = "testrabbit_%d_%d" % (self.rand, self.num_users)

        # Find a user that may already exist (from a previous contest).
        users = get_users(self.contest_id)
        user_create_args = {
            "username": username,
            "password": "kamikaze",
            "method": "plaintext",
            "first_name": "Ms. Test",
            "last_name": "Wabbit the %d%s" % (self.num_users,
                                              enumerify(self.num_users))
        }
        if username in users:
            self.user_id = users[username]['id']
            add_existing_user(self.user_id, **user_create_args)
            logging.info("Using existing user with id %s.", self.user_id)
        else:
            self.user_id = add_user(contest_id=str(self.contest_id),
                                    **user_create_args)
            logging.info("Created user with id %s.", self.user_id)
        return self.user_id

    def create_or_get_task(self, task_module):
        """Create a new task if it does not exist.

        task_module (module): a task as in task/<name>.

        return (int): task id of the new (or existing) task.

        """
        name = task_module.task_info['name'] + str(self.rand)

        # Have we done this before? Pull it out of our cache if so.
        if name in self.task_id_map:
            # Ensure we don't have multiple modules with the same task name.
            assert self.task_id_map[name][1] == task_module

            return self.task_id_map[name][0]

        task_create_args = {
            "token_mode": "finite",
            "token_max_number": "100",
            "token_min_interval": "0",
            "token_gen_initial": "100",
            "token_gen_number": "0",
            "token_gen_interval": "1",
            "token_gen_max": "100",
            "max_submission_number": None,
            "max_user_test_number": None,
            "min_submission_interval": None,
            "min_user_test_interval": None,
        }
        task_create_args.update(task_module.task_info)

        # Update the name with the random bit to avoid conflicts.
        task_create_args["name"] = name

        # Find if the task already exists (the name make sure that if it
        # exists, it is already in out contest).
        tasks = get_tasks()
        if name in tasks:
            # Then just use the existing one.
            task = tasks[name]
            task_id = task['id']
            self.task_id_map[name] = (task_id, task_module)
            add_existing_task(task_id, contest_id=str(self.contest_id),
                              **task_create_args)
            return task_id

        # Otherwise, we need to add the task ourselves.
        task_id = add_task(contest_id=str(self.contest_id), **task_create_args)

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

        self.task_id_map[name] = (task_id, task_module)

        logging.info("Created task %s as id %s", name, task_id)

        return task_id

    # Test execution.

    def _all_submissions(self):
        """Yield all pairs (test, language)."""
        for test in self.test_list:
            for lang in test.languages:
                yield (test, lang)

    def _all_user_tests(self):
        """Yield all pairs (test, language)."""
        for test in self.test_list:
            if test.user_tests:
                for lang in test.languages:
                    yield (test, lang)

    def submit_tests(self):
        """Create the tasks, and submit for all languages in all tests.

        """
        # Pre-install all tasks in the contest. After this, we restart
        # ProxyService to ensure it reinitializes, picking up the new
        # tasks and sending them to RWS.
        for test in self.test_list:
            self.create_or_get_task(test.task_module)
        self.ps.start("EvaluationService", contest=self.contest_id)
        self.ps.start("ContestWebServer", contest=self.contest_id)
        self.ps.start("ProxyService", contest=self.contest_id)
        for shard in xrange(self.workers):
            self.ps.start("Worker", shard)
        self.ps.wait()

        for i, (test, lang) in enumerate(self._all_submissions()):
            logging.info("Submitting submission %s/%s: %s (%s)",
                         i + 1, self.n_submissions, test.name, lang)
            task_id = self.create_or_get_task(test.task_module)
            try:
                test.submit(self.contest_id, task_id, self.user_id, lang)
            except TestFailure as f:
                logging.error("(FAILED (while submitting): %s)", f.message)
                self.failures.append((test, lang, f.message))

        for i, (test, lang) in enumerate(self._all_user_tests()):
            logging.info("Submitting user test  %s/%s: %s (%s)",
                         i + 1, self.n_user_tests, test.name, lang)
            task_id = self.create_or_get_task(test.task_module)
            try:
                test.submit_user_test(
                    self.contest_id, task_id, self.user_id, lang)
            except TestFailure as f:
                logging.error("(FAILED (while submitting): %s)", f.message)
                self.failures.append((test, lang, f.message))

    def wait_for_evaluation(self):
        """Wait for all submissions to evaluate.

        The first will wait longer as ES prioritizes compilations.

        """
        for i, (test, lang) in enumerate(self._all_submissions()):
            logging.info("Waiting for submission %s/%s: %s (%s)",
                         i + 1, self.n_submissions, test.name, lang)
            try:
                test.wait(self.contest_id, lang)
            except TestFailure as f:
                logging.error("(FAILED (while evaluating): %s)", f.message)
                self.failures.append((test, lang, f.message))

        for i, (test, lang) in enumerate(self._all_user_tests()):
            logging.info("Waiting for user test %s/%s: %s (%s)",
                         i + 1, self.n_user_tests, test.name, lang)
            try:
                test.wait_user_test(self.contest_id, lang)
            except TestFailure as f:
                logging.error("(FAILED (while evaluating user test): %s)",
                              f.message)
                self.failures.append((test, lang, f.message))

        return self.failures
