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

"""Communication-related handlers for CWS.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging

import tornado.web

from cms.db import Question
from cms.server import multi_contest

from .contest import ContestHandler, NOTIFICATION_ERROR, NOTIFICATION_SUCCESS


logger = logging.getLogger(__name__)


class CommunicationHandler(ContestHandler):
    """Displays the private conversations between the logged in user
    and the contest managers..

    """
    @tornado.web.authenticated
    @multi_contest
    def get(self):
        self.set_secure_cookie(self.contest.name + "_unread_count", "0")
        self.render("communication.html", **self.r_params)


class QuestionHandler(ContestHandler):
    """Called when the user submits a question.

    """
    @tornado.web.authenticated
    @multi_contest
    def post(self):
        participation = self.current_user

        # User can post only if we want.
        if not self.contest.allow_questions:
            raise tornado.web.HTTPError(404)

        fallback_page = self.contest_url("communication")

        subject_length = len(self.get_argument("question_subject", ""))
        text_length = len(self.get_argument("question_text", ""))
        if subject_length > 50 or text_length > 2000:
            logger.warning("Long question (%d, %d) dropped for user %s.",
                           subject_length, text_length,
                           self.current_user.user.username)
            self.application.service.add_notification(
                self.current_user.user.username,
                self.timestamp,
                self._("Question too big!"),
                self._("You have reached the question length limit."),
                NOTIFICATION_ERROR)
            self.redirect(fallback_page)
            return

        question = Question(self.timestamp,
                            self.get_argument("question_subject", ""),
                            self.get_argument("question_text", ""),
                            participation=participation)
        self.sql_session.add(question)
        self.sql_session.commit()

        logger.info(
            "Question submitted by user %s.", participation.user.username)

        # Add "All ok" notification.
        self.application.service.add_notification(
            participation.user.username,
            self.timestamp,
            self._("Question received"),
            self._("Your question has been received, you will be "
                   "notified when it is answered."),
            NOTIFICATION_SUCCESS)

        self.redirect(fallback_page)
