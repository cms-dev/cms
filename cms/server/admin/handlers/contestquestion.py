#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
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

"""Question-related handlers for AWS for a specific contest.

"""

from abc import ABCMeta, abstractmethod
import logging

import collections
try:
    collections.MutableMapping
except:
    # Monkey-patch: Tornado 4.5.3 does not work on Python 3.11 by default
    collections.MutableMapping = collections.abc.MutableMapping

import tornado.web

from cms.db import Contest, Question, Participation
from cmscommon.datetime import make_datetime
from .base import BaseHandler, require_permission


logger = logging.getLogger(__name__)


class QuestionsHandler(BaseHandler):
    """Page to see and send messages to all the contestants.

    """
    @require_permission(BaseHandler.AUTHENTICATED)
    def get(self, contest_id):
        self.contest = self.safe_get_item(Contest, contest_id)

        self.r_params = self.render_params()
        self.r_params["questions"] = self.sql_session.query(Question)\
            .join(Participation)\
            .filter(Participation.contest_id == contest_id)\
            .order_by(Question.question_timestamp.desc())\
            .order_by(Question.id).all()
        self.render("questions.html", **self.r_params)



class QuestionActionHandler(BaseHandler, metaclass=ABCMeta):
    """Base class for handlers for actions on questions."""

    @abstractmethod
    def process_question(self, question: Question):
        """Called on POST requests. Perform the appropriate action on the
        question."""
        pass

    @require_permission(BaseHandler.PERMISSION_MESSAGING)
    def post(self, contest_id, question_id):
        user_id = self.get_argument("user_id", None)
        if user_id is not None:
            ref = self.url("contest", contest_id, "user", user_id, "edit")
        else:
            ref = self.url("contest", contest_id, "questions")

        question = self.safe_get_item(Question, question_id)
        self.contest = self.safe_get_item(Contest, contest_id)

        # Protect against URLs providing incompatible parameters.
        if self.contest is not question.participation.contest:
            raise tornado.web.HTTPError(404)

        self.process_question(question)
        self.redirect(ref)

class QuestionReplyHandler(QuestionActionHandler):
    """Called when the manager replies to a question made by a user.

    """

    def process_question(self, question):
        reply_subject_code: str = self.get_argument(
            "reply_question_quick_answer", "")
        question.reply_text = self.get_argument("reply_question_text", "")

        # Ignore invalid answers
        if reply_subject_code not in Question.QUICK_ANSWERS:
            question.reply_subject = ""
        else:
            # Quick answer given, ignore long answer.
            question.reply_subject = \
                Question.QUICK_ANSWERS[reply_subject_code]
            question.reply_text = ""

        question.reply_timestamp = make_datetime()
        question.admin = self.current_user

        if self.try_commit():
            logger.info("Reply sent to user %s in contest %s for "
                        "question with id %s.",
                        question.participation.user.username,
                        question.participation.contest.name,
                        question.id)

class QuestionIgnoreHandler(QuestionActionHandler):
    """Called when the manager chooses to ignore or stop ignoring a
    question.

    """
    def process_question(self, question):
        should_ignore = self.get_argument("ignore", "no") == "yes"

        # Commit the change.
        question.ignored = should_ignore
        question.admin = self.current_user
        if self.try_commit():
            logger.info("Question '%s' by user %s in contest %s has "
                        "been %s",
                        question.subject,
                        question.participation.user.username,
                        question.participation.contest.name,
                        "ignored" if should_ignore else "unignored")


class QuestionClaimHandler(QuestionActionHandler):
    """Called when the manager chooses to claim or unclaim a question."""

    def process_question(self, question):
        # Can claim/unclaim only a question not ignored or answered.
        if question.ignored or question.reply_timestamp is not None:
            raise tornado.web.HTTPError(405)

        should_claim = self.get_argument("claim", "no") == "yes"

        # Commit the change.
        if should_claim:
            question.admin = self.current_user
        else:
            question.admin = None
        if self.try_commit():
            logger.info("Question '%s' by user %s in contest %s has "
                        "been %s by %s",
                        question.subject,
                        question.participation.user.username,
                        question.participation.contest.name,
                        "claimed" if should_claim else "unclaimed",
                        self.current_user.name)
