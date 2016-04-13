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

"""Non-categorized handlers for CWS.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import json
import logging
import pickle

import tornado.web

from cms import config
from cms.db import Participation, PrintJob, User
from cms.server import actual_phase_required, filter_ascii
from cmscommon.datetime import make_datetime, make_timestamp

from .base import BaseHandler, check_ip, \
    NOTIFICATION_ERROR, NOTIFICATION_SUCCESS


logger = logging.getLogger(__name__)


class MainHandler(BaseHandler):
    """Home page handler.

    """
    def get(self):
        self.render("overview.html", **self.r_params)


class LoginHandler(BaseHandler):
    """Login handler.

    """
    def post(self):
        username = self.get_argument("username", "")
        password = self.get_argument("password", "")
        next_page = self.get_argument("next", "/")
        user = self.sql_session.query(User)\
            .filter(User.username == username)\
            .first()
        participation = self.sql_session.query(Participation)\
            .filter(Participation.contest == self.contest)\
            .filter(Participation.user == user)\
            .first()

        if user is None:
            # TODO: notify the user that they don't exist
            self.redirect("/?login_error=true")
            return

        if participation is None:
            # TODO: notify the user that they're uninvited
            self.redirect("/?login_error=true")
            return

        # If a contest-specific password is defined, use that. If it's
        # not, use the user's main password.
        if participation.password is None:
            correct_password = user.password
        else:
            correct_password = participation.password

        filtered_user = filter_ascii(username)
        filtered_pass = filter_ascii(password)

        if password != correct_password:
            logger.info("Login error: user=%s pass=%s remote_ip=%s." %
                        (filtered_user, filtered_pass, self.request.remote_ip))
            self.redirect("/?login_error=true")
            return

        if self.contest.ip_restriction and participation.ip is not None \
                and not check_ip(self.request.remote_ip, participation.ip):
            logger.info("Unexpected IP: user=%s pass=%s remote_ip=%s.",
                        filtered_user, filtered_pass, self.request.remote_ip)
            self.redirect("/?login_error=true")
            return

        if participation.hidden and self.contest.block_hidden_participations:
            logger.info("Hidden user login attempt: "
                        "user=%s pass=%s remote_ip=%s.",
                        filtered_user, filtered_pass, self.request.remote_ip)
            self.redirect("/?login_error=true")
            return

        logger.info("User logged in: user=%s remote_ip=%s.",
                    filtered_user, self.request.remote_ip)
        self.set_secure_cookie("login",
                               pickle.dumps((user.username,
                                             correct_password,
                                             make_timestamp())),
                               expires_days=None)
        self.redirect(next_page)


class StartHandler(BaseHandler):
    """Start handler.

    Used by a user who wants to start his per_user_time.

    """
    @tornado.web.authenticated
    @actual_phase_required(-1)
    def post(self):
        participation = self.current_user

        logger.info("Starting now for user %s", participation.user.username)
        participation.starting_time = self.timestamp
        self.sql_session.commit()

        self.redirect("/")


class LogoutHandler(BaseHandler):
    """Logout handler.

    """
    def get(self):
        self.clear_cookie("login")
        self.redirect("/")


class NotificationsHandler(BaseHandler):
    """Displays notifications.

    """

    refresh_cookie = False

    @tornado.web.authenticated
    def get(self):
        if not self.current_user:
            raise tornado.web.HTTPError(403)

        participation = self.current_user

        res = []
        last_notification = make_datetime(
            float(self.get_argument("last_notification", "0")))

        # Announcements
        for announcement in self.contest.announcements:
            if announcement.timestamp > last_notification \
                    and announcement.timestamp < self.timestamp:
                res.append({"type": "announcement",
                            "timestamp":
                            make_timestamp(announcement.timestamp),
                            "subject": announcement.subject,
                            "text": announcement.text})

        # Private messages
        for message in participation.messages:
            if message.timestamp > last_notification \
                    and message.timestamp < self.timestamp:
                res.append({"type": "message",
                            "timestamp": make_timestamp(message.timestamp),
                            "subject": message.subject,
                            "text": message.text})

        # Answers to questions
        for question in participation.questions:
            if question.reply_timestamp is not None \
                    and question.reply_timestamp > last_notification \
                    and question.reply_timestamp < self.timestamp:
                subject = question.reply_subject
                text = question.reply_text
                if question.reply_subject is None:
                    subject = question.reply_text
                    text = ""
                elif question.reply_text is None:
                    text = ""
                res.append({"type": "question",
                            "timestamp":
                            make_timestamp(question.reply_timestamp),
                            "subject": subject,
                            "text": text})

        # Update the unread_count cookie before taking notifications
        # into account because we don't want to count them.
        prev_unread_count = self.get_secure_cookie("unread_count")
        next_unread_count = len(res) + (
            int(prev_unread_count) if prev_unread_count is not None else 0)
        self.set_secure_cookie("unread_count", "%d" % next_unread_count)

        # Simple notifications
        notifications = self.application.service.notifications
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


class PrintingHandler(BaseHandler):
    """Serve the interface to print and handle submitted print jobs.

    """
    @tornado.web.authenticated
    @actual_phase_required(0, 1, 2)
    def get(self):
        participation = self.current_user

        if not self.r_params["printing_enabled"]:
            self.redirect("/")
            return

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
    def post(self):
        participation = self.current_user

        if not self.r_params["printing_enabled"]:
            self.redirect("/")
            return

        printjobs = self.sql_session.query(PrintJob)\
            .filter(PrintJob.participation == participation)\
            .all()
        old_count = len(printjobs)
        if config.max_jobs_per_user <= old_count:
            self.application.service.add_notification(
                participation.user.username,
                self.timestamp,
                self._("Too many print jobs!"),
                self._("You have reached the maximum limit of "
                       "at most %d print jobs.") % config.max_jobs_per_user,
                NOTIFICATION_ERROR)
            self.redirect("/printing")
            return

        # Ensure that the user did not submit multiple files with the
        # same name and that the user sent exactly one file.
        if any(len(filename) != 1
               for filename in self.request.files.values()) \
                or set(self.request.files.keys()) != set(["file"]):
            self.application.service.add_notification(
                participation.user.username,
                self.timestamp,
                self._("Invalid format!"),
                self._("Please select the correct files."),
                NOTIFICATION_ERROR)
            self.redirect("/printing")
            return

        filename = self.request.files["file"][0]["filename"]
        data = self.request.files["file"][0]["body"]

        # Check if submitted file is small enough.
        if len(data) > config.max_print_length:
            self.application.service.add_notification(
                participation.user.username,
                self.timestamp,
                self._("File too big!"),
                self._("Each file must be at most %d bytes long.") %
                config.max_print_length,
                NOTIFICATION_ERROR)
            self.redirect("/printing")
            return

        # We now have to send the file to the destination...
        try:
            digest = self.application.service.file_cacher.put_file_content(
                data,
                "Print job sent by %s at %d." % (
                    participation.user.username,
                    make_timestamp(self.timestamp)))

        # In case of error, the server aborts
        except Exception as error:
            logger.error("Storage failed! %s", error)
            self.application.service.add_notification(
                participation.user.username,
                self.timestamp,
                self._("Print job storage failed!"),
                self._("Please try again."),
                NOTIFICATION_ERROR)
            self.redirect("/printing")
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
        self.application.service.printing_service.new_printjob(
            printjob_id=printjob.id)
        self.application.service.add_notification(
            participation.user.username,
            self.timestamp,
            self._("Print job received"),
            self._("Your print job has been received."),
            NOTIFICATION_SUCCESS)
        self.redirect("/printing")


class DocumentationHandler(BaseHandler):
    """Displays the instruction (compilation lines, documentation,
    ...) of the contest.

    """
    @tornado.web.authenticated
    def get(self):
        self.render("documentation.html", **self.r_params)
