#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2015 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2015-2016 William Di Luigi <williamdiluigi@gmail.com>
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

"""Non-categorized handlers for CWS.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa
from six import iterkeys, itervalues

import ipaddress
import json
import logging

import tornado.web

from cms import config
from cms.db import PrintJob
from cms.grading import COMPILATION_MESSAGES, EVALUATION_MESSAGES
from cms.server import multi_contest
from cms.server.contest.authentication import validate_login
from cms.server.contest.communication import get_communications
from cmscommon.datetime import make_datetime, make_timestamp

from ..phase_management import actual_phase_required

from .contest import ContestHandler, NOTIFICATION_ERROR, NOTIFICATION_SUCCESS


logger = logging.getLogger(__name__)


class MainHandler(ContestHandler):
    """Home page handler.

    """
    @multi_contest
    def get(self):
        self.render("overview.html", **self.r_params)


class LoginHandler(ContestHandler):
    """Login handler.

    """
    @multi_contest
    def post(self):
        error_args = {"login_error": "true"}
        next_page = self.get_argument("next", None)
        if next_page is not None:
            error_args["next"] = next_page
            if next_page != "/":
                next_page = self.url(*next_page.strip("/").split("/"))
            else:
                next_page = self.url()
        else:
            next_page = self.contest_url()
        error_page = self.contest_url(**error_args)

        username = self.get_argument("username", "")
        password = self.get_argument("password", "")

        try:
            # In py2 Tornado gives us the IP address as a native binary
            # string, whereas ipaddress wants text (unicode) strings.
            ip_address = ipaddress.ip_address(str(self.request.remote_ip))
        except ValueError:
            logger.warning("Invalid IP address provided by Tornado: %s",
                           self.request.remote_ip)
            return None

        participation, cookie = validate_login(
            self.sql_session, self.contest, self.timestamp, username, password,
            ip_address)

        cookie_name = self.contest.name + "_login"
        if cookie is None:
            self.clear_cookie(cookie_name)
        else:
            self.set_secure_cookie(cookie_name, cookie, expires_days=None)

        if participation is None:
            self.redirect(error_page)
        else:
            self.redirect(next_page)


class StartHandler(ContestHandler):
    """Start handler.

    Used by a user who wants to start their per_user_time.

    """
    @tornado.web.authenticated
    @actual_phase_required(-1)
    @multi_contest
    def post(self):
        participation = self.current_user

        logger.info("Starting now for user %s", participation.user.username)
        participation.starting_time = self.timestamp
        self.sql_session.commit()

        self.redirect(self.contest_url())


class LogoutHandler(ContestHandler):
    """Logout handler.

    """
    @multi_contest
    def post(self):
        self.clear_cookie(self.contest.name + "_login")
        self.redirect(self.contest_url())


class NotificationsHandler(ContestHandler):
    """Displays notifications.

    """

    refresh_cookie = False

    @tornado.web.authenticated
    @multi_contest
    def get(self):
        participation = self.current_user

        last_notification = self.get_argument("last_notification", None)
        if last_notification is not None:
            last_notification = make_datetime(float(last_notification))

        res = get_communications(self.sql_session, participation,
                                 self.timestamp, after=last_notification)

        # Simple notifications
        notifications = self.service.notifications
        username = participation.user.username
        if username in notifications:
            for notification in notifications[username]:
                res.append({"type": "notification",
                            "timestamp": make_timestamp(notification[0]),
                            "subject": notification[1],
                            "text": notification[2],
                            "level": notification[3]})
            del notifications[username]

        self.write(json.dumps(res))


class PrintingHandler(ContestHandler):
    """Serve the interface to print and handle submitted print jobs.

    """
    @tornado.web.authenticated
    @actual_phase_required(0)
    @multi_contest
    def get(self):
        participation = self.current_user

        if not self.r_params["printing_enabled"]:
            raise tornado.web.HTTPError(404)

        printjobs = self.sql_session.query(PrintJob)\
            .filter(PrintJob.participation == participation)\
            .all()

        remaining_jobs = max(0, config.max_jobs_per_user - len(printjobs))

        self.render("printing.html",
                    printjobs=printjobs,
                    remaining_jobs=remaining_jobs,
                    max_pages=config.max_pages_per_job,
                    pdf_printing_allowed=config.pdf_printing_allowed,
                    **self.r_params)

    @tornado.web.authenticated
    @actual_phase_required(0)
    @multi_contest
    def post(self):
        participation = self.current_user

        if not self.r_params["printing_enabled"]:
            raise tornado.web.HTTPError(404)

        fallback_page = self.contest_url("printing")

        printjobs = self.sql_session.query(PrintJob)\
            .filter(PrintJob.participation == participation)\
            .all()
        old_count = len(printjobs)
        if config.max_jobs_per_user <= old_count:
            self.service.add_notification(
                participation.user.username,
                self.timestamp,
                self._("Too many print jobs!"),
                self._("You have reached the maximum limit of "
                       "at most %d print jobs.") % config.max_jobs_per_user,
                NOTIFICATION_ERROR)
            self.redirect(fallback_page)
            return

        # Ensure that the user did not submit multiple files with the
        # same name and that the user sent exactly one file.
        if any(len(filename) != 1
               for filename in itervalues(self.request.files)) \
                or set(iterkeys(self.request.files)) != set(["file"]):
            self.service.add_notification(
                participation.user.username,
                self.timestamp,
                self._("Invalid format!"),
                self._("Please select the correct files."),
                NOTIFICATION_ERROR)
            self.redirect(fallback_page)
            return

        filename = self.request.files["file"][0]["filename"]
        data = self.request.files["file"][0]["body"]

        # Check if submitted file is small enough.
        if len(data) > config.max_print_length:
            self.service.add_notification(
                participation.user.username,
                self.timestamp,
                self._("File too big!"),
                self._("Each file must be at most %d bytes long.") %
                config.max_print_length,
                NOTIFICATION_ERROR)
            self.redirect(fallback_page)
            return

        # We now have to send the file to the destination...
        try:
            digest = self.service.file_cacher.put_file_content(
                data,
                "Print job sent by %s at %d." % (
                    participation.user.username,
                    make_timestamp(self.timestamp)))

        # In case of error, the server aborts
        except Exception as error:
            logger.error("Storage failed! %s", error)
            self.service.add_notification(
                participation.user.username,
                self.timestamp,
                self._("Print job storage failed!"),
                self._("Please try again."),
                NOTIFICATION_ERROR)
            self.redirect(fallback_page)
            return

        # The file is stored, ready to submit!
        logger.info("File stored for print job sent by %s",
                    participation.user.username)

        printjob = PrintJob(timestamp=self.timestamp,
                            participation=participation,
                            filename=filename,
                            digest=digest)

        self.sql_session.add(printjob)
        self.sql_session.commit()
        self.service.printing_service.new_printjob(
            printjob_id=printjob.id)
        self.service.add_notification(
            participation.user.username,
            self.timestamp,
            self._("Print job received"),
            self._("Your print job has been received."),
            NOTIFICATION_SUCCESS)
        self.redirect(fallback_page)


class DocumentationHandler(ContestHandler):
    """Displays the instruction (compilation lines, documentation,
    ...) of the contest.

    """
    @tornado.web.authenticated
    @multi_contest
    def get(self):
        self.render("documentation.html",
                    COMPILATION_MESSAGES=COMPILATION_MESSAGES,
                    EVALUATION_MESSAGES=EVALUATION_MESSAGES,
                    **self.r_params)
