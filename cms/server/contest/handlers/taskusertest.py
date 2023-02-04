#!/usr/bin/env python3

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

import logging
import re

try:
    import tornado4.web as tornado_web
except ImportError:
    import tornado.web as tornado_web

from cms import config
from cms.db import UserTest, UserTestResult
from cms.grading.languagemanager import get_language
from cms.server import multi_contest
from cms.server.contest.submission import get_submission_count, \
    TestingNotAllowed, UnacceptableUserTest, accept_user_test
from cmscommon.crypto import encrypt_number
from cmscommon.mimetypes import get_type_for_file_name
from .contest import ContestHandler, FileHandler
from ..phase_management import actual_phase_required


logger = logging.getLogger(__name__)


# Dummy function to mark translatable strings.
def N_(msgid):
    return msgid


class UserTestInterfaceHandler(ContestHandler):
    """Serve the interface to test programs.

    """
    @tornado_web.authenticated
    @actual_phase_required(0)
    @multi_contest
    def get(self):
        participation = self.current_user

        if not self.r_params["testing_enabled"]:
            raise tornado_web.HTTPError(404)

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

    @tornado_web.authenticated
    @actual_phase_required(0)
    @multi_contest
    def post(self, task_name):
        if not self.r_params["testing_enabled"]:
            raise tornado_web.HTTPError(404)

        task = self.get_task(task_name)
        if task is None:
            raise tornado_web.HTTPError(404)

        query_args = dict()

        try:
            user_test = accept_user_test(
                self.sql_session, self.service.file_cacher, self.current_user,
                task, self.timestamp, self.request.files,
                self.get_argument("language", None))
            self.sql_session.commit()
        except TestingNotAllowed:
            logger.warning("User %s tried to make test on task %s.",
                           self.current_user.user.username, task_name)
            raise tornado_web.HTTPError(404)
        except UnacceptableUserTest as e:
            logger.info("Sent error: `%s' - `%s'", e.subject, e.formatted_text)
            self.notify_error(e.subject, e.text, e.text_params)
        else:
            self.service.evaluation_service.new_user_test(
                user_test_id=user_test.id)
            self.notify_success(N_("Test received"),
                                N_("Your test has been received "
                                   "and is currently being executed."))
            # The argument (encrypted user test id) is not used by CWS
            # (nor it discloses information to the user), but it is
            # useful for automatic testing to obtain the user test id).
            query_args["user_test_id"] = \
                encrypt_number(user_test.id, config.secret_key)

        self.redirect(self.contest_url("testing", task_name=task.name,
                                       **query_args))


class UserTestStatusHandler(ContestHandler):

    refresh_cookie = False

    @tornado_web.authenticated
    @actual_phase_required(0)
    @multi_contest
    def get(self, task_name, user_test_num):
        if not self.r_params["testing_enabled"]:
            raise tornado_web.HTTPError(404)

        task = self.get_task(task_name)
        if task is None:
            raise tornado_web.HTTPError(404)

        user_test = self.get_user_test(task, user_test_num)
        if user_test is None:
            raise tornado_web.HTTPError(404)

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
                data["execution_time"] = \
                    self.translation.format_duration(ur.execution_time)
            else:
                data["execution_time"] = None

            if ur.execution_memory is not None:
                data["memory"] = \
                    self.translation.format_size(ur.execution_memory)
            else:
                data["memory"] = None

            data["output"] = ur.output is not None

        self.write(data)


class UserTestDetailsHandler(ContestHandler):

    refresh_cookie = False

    @tornado_web.authenticated
    @actual_phase_required(0)
    @multi_contest
    def get(self, task_name, user_test_num):
        if not self.r_params["testing_enabled"]:
            raise tornado_web.HTTPError(404)

        task = self.get_task(task_name)
        if task is None:
            raise tornado_web.HTTPError(404)

        user_test = self.get_user_test(task, user_test_num)
        if user_test is None:
            raise tornado_web.HTTPError(404)

        tr = user_test.get_result(task.active_dataset)

        self.render("user_test_details.html", task=task, tr=tr,
                    **self.r_params)


class UserTestIOHandler(FileHandler):
    """Send back a submission file.

    """
    @tornado_web.authenticated
    @actual_phase_required(0)
    @multi_contest
    def get(self, task_name, user_test_num, io):
        if not self.r_params["testing_enabled"]:
            raise tornado_web.HTTPError(404)

        task = self.get_task(task_name)
        if task is None:
            raise tornado_web.HTTPError(404)

        user_test = self.get_user_test(task, user_test_num)
        if user_test is None:
            raise tornado_web.HTTPError(404)

        if io == "input":
            digest = user_test.input
        else:  # io == "output"
            tr = user_test.get_result(task.active_dataset)
            digest = tr.output if tr is not None else None
        self.sql_session.close()

        if digest is None:
            raise tornado_web.HTTPError(404)

        mimetype = 'text/plain'

        self.fetch(digest, mimetype, io)


class UserTestFileHandler(FileHandler):
    """Send back a submission file.

    """
    @tornado_web.authenticated
    @actual_phase_required(0)
    @multi_contest
    def get(self, task_name, user_test_num, filename):
        if not self.r_params["testing_enabled"]:
            raise tornado_web.HTTPError(404)

        task = self.get_task(task_name)
        if task is None:
            raise tornado_web.HTTPError(404)

        user_test = self.get_user_test(task, user_test_num)
        if user_test is None:
            raise tornado_web.HTTPError(404)

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
        elif filename in user_test.managers:
            # Graders are not stored with the .%l suffix
            # Instead, the original name is used
            digest = user_test.managers[filename].digest
        else:
            raise tornado_web.HTTPError(404)
        self.sql_session.close()

        mimetype = get_type_for_file_name(filename)
        if mimetype is None:
            mimetype = 'application/octet-stream'

        self.fetch(digest, mimetype, filename)
