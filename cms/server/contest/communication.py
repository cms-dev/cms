#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2015 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""Communication-related helpers for CWS.

"""

import logging

import gevent
import requests

from cms import config
from cms.db import Question, Announcement, Message
from cmscommon.datetime import make_timestamp


logger = logging.getLogger(__name__)


# Dummy function to mark translatable strings.
def N_(msgid):
    return msgid


class QuestionsNotAllowed(Exception):
    """Raised when questions are disallowed by the contest rules."""

    pass


class UnacceptableQuestion(Exception):
    """Raised when a question can't be accepted."""

    def __init__(self, subject, text, text_params=None):
        super().__init__(subject, text, text_params)
        self.subject = subject
        self.text = text
        self.text_params = text_params


def send_telegram_message(content):
    """Send a message as the Telegram bot with the specified content.
    """
    api_url = "https://api.telegram.org/bot{}/sendMessage" \
        .format(config.telegram_bot_token)
    body = {"chat_id": config.telegram_bot_chat_id,
            "text": content,
            "parse_mode": "HTML"}
    res = requests.post(api_url, data=body)
    if res.status_code != 200:
        logger.warn("Failed to send Telegram notification: %s", res.json())
    else:
        logger.debug("Telegram notification sent for the question")


def send_telegram_question_notification(question):
    """Craft and send a Telegram message with the question content.

    This is a no-op if the bot is not configured.

    This also takes care of formatting the message to be sent, escaping
    it and making sure it doesn't exceed the bot message size limit
    (4096 bytes).

    The message is sent in a different greenlet, so that it doesn't
    block the caller if the network is slow.
    """
    if not config.telegram_bot_token or not config.telegram_bot_chat_id:
        return
    trim = lambda s, n: s[:n] + "…" if len(s) > n else s
    escape = lambda t: t.replace("<", "&lt;").replace(">", "&gt;")
    message = """<b>New question</b>
From: <code>{username}</code>
Subject: <i>{subject}</i>

{text}
""".format(
        username=trim(escape(question.participation.user.username), 50),
        subject=trim(escape(question.subject), 100),
        text=trim(escape(question.text), 3000))
    gevent.spawn(send_telegram_message, message)


def accept_question(sql_session, participation, timestamp, subject, text):
    """Add a contestant-submitted question to the database.

    Validate and add a question received from a contestant (usually
    through CWS) to the database.

    sql_session (Session): the SQLAlchemy database session to use.
    participation (Participation): the participation of the user who
        posed the question.
    timestamp (datetime): when the question was asked.
    subject (str): the subject of the question.
    text (str): the body of the question.

    return (Question): the question that was added to the database.

    raise (QuestionsNotAllowed): if the contest doesn't allow
        contestants to ask questions.
    raise (UnacceptableQuestion): if some conditions necessary to
        accept the questions were not met.

    """
    if not participation.contest.allow_questions:
        raise QuestionsNotAllowed()

    subject_length = len(subject)
    text_length = len(text)
    if subject_length > Question.MAX_SUBJECT_LENGTH \
            or text_length > Question.MAX_TEXT_LENGTH:
        logger.warning("Long question (%d, %d) dropped for user %s.",
                       subject_length, text_length,
                       participation.user.username)
        raise UnacceptableQuestion(
            N_("Question too long!"),
            N_("Subject must be at most %(max_subject_length)d characters, "
               "content at most %(max_text_length)d."),
            {"max_subject_length": Question.MAX_SUBJECT_LENGTH,
             "max_text_length": Question.MAX_TEXT_LENGTH})

    question = Question(timestamp, subject, text, participation=participation)
    sql_session.add(question)

    logger.info("Question submitted by user %s.", participation.user.username)

    try:
        send_telegram_question_notification(question)
    except Exception as e:
        logger.exception("Error occurred while sending Telegram notification")

    return question


def get_communications(sql_session, participation, timestamp, after=None):
    """Retrieve some contestant's communications at some given time.

    Return the list of admin-to-contestant communications (that is,
    announcements, messages and answers to questions) for the given
    contestant that occurred up to and including the given time.
    Optionally, ignore the communications that occurred before another
    given time. The result will be returned in a JSON-compatible format
    (that is, a tree of numbers, strings, lists and dicts).

    sql_session (Session): the SQLAlchemy database session to use.
    participation (Participation): the participation of the user whose
        communications are to be returned.
    timestamp (datetime): the moment in time at which the "snapshot" of
        the communications is to be taken (i.e., communications that
        will occur after this moment, but are already in the database,
        are to be ignored).
    after (datetime|None): if not none, ignore also the communications
        that were received at or before this moment in time.

    return ([dict]): for each communication a dictionary with 4 fields:
        type (either "announcement", "message" or "question"), subject,
        text and timestamp (the number of seconds since the UNIX epoch,
        as a float).

    """

    res = list()

    # Announcements
    query = sql_session.query(Announcement) \
        .filter(Announcement.contest == participation.contest) \
        .filter(Announcement.timestamp <= timestamp)
    if after is not None:
        query = query.filter(Announcement.timestamp > after)
    for announcement in query.all():
        res.append({"type": "announcement",
                    "timestamp": make_timestamp(announcement.timestamp),
                    "subject": announcement.subject,
                    "text": announcement.text})

    # Private messages
    query = sql_session.query(Message) \
        .filter(Message.participation == participation) \
        .filter(Message.timestamp <= timestamp)
    if after is not None:
        query = query.filter(Message.timestamp > after)
    for message in query.all():
        res.append({"type": "message",
                    "timestamp": make_timestamp(message.timestamp),
                    "subject": message.subject,
                    "text": message.text})

    # Answers to questions
    query = sql_session.query(Question) \
        .filter(Question.participation == participation) \
        .filter(Question.reply_timestamp.isnot(None)) \
        .filter(Question.reply_timestamp <= timestamp)
    if after is not None:
        query = query.filter(Question.reply_timestamp > after)
    for question in query.all():
        subject = question.reply_subject
        text = question.reply_text
        if text is None:
            text = ""
        if subject is None:
            subject, text = text, ""
        res.append({"type": "question",
                    "timestamp": make_timestamp(question.reply_timestamp),
                    "subject": subject,
                    "text": text})

    return res
