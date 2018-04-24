#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2015-2016 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
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

"""Usertest-related handlers for CWS for a specific task.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa
from six import iterkeys, iteritems

import logging
import re

import tornado.web

from cms import config
from cms.db import UserTest, UserTestFile, UserTestManager, UserTestResult
from cms.grading.languagemanager import get_language
from cms.server import multi_contest
from cms.server.contest.submission import get_submission_count, \
    check_max_number, check_min_interval, InvalidArchive, \
    extract_files_from_tornado, InvalidFilesOrLanguage, \
    match_files_and_languages, fetch_file_digests_from_previous_submission, \
    store_local_copy, StorageFailed
from cmscommon.crypto import encrypt_number
from cmscommon.datetime import make_timestamp
from cmscommon.mimetypes import get_type_for_file_name

from ..phase_management import actual_phase_required

from .contest import ContestHandler, FileHandler


logger = logging.getLogger(__name__)


# Dummy function to mark translatable strings.
def N_(msgid):
    return msgid


class UserTestInterfaceHandler(ContestHandler):
    """Serve the interface to test programs.

    """
    @tornado.web.authenticated
    @actual_phase_required(0)
    @multi_contest
    def get(self):
        participation = self.current_user

        if not self.r_params["testing_enabled"]:
            raise tornado.web.HTTPError(404)

        user_tests = dict()
        user_tests_left = dict()
        default_task = None

        user_tests_left_contest = None
        if self.contest.max_user_test_number is not None:
            user_test_c = \
                get_submission_count(self.sql_session, participation,
                                     contest=self.contest, cls=UserTest)
            user_tests_left_contest = \
                self.contest.max_user_test_number - user_test_c

        for task in self.contest.tasks:
            if self.get_argument("task_name", None) == task.name:
                default_task = task
            user_tests[task.id] = self.sql_session.query(UserTest)\
                .filter(UserTest.participation == participation)\
                .filter(UserTest.task == task)\
                .all()
            user_tests_left_task = None
            if task.max_user_test_number is not None:
                user_tests_left_task = \
                    task.max_user_test_number - len(user_tests[task.id])

            user_tests_left[task.id] = user_tests_left_contest
            if user_tests_left_task is not None and \
                (user_tests_left_contest is None or
                 user_tests_left_contest > user_tests_left_task):
                user_tests_left[task.id] = user_tests_left_task

            # Make sure we do not show negative value if admins changed
            # the maximum
            if user_tests_left[task.id] is not None:
                user_tests_left[task.id] = max(0, user_tests_left[task.id])

        if default_task is None and len(self.contest.tasks) > 0:
            default_task = self.contest.tasks[0]

        self.render("test_interface.html", default_task=default_task,
                    user_tests=user_tests, user_tests_left=user_tests_left,
                    **self.r_params)


class UserTestHandler(ContestHandler):

    refresh_cookie = False

    # The following code has been taken from SubmitHandler and adapted
    # for UserTests.

    def _send_error(self, subject, text):
        """Shorthand for sending a notification and redirecting."""
        logger.warning("Sent error: `%s' - `%s'", subject, text)
        self.notify_error(subject, text)
        self.redirect(self.contest_url(*self.fallback_page,
                                       **self.fallback_args))

    @tornado.web.authenticated
    @actual_phase_required(0)
    @multi_contest
    def post(self, task_name):
        participation = self.current_user

        if not self.r_params["testing_enabled"]:
            raise tornado.web.HTTPError(404)

        task = self.get_task(task_name)
        if task is None:
            raise tornado.web.HTTPError(404)

        self.fallback_page = ["testing"]
        self.fallback_args = {"task_name": task.name}

        # Check that the task is testable
        task_type = task.active_dataset.task_type_object
        if not task_type.testable:
            logger.warning("User %s tried to make test on task %s.",
                           participation.user.username, task_name)
            raise tornado.web.HTTPError(404)

        # Alias for easy access
        contest = self.contest

        # Enforce maximum number of user_tests
        if not check_max_number(self.sql_session, contest.max_user_test_number,
                                participation, contest=contest, cls=UserTest):
            self._send_error(self._("Too many submissions!"),
                             self._("You have reached the maximum limit of "
                                    "at most %d tests among all tasks.")
                             % contest.max_user_test_number)
            return
        if not check_max_number(self.sql_session, task.max_user_test_number,
                                participation, task=task, cls=UserTest):
            self._send_error(self._("Too many submissions!"),
                             self._("You have reached the maximum limit of "
                                    "at most %d tests on this task.")
                             % task.max_user_test_number)
            return

        # Enforce minimum time between user_tests
        if not check_min_interval(
                self.sql_session, contest.min_user_test_interval,
                self.timestamp, participation, contest=contest, cls=UserTest):
            self._send_error(self._("Too many submissions!"),
                             self._("Among all tasks, you can test again "
                                    "after %d seconds from last test.")
                             % contest.min_user_test_interval.total_seconds())
            return
        if not check_min_interval(
                self.sql_session, task.min_user_test_interval, self.timestamp,
                participation, task=task, cls=UserTest):
            self._send_error(self._("Too many submissions!"),
                             self._("For this task, you can test again "
                                    "after %d seconds from last test.")
                             % task.min_user_test_interval.total_seconds())
            return

        # Required files from the user.
        required_codenames = set(task.submission_format +
                                 task_type.get_user_managers() +
                                 ["input"])

        try:
            given_files = extract_files_from_tornado(self.request.files)
        except InvalidArchive:
            self._send_error(
                self._("Invalid archive format!"),
                self._("The submitted archive could not be opened."))
            return

        try:
            files, language = match_files_and_languages(
                given_files, self.get_argument("language", None),
                required_codenames, contest.languages)
        except InvalidFilesOrLanguage:
            self._send_error(
                self._("Invalid test format!"),
                self._("Please select the correct files."))
            return

        file_digests = dict()
        missing_codenames = required_codenames.difference(iterkeys(files))
        if len(missing_codenames) > 0:
            if task.active_dataset.task_type_object.ALLOW_PARTIAL_SUBMISSION:
                file_digests = fetch_file_digests_from_previous_submission(
                    self.sql_session, participation, task, language,
                    missing_codenames, cls=UserTest)
            else:
                self._send_error(
                    self._("Invalid test format!"),
                    self._("Please select the correct files."))
                return

        # Check if submitted files are small enough.
        if any(len(content) > config.max_submission_length
               for codename, content in iteritems(files)
               if codename != "input"):
            self._send_error(
                self._("Test too big!"),
                self._("Each source file must be at most %d bytes long.") %
                config.max_submission_length)
            return
        if "input" in files and len(files["input"]) > config.max_input_length:
            self._send_error(
                self._("Input too big!"),
                self._("The input file must be at most %d bytes long.") %
                config.max_input_length)
            return

        # All checks done, submission accepted.

        # Attempt to store the submission locally to be able to
        # recover a failure.

        if config.tests_local_copy:
            try:
                store_local_copy(config.tests_local_copy_path, participation,
                                 task, self.timestamp, files)
            except StorageFailed:
                logger.error("Test local copy failed.", exc_info=True)

        # We now have to send all the files to the destination...
        try:
            for filename in files:
                digest = self.service.file_cacher.put_file_content(
                    files[filename],
                    "Test file %s sent by %s at %d." % (
                        filename, participation.user.username,
                        make_timestamp(self.timestamp)))
                file_digests[filename] = digest

        # In case of error, the server aborts the submission
        except Exception as error:
            logger.error("Storage failed! %s", error)
            self._send_error(
                self._("Test storage failed!"),
                self._("Please try again."))
            return

        # All the files are stored, ready to submit!
        logger.info("All files stored for test sent by %s",
                    participation.user.username)
        user_test = UserTest(self.timestamp,
                             language.name if language is not None else None,
                             file_digests["input"],
                             participation=participation,
                             task=task)

        for filename in task.submission_format:
            digest = file_digests[filename]
            self.sql_session.add(
                UserTestFile(filename, digest, user_test=user_test))
        for filename in task_type.get_user_managers():
            digest = file_digests[filename]
            if language is not None:
                extension = language.source_extension
                filename = filename.replace(".%l", extension)
            self.sql_session.add(
                UserTestManager(filename, digest, user_test=user_test))

        self.sql_session.add(user_test)
        self.sql_session.commit()
        self.service.evaluation_service.new_user_test(
            user_test_id=user_test.id)
        self.notify_success(
            N_("Test received"),
            N_("Your test has been received "
               "and is currently being executed."))

        # The argument (encripted user test id) is not used by CWS
        # (nor it discloses information to the user), but it is useful
        # for automatic testing to obtain the user test id).
        self.redirect(self.contest_url(
            *self.fallback_page,
            user_test_id=encrypt_number(user_test.id, config.secret_key),
            **self.fallback_args))


class UserTestStatusHandler(ContestHandler):

    refresh_cookie = False

    @tornado.web.authenticated
    @actual_phase_required(0)
    @multi_contest
    def get(self, task_name, user_test_num):
        if not self.r_params["testing_enabled"]:
            raise tornado.web.HTTPError(404)

        task = self.get_task(task_name)
        if task is None:
            raise tornado.web.HTTPError(404)

        user_test = self.get_user_test(task, user_test_num)
        if user_test is None:
            raise tornado.web.HTTPError(404)

        ur = user_test.get_result(task.active_dataset)
        data = dict()

        if ur is None:
            data["status"] = UserTestResult.COMPILING
        else:
            data["status"] = ur.get_status()

        if data["status"] == UserTestResult.COMPILING:
            data["status_text"] = self._("Compiling...")
        elif data["status"] == UserTestResult.COMPILATION_FAILED:
            data["status_text"] = "%s <a class=\"details\">%s</a>" % (
                self._("Compilation failed"), self._("details"))
        elif data["status"] == UserTestResult.EVALUATING:
            data["status_text"] = self._("Executing...")
        elif data["status"] == UserTestResult.EVALUATED:
            data["status_text"] = "%s <a class=\"details\">%s</a>" % (
                self._("Executed"), self._("details"))

            if ur.execution_time is not None:
                data["time"] = \
                    self.translation.format_duration(ur.execution_time)
            else:
                data["time"] = None

            if ur.execution_memory is not None:
                data["memory"] = \
                    self.translation.format_size(ur.execution_memory)
            else:
                data["memory"] = None

            data["output"] = ur.output is not None

        self.write(data)


class UserTestDetailsHandler(ContestHandler):

    refresh_cookie = False

    @tornado.web.authenticated
    @actual_phase_required(0)
    @multi_contest
    def get(self, task_name, user_test_num):
        if not self.r_params["testing_enabled"]:
            raise tornado.web.HTTPError(404)

        task = self.get_task(task_name)
        if task is None:
            raise tornado.web.HTTPError(404)

        user_test = self.get_user_test(task, user_test_num)
        if user_test is None:
            raise tornado.web.HTTPError(404)

        tr = user_test.get_result(task.active_dataset)

        self.render("user_test_details.html", task=task, tr=tr,
                    **self.r_params)


class UserTestIOHandler(FileHandler):
    """Send back a submission file.

    """
    @tornado.web.authenticated
    @actual_phase_required(0)
    @multi_contest
    def get(self, task_name, user_test_num, io):
        if not self.r_params["testing_enabled"]:
            raise tornado.web.HTTPError(404)

        task = self.get_task(task_name)
        if task is None:
            raise tornado.web.HTTPError(404)

        user_test = self.get_user_test(task, user_test_num)
        if user_test is None:
            raise tornado.web.HTTPError(404)

        if io == "input":
            digest = user_test.input
        else:  # io == "output"
            tr = user_test.get_result(task.active_dataset)
            digest = tr.output if tr is not None else None
        self.sql_session.close()

        if digest is None:
            raise tornado.web.HTTPError(404)

        mimetype = 'text/plain'

        self.fetch(digest, mimetype, io)


class UserTestFileHandler(FileHandler):
    """Send back a submission file.

    """
    @tornado.web.authenticated
    @actual_phase_required(0)
    @multi_contest
    def get(self, task_name, user_test_num, filename):
        if not self.r_params["testing_enabled"]:
            raise tornado.web.HTTPError(404)

        task = self.get_task(task_name)
        if task is None:
            raise tornado.web.HTTPError(404)

        user_test = self.get_user_test(task, user_test_num)
        if user_test is None:
            raise tornado.web.HTTPError(404)

        # filename is the name used by the browser, hence is something
        # like 'foo.c' (and the extension is CMS's preferred extension
        # for the language). To retrieve the right file, we need to
        # decode it to 'foo.%l'.
        stored_filename = filename
        if user_test.language is not None:
            extension = get_language(user_test.language).source_extension
            stored_filename = re.sub(r'%s$' % extension, '.%l', filename)

        if stored_filename in user_test.files:
            digest = user_test.files[stored_filename].digest
        elif stored_filename in user_test.managers:
            digest = user_test.managers[stored_filename].digest
        else:
            raise tornado.web.HTTPError(404)
        self.sql_session.close()

        mimetype = get_type_for_file_name(filename)
        if mimetype is None:
            mimetype = 'application/octet-stream'

        self.fetch(digest, mimetype, filename)
