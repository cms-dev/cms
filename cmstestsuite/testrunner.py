#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2016 Amir Keivan Mohtashami <akmohtashami97@gmail.com>
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

"""Utility class to run functional-like tests."""

import datetime
import logging
import os
import subprocess

from cms import TOKEN_MODE_FINITE
from cmscommon.datetime import get_system_timezone
from cmstestsuite import CONFIG
from cmstestsuite.Test import TestFailure
from cmstestsuite.Tests import ALL_LANGUAGES
from cmstestsuite.functionaltestframework import FunctionalTestFramework
from cmstestsuite.programstarter import ProgramStarter


logger = logging.getLogger(__name__)


class TestRunner:
    def __init__(self, test_list, contest_id=None, workers=1, cpu_limits=None):
        self.start_time = datetime.datetime.now()
        self.last_end_time = self.start_time

        self.framework = FunctionalTestFramework()
        self.load_cms_conf()

        self.ps = ProgramStarter(cpu_limits)

        # Map from task name to (task id, task_module).
        self.task_id_map = {}

        # String to append to objects' names to avoid collisions. Will be the
        # first positive integer i for which admin_<i> is not already
        # registered, and we will hope that if the admin name doesn't clash, no
        # other name will.
        self.suffix = None

        self.num_users = 0
        self.workers = workers

        if CONFIG["TEST_DIR"] is not None:
            # Set up our expected environment.
            os.chdir("%(TEST_DIR)s" % CONFIG)
            os.environ["PYTHONPATH"] = "%(TEST_DIR)s" % CONFIG

        self.start_generic_services()
        self.suffix = self.framework.initialize_aws()

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

    def load_cms_conf(self):
        try:
            git_root = subprocess.check_output(
                "git rev-parse --show-toplevel", shell=True,
                stderr=subprocess.DEVNULL).decode('utf-8').strip()
        except subprocess.CalledProcessError:
            git_root = None
        CONFIG["TEST_DIR"] = git_root
        CONFIG["CONFIG_PATH"] = "%s/config/cms.conf" % CONFIG["TEST_DIR"]
        if CONFIG["TEST_DIR"] is None:
            CONFIG["CONFIG_PATH"] = "/usr/local/etc/cms.conf"

        # Override CMS config path when environment variable is present
        CMS_CONFIG_ENV_VAR = "CMS_CONFIG"
        if CMS_CONFIG_ENV_VAR in os.environ:
            CONFIG["CONFIG_PATH"] = os.environ[CMS_CONFIG_ENV_VAR]

        return self.framework.get_cms_config()

    def log_elapsed_time(self):
        end_time = datetime.datetime.now()
        logger.info("Time elapsed: %s, since last: %s",
                    end_time - self.start_time,
                    end_time - self.last_end_time)
        self.last_end_time = end_time

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
        self.contest_id = self.framework.add_contest(
            name="testcontest_%s" % self.suffix,
            description="A test contest #%s." % self.suffix,
            languages=list(ALL_LANGUAGES),
            allow_password_authentication="checked",
            start=start_time.strftime("%Y-%m-%d %H:%M:%S.%f"),
            stop=stop_time.strftime("%Y-%m-%d %H:%M:%S.%f"),
            timezone=get_system_timezone(),
            allow_user_tests="checked",
            token_mode=TOKEN_MODE_FINITE,
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

        username = "testrabbit_%s_%d" % (self.suffix, self.num_users)

        # Find a user that may already exist (from a previous contest).
        users = self.framework.get_users(self.contest_id)
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
            self.framework.add_existing_user(self.user_id, **user_create_args)
            logging.info("Using existing user with id %s.", self.user_id)
        else:
            self.user_id = self.framework.add_user(
                contest_id=str(self.contest_id), **user_create_args)
            logging.info("Created user with id %s.", self.user_id)
        return self.user_id

    def create_or_get_task(self, task_module):
        """Create a new task if it does not exist.

        task_module (module): a task as in task/<name>.

        return (int): task id of the new (or existing) task.

        """
        name = "%s_%s" % (task_module.task_info['name'], self.suffix)

        # Have we done this before? Pull it out of our cache if so.
        if name in self.task_id_map:
            # Ensure we don't have multiple modules with the same task name.
            assert self.task_id_map[name][1] == task_module

            return self.task_id_map[name][0]

        task_create_args = {
            "token_mode": TOKEN_MODE_FINITE,
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
        tasks = self.framework.get_tasks()
        if name in tasks:
            # Then just use the existing one.
            task = tasks[name]
            task_id = task['id']
            self.task_id_map[name] = (task_id, task_module)
            self.framework.add_existing_task(
                task_id, contest_id=str(self.contest_id), **task_create_args)
            return task_id

        # Otherwise, we need to add the task ourselves.
        task_id = self.framework.add_task(
            contest_id=str(self.contest_id), **task_create_args)

        # add any managers
        code_path = os.path.join(
            os.path.dirname(task_module.__file__),
            "code")
        if hasattr(task_module, 'managers'):
            for manager in task_module.managers:
                mpath = os.path.join(code_path, manager)
                self.framework.add_manager(task_id, mpath)

        # add the task's test data.
        data_path = os.path.join(
            os.path.dirname(task_module.__file__),
            "data")
        for num, (input_file, output_file, public) \
                in enumerate(task_module.test_cases):
            ipath = os.path.join(data_path, input_file)
            opath = os.path.join(data_path, output_file)
            self.framework.add_testcase(task_id, num, ipath, opath, public)

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

    def submit_tests(self, concurrent_submit_and_eval=True):
        """Create the tasks, and submit for all languages in all tests.

        concurrent_submit_and_eval (boolean): if False, start ES only
            after CWS received all the submissions, with the goal of
            having a clearer view of the time each step takes.

        """
        # Pre-install all tasks in the contest. We start the other services
        # after this to ensure they pick up the new tasks before receiving
        # data for them.
        for test in self.test_list:
            self.create_or_get_task(test.task_module)

        # We start now only the services we need in order to submit and
        # we start the other ones while the submissions are being sent
        # out. A submission can arrive after ES's first sweep, but
        # before CWS connects to ES; if so, it will be ignored until
        # ES's second sweep, making the test flaky due to timeouts. By
        # waiting for ES to start before submitting, we ensure CWS can
        # send the notification for all submissions.
        self.ps.start("ContestWebServer", contest=self.contest_id)
        if concurrent_submit_and_eval:
            self.ps.start("EvaluationService", contest=self.contest_id)
        self.ps.wait()

        self.ps.start("ProxyService", contest=self.contest_id)
        for shard in range(self.workers):
            self.ps.start("Worker", shard)

        for i, (test, lang) in enumerate(self._all_submissions()):
            logging.info("Submitting submission %s/%s: %s (%s)",
                         i + 1, self.n_submissions, test.name, lang)
            task_id = self.create_or_get_task(test.task_module)
            try:
                test.submit(task_id, self.user_id, lang)
            except TestFailure as f:
                logging.error("(FAILED (while submitting): %s)", f)
                self.failures.append((test, lang, str(f)))

        for i, (test, lang) in enumerate(self._all_user_tests()):
            logging.info("Submitting user test  %s/%s: %s (%s)",
                         i + 1, self.n_user_tests, test.name, lang)
            task_id = self.create_or_get_task(test.task_module)
            try:
                test.submit_user_test(task_id, self.user_id, lang)
            except TestFailure as f:
                logging.error("(FAILED (while submitting): %s)", f)
                self.failures.append((test, lang, str(f)))

        if not concurrent_submit_and_eval:
            self.ps.start("EvaluationService", contest=self.contest_id)
        self.ps.wait()

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
                logging.error("(FAILED (while evaluating): %s)", f)
                self.failures.append((test, lang, str(f)))

        for i, (test, lang) in enumerate(self._all_user_tests()):
            logging.info("Waiting for user test %s/%s: %s (%s)",
                         i + 1, self.n_user_tests, test.name, lang)
            try:
                test.wait_user_test(self.contest_id, lang)
            except TestFailure as f:
                logging.error("(FAILED (while evaluating user test): %s)", f)
                self.failures.append((test, lang, str(f)))

        return self.failures
