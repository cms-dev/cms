#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2025 Luca Versari <veluca93@gmail.com>
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

"""API handlers for CMS.

"""

import ipaddress
import logging

try:
    import tornado4.web as tornado_web
except ImportError:
    import tornado.web as tornado_web

from cms.db.submission import Submission
from cms.server import multi_contest
from cms.server.contest.authentication import validate_login
from cms.server.contest.submission import \
    UnacceptableSubmission, accept_submission
from .contest import ContestHandler
from ..phase_management import actual_phase_required

logger = logging.getLogger(__name__)


class ApiLoginHandler(ContestHandler):
    """Login handler.

    """
    @multi_contest
    def post(self):
        username = self.get_argument("username", "")
        password = self.get_argument("password", "")

        try:
            ip_address = ipaddress.ip_address(self.request.remote_ip)
        except ValueError:
            logger.warning("Invalid IP address provided by Tornado: %s",
                           self.request.remote_ip)
            return None

        participation, login_data = validate_login(
            self.sql_session, self.contest, self.timestamp, username, password,
            ip_address)

        if participation is None:
            self.json({"error": "Login failed"}, 403)
        elif login_data is not None:
            cookie_name = self.contest.name + "_login"
            self.json({"login_data": self.create_signed_value(
                cookie_name, login_data).decode()})
        else:
            self.json({})

    def check_xsrf_cookie(self):
        pass


class ApiTaskListHandler(ContestHandler):
    """Handler to list all tasks and their statements.

    """
    @tornado_web.authenticated
    @actual_phase_required(0, 3)
    @multi_contest
    def get(self):
        contest = self.contest
        tasks = []
        for task in contest.tasks:
            name = task.name
            statements = [s for s in task.statements]
            sub_format = task.submission_format
            tasks.append({"name": name,
                          "statements": statements,
                          "submission_format": sub_format})
        self.json({"tasks": tasks})


class ApiSubmitHandler(ContestHandler):
    """Handles the received submissions.

    """
    @tornado_web.authenticated
    @actual_phase_required(0, 3)
    @multi_contest
    def post(self, task_name: str):
        task = self.get_task(task_name)
        if task is None:
            self.json({"error": "Not found"}, 404)
            return

        # Only set the official bit when the user can compete and we are not in
        # analysis mode.
        official = self.r_params["actual_phase"] == 0

        try:
            submission = accept_submission(
                self.sql_session, self.service.file_cacher, self.current_user,
                task, self.timestamp, self.request.files,
                self.get_argument("language", None), official)
            self.sql_session.commit()
        except UnacceptableSubmission as e:
            logger.info("API submission rejected: `%s' - `%s'",
                        e.subject, e.formatted_text)
            self.json({"error": e.subject, "details": e.formatted_text}, 400)
        else:
            logger.info(
                f'API submission accepted: Submission ID {submission.id}')
            self.service.evaluation_service.new_submission(
                submission_id=submission.id)
            self.json({'id': str(submission.opaque_id)})


class ApiSubmissionListHandler(ContestHandler):
    """Retrieves the list of submissions on a task.

    """
    @tornado_web.authenticated
    @actual_phase_required(0, 3)
    @multi_contest
    def get(self, task_name: str):
        task = self.get_task(task_name)
        if task is None:
            self.json({"error": "Not found"}, 404)
            return
        submissions: list[Submission] = (
            self.sql_session.query(Submission)
            .filter(Submission.participation == self.current_user)
            .filter(Submission.task == task)
            .all()
        )
        self.json({'list': [{"id": str(s.opaque_id)} for s in submissions]})
