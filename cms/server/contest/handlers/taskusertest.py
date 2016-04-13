#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2015 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2015 William Di Luigi <williamdiluigi@gmail.com>
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
from __future__ import print_function
from __future__ import unicode_literals

import io
import logging
import os
import pickle

from urllib import quote

import tornado.web

from sqlalchemy import func

from cms import config, filename_to_language
from cms.db import Task, UserTest, UserTestFile, UserTestManager
from cms.grading.tasktypes import get_task_type
from cms.server import actual_phase_required, format_size
from cmscommon.archive import Archive
from cmscommon.datetime import make_timestamp
from cmscommon.mimetypes import get_type_for_file_name

from .base import BaseHandler, FileHandler, \
    NOTIFICATION_ERROR, NOTIFICATION_SUCCESS


logger = logging.getLogger(__name__)


class UserTestInterfaceHandler(BaseHandler):
    """Serve the interface to test programs.

    """
    @tornado.web.authenticated
    @actual_phase_required(0, 1, 2)
    def get(self):
        participation = self.current_user

        if not self.r_params["testing_enabled"]:
            self.redirect("/")
            return

        user_tests = dict()
        user_tests_left = dict()
        default_task = None

        user_tests_left_contest = None
        if self.contest.max_user_test_number is not None:
            user_test_c = self.sql_session.query(func.count(UserTest.id))\
                .join(UserTest.task)\
                .filter(Task.contest == self.contest)\
                .filter(UserTest.participation == participation)\
                .scalar()
            user_tests_left_contest = \
                self.contest.max_user_test_number - user_test_c

        for task in self.contest.tasks:
            if self.request.query == task.name:
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


class UserTestHandler(BaseHandler):

    refresh_cookie = False

    # The following code has been taken from SubmitHandler and adapted
    # for UserTests.

    @tornado.web.authenticated
    @actual_phase_required(0)
    def post(self, task_name):
        participation = self.current_user

        if not self.r_params["testing_enabled"]:
            self.redirect("/")
            return

        try:
            task = self.contest.get_task(task_name)
        except KeyError:
            raise tornado.web.HTTPError(404)

        # Check that the task is testable
        task_type = get_task_type(dataset=task.active_dataset)
        if not task_type.testable:
            logger.warning("User %s tried to make test on task %s.",
                           participation.user.username, task_name)
            raise tornado.web.HTTPError(404)

        # Alias for easy access
        contest = self.contest

        # Enforce maximum number of user_tests
        try:
            if contest.max_user_test_number is not None:
                user_test_c = self.sql_session.query(func.count(UserTest.id))\
                    .join(UserTest.task)\
                    .filter(Task.contest == contest)\
                    .filter(UserTest.participation == participation)\
                    .scalar()
                if user_test_c >= contest.max_user_test_number:
                    raise ValueError(
                        self._("You have reached the maximum limit of "
                               "at most %d tests among all tasks.") %
                        contest.max_user_test_number)
            if task.max_user_test_number is not None:
                user_test_t = self.sql_session.query(func.count(UserTest.id))\
                    .filter(UserTest.task == task)\
                    .filter(UserTest.participation == participation)\
                    .scalar()
                if user_test_t >= task.max_user_test_number:
                    raise ValueError(
                        self._("You have reached the maximum limit of "
                               "at most %d tests on this task.") %
                        task.max_user_test_number)
        except ValueError as error:
            self.application.service.add_notification(
                participation.user.username,
                self.timestamp,
                self._("Too many tests!"),
                error.message,
                NOTIFICATION_ERROR)
            self.redirect("/testing?%s" % quote(task.name, safe=''))
            return

        # Enforce minimum time between user_tests
        try:
            if contest.min_user_test_interval is not None:
                last_user_test_c = self.sql_session.query(UserTest)\
                    .join(UserTest.task)\
                    .filter(Task.contest == contest)\
                    .filter(UserTest.participation == participation)\
                    .order_by(UserTest.timestamp.desc())\
                    .first()
                if last_user_test_c is not None and \
                        self.timestamp - last_user_test_c.timestamp < \
                        contest.min_user_test_interval:
                    raise ValueError(
                        self._("Among all tasks, you can test again "
                               "after %d seconds from last test.") %
                        contest.min_user_test_interval.total_seconds())
            # We get the last user_test even if we may not need it
            # for min_user_test_interval because we may need it later,
            # in case this is a ALLOW_PARTIAL_SUBMISSION task.
            last_user_test_t = self.sql_session.query(UserTest)\
                .filter(UserTest.participation == participation)\
                .filter(UserTest.task == task)\
                .order_by(UserTest.timestamp.desc())\
                .first()
            if task.min_user_test_interval is not None:
                if last_user_test_t is not None and \
                        self.timestamp - last_user_test_t.timestamp < \
                        task.min_user_test_interval:
                    raise ValueError(
                        self._("For this task, you can test again "
                               "after %d seconds from last test.") %
                        task.min_user_test_interval.total_seconds())
        except ValueError as error:
            self.application.service.add_notification(
                participation.user.username,
                self.timestamp,
                self._("Tests too frequent!"),
                error.message,
                NOTIFICATION_ERROR)
            self.redirect("/testing?%s" % quote(task.name, safe=''))
            return

        # Ensure that the user did not submit multiple files with the
        # same name.
        if any(len(filename) != 1 for filename in self.request.files.values()):
            self.application.service.add_notification(
                participation.user.username,
                self.timestamp,
                self._("Invalid test format!"),
                self._("Please select the correct files."),
                NOTIFICATION_ERROR)
            self.redirect("/testing?%s" % quote(task.name, safe=''))
            return

        # If the user submitted an archive, extract it and use content
        # as request.files.
        if len(self.request.files) == 1 and \
                self.request.files.keys()[0] == "submission":
            archive_data = self.request.files["submission"][0]
            del self.request.files["submission"]

            # Create the archive.
            archive = Archive.from_raw_data(archive_data["body"])

            if archive is None:
                self.application.service.add_notification(
                    participation.user.username,
                    self.timestamp,
                    self._("Invalid archive format!"),
                    self._("The submitted archive could not be opened."),
                    NOTIFICATION_ERROR)
                self.redirect("/testing?%s" % quote(task.name, safe=''))
                return

            # Extract the archive.
            unpacked_dir = archive.unpack()
            for name in archive.namelist():
                filename = os.path.basename(name)
                body = open(os.path.join(unpacked_dir, filename), "r").read()
                self.request.files[filename] = [{
                    'filename': filename,
                    'body': body
                }]

            archive.cleanup()

        # This ensure that the user sent one file for every name in
        # submission format and no more. Less is acceptable if task
        # type says so.
        required = set([sfe.filename for sfe in task.submission_format] +
                       task_type.get_user_managers(task.submission_format) +
                       ["input"])
        provided = set(self.request.files.keys())
        if not (required == provided or (task_type.ALLOW_PARTIAL_SUBMISSION
                                         and required.issuperset(provided))):
            self.application.service.add_notification(
                participation.user.username,
                self.timestamp,
                self._("Invalid test format!"),
                self._("Please select the correct files."),
                NOTIFICATION_ERROR)
            self.redirect("/testing?%s" % quote(task.name, safe=''))
            return

        # Add submitted files. After this, files is a dictionary indexed
        # by *our* filenames (something like "output01.txt" or
        # "taskname.%l", and whose value is a couple
        # (user_assigned_filename, content).
        files = {}
        for uploaded, data in self.request.files.iteritems():
            files[uploaded] = (data[0]["filename"], data[0]["body"])

        # If we allow partial submissions, implicitly we recover the
        # non-submitted files from the previous submission. And put them
        # in file_digests (i.e. like they have already been sent to FS).
        submission_lang = None
        file_digests = {}
        if task_type.ALLOW_PARTIAL_SUBMISSION and last_user_test_t is not None:
            for filename in required.difference(provided):
                if filename in last_user_test_t.files:
                    # If we retrieve a language-dependent file from
                    # last submission, we take not that language must
                    # be the same.
                    if "%l" in filename:
                        submission_lang = last_user_test_t.language
                    file_digests[filename] = \
                        last_user_test_t.files[filename].digest

        # We need to ensure that everytime we have a .%l in our
        # filenames, the user has one amongst ".cpp", ".c", or ".pas,
        # and that all these are the same (i.e., no mixed-language
        # submissions).

        error = None
        for our_filename in files:
            user_filename = files[our_filename][0]
            if our_filename.find(".%l") != -1:
                lang = filename_to_language(user_filename)
                if lang is None:
                    error = self._("Cannot recognize test's language.")
                    break
                elif submission_lang is not None and \
                        submission_lang != lang:
                    error = self._("All sources must be in the same language.")
                    break
                else:
                    submission_lang = lang
        if error is not None:
            self.application.service.add_notification(
                participation.user.username,
                self.timestamp,
                self._("Invalid test!"),
                error,
                NOTIFICATION_ERROR)
            self.redirect("/testing?%s" % quote(task.name, safe=''))
            return

        # Check if submitted files are small enough.
        if any([len(f[1]) > config.max_submission_length
                for n, f in files.items() if n != "input"]):
            self.application.service.add_notification(
                participation.user.username,
                self.timestamp,
                self._("Test too big!"),
                self._("Each source file must be at most %d bytes long.") %
                config.max_submission_length,
                NOTIFICATION_ERROR)
            self.redirect("/testing?%s" % quote(task.name, safe=''))
            return
        if len(files["input"][1]) > config.max_input_length:
            self.application.service.add_notification(
                participation.user.username,
                self.timestamp,
                self._("Input too big!"),
                self._("The input file must be at most %d bytes long.") %
                config.max_input_length,
                NOTIFICATION_ERROR)
            self.redirect("/testing?%s" % quote(task.name, safe=''))
            return

        # All checks done, submission accepted.

        # Attempt to store the submission locally to be able to
        # recover a failure.
        if config.tests_local_copy:
            try:
                path = os.path.join(
                    config.tests_local_copy_path.replace("%s",
                                                         config.data_dir),
                    participation.user.username)
                if not os.path.exists(path):
                    os.makedirs(path)
                # Pickle in ASCII format produces str, not unicode,
                # therefore we open the file in binary mode.
                with io.open(
                        os.path.join(path,
                                     "%d" % make_timestamp(self.timestamp)),
                        "wb") as file_:
                    pickle.dump((self.contest.id,
                                 participation.user.id,
                                 task.id,
                                 files), file_)
            except Exception as error:
                logger.error("Test local copy failed.", exc_info=True)

        # We now have to send all the files to the destination...
        try:
            for filename in files:
                digest = self.application.service.file_cacher.put_file_content(
                    files[filename][1],
                    "Test file %s sent by %s at %d." % (
                        filename, participation.user.username,
                        make_timestamp(self.timestamp)))
                file_digests[filename] = digest

        # In case of error, the server aborts the submission
        except Exception as error:
            logger.error("Storage failed! %s", error)
            self.application.service.add_notification(
                participation.user.username,
                self.timestamp,
                self._("Test storage failed!"),
                self._("Please try again."),
                NOTIFICATION_ERROR)
            self.redirect("/testing?%s" % quote(task.name, safe=''))
            return

        # All the files are stored, ready to submit!
        logger.info("All files stored for test sent by %s",
                    participation.user.username)
        user_test = UserTest(self.timestamp,
                             submission_lang,
                             file_digests["input"],
                             participation=participation,
                             task=task)

        for filename in [sfe.filename for sfe in task.submission_format]:
            digest = file_digests[filename]
            self.sql_session.add(
                UserTestFile(filename, digest, user_test=user_test))
        for filename in task_type.get_user_managers(task.submission_format):
            digest = file_digests[filename]
            if submission_lang is not None:
                filename = filename.replace("%l", submission_lang)
            self.sql_session.add(
                UserTestManager(filename, digest, user_test=user_test))

        self.sql_session.add(user_test)
        self.sql_session.commit()
        self.application.service.evaluation_service.new_user_test(
            user_test_id=user_test.id)
        self.application.service.add_notification(
            participation.user.username,
            self.timestamp,
            self._("Test received"),
            self._("Your test has been received "
                   "and is currently being executed."),
            NOTIFICATION_SUCCESS)
        self.redirect("/testing?%s" % quote(task.name, safe=''))


class UserTestStatusHandler(BaseHandler):

    refresh_cookie = False

    @tornado.web.authenticated
    @actual_phase_required(0, 1, 2)
    def get(self, task_name, user_test_num):
        participation = self.current_user

        if not self.r_params["testing_enabled"]:
            raise tornado.web.HTTPError(404)

        try:
            task = self.contest.get_task(task_name)
        except KeyError:
            raise tornado.web.HTTPError(404)

        user_test = self.sql_session.query(UserTest)\
            .filter(UserTest.participation == participation)\
            .filter(UserTest.task == task)\
            .order_by(UserTest.timestamp)\
            .offset(int(user_test_num) - 1)\
            .first()
        if user_test is None:
            raise tornado.web.HTTPError(404)

        ur = user_test.get_result(task.active_dataset)

        # TODO: use some kind of constants to refer to the status.
        data = dict()
        if ur is None or not ur.compiled():
            data["status"] = 1
            data["status_text"] = self._("Compiling...")
        elif ur.compilation_failed():
            data["status"] = 2
            data["status_text"] = "%s <a class=\"details\">%s</a>" % (
                self._("Compilation failed"), self._("details"))
        elif not ur.evaluated():
            data["status"] = 3
            data["status_text"] = self._("Executing...")
        else:
            data["status"] = 4
            data["status_text"] = "%s <a class=\"details\">%s</a>" % (
                self._("Executed"), self._("details"))
            if ur.execution_time is not None:
                data["time"] = self._("%(seconds)0.3f s") % {
                    'seconds': ur.execution_time}
            else:
                data["time"] = None
            if ur.execution_memory is not None:
                data["memory"] = format_size(ur.execution_memory)
            else:
                data["memory"] = None
            data["output"] = ur.output is not None

        self.write(data)


class UserTestDetailsHandler(BaseHandler):

    refresh_cookie = False

    @tornado.web.authenticated
    @actual_phase_required(0, 1, 2)
    def get(self, task_name, user_test_num):
        participation = self.current_user

        if not self.r_params["testing_enabled"]:
            raise tornado.web.HTTPError(404)

        try:
            task = self.contest.get_task(task_name)
        except KeyError:
            raise tornado.web.HTTPError(404)

        user_test = self.sql_session.query(UserTest)\
            .filter(UserTest.participation == participation)\
            .filter(UserTest.task == task)\
            .order_by(UserTest.timestamp)\
            .offset(int(user_test_num) - 1)\
            .first()
        if user_test is None:
            raise tornado.web.HTTPError(404)

        tr = user_test.get_result(task.active_dataset)

        self.render("user_test_details.html", task=task, tr=tr)


class UserTestIOHandler(FileHandler):
    """Send back a submission file.

    """
    @tornado.web.authenticated
    @actual_phase_required(0, 1, 2)
    def get(self, task_name, user_test_num, io):
        participation = self.current_user

        if not self.r_params["testing_enabled"]:
            raise tornado.web.HTTPError(404)

        try:
            task = self.contest.get_task(task_name)
        except KeyError:
            raise tornado.web.HTTPError(404)

        user_test = self.sql_session.query(UserTest)\
            .filter(UserTest.participation == participation)\
            .filter(UserTest.task == task)\
            .order_by(UserTest.timestamp)\
            .offset(int(user_test_num) - 1)\
            .first()
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
    @actual_phase_required(0, 1, 2)
    def get(self, task_name, user_test_num, filename):
        participation = self.current_user

        if not self.r_params["testing_enabled"]:
            raise tornado.web.HTTPError(404)

        try:
            task = self.contest.get_task(task_name)
        except KeyError:
            raise tornado.web.HTTPError(404)

        user_test = self.sql_session.query(UserTest)\
            .filter(UserTest.participation == participation)\
            .filter(UserTest.task == task)\
            .order_by(UserTest.timestamp)\
            .offset(int(user_test_num) - 1)\
            .first()
        if user_test is None:
            raise tornado.web.HTTPError(404)

        # filename follows our convention (e.g. 'foo.%l'), real_filename
        # follows the one we present to the user (e.g. 'foo.c').
        real_filename = filename
        if user_test.language is not None:
            real_filename = filename.replace("%l", user_test.language)

        if filename in user_test.files:
            digest = user_test.files[filename].digest
        elif filename in user_test.managers:
            digest = user_test.managers[filename].digest
        else:
            raise tornado.web.HTTPError(404)
        self.sql_session.close()

        mimetype = get_type_for_file_name(real_filename)
        if mimetype is None:
            mimetype = 'application/octet-stream'

        self.fetch(digest, mimetype, real_filename)
