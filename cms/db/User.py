#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""User-related database interface for SQLAlchemy. Not to be used
directly (import it from SQLAlchemyAll).

"""

from datetime import timedelta

from sqlalchemy import Column, ForeignKey, UniqueConstraint, \
     Boolean, Integer, String, DateTime, Interval
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import relationship, backref

from cms.db.SQLAlchemyUtils import Base
from cms.db.Contest import Contest
from cmscommon.DateTime import make_datetime, make_timestamp


class User(Base):
    """Class to store a 'user participating in a contest'. Not to be
    used directly (import it from SQLAlchemyAll).

    """
    # TODO: we really need to split this as a user (as in: not paired
    # with a contest) and a participation.
    __tablename__ = 'users'
    __table_args__ = (
        UniqueConstraint('contest_id', 'username',
                         name='cst_user_contest_id_username'),
        )

    # Auto increment primary key.
    id = Column(Integer, primary_key=True)

    # Real name (human readable) of the user.
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)

    # Username and password to log in the CWS.
    username = Column(String, nullable=False)
    password = Column(String, nullable=False)

    # Email for any communications in case of remote contest.
    email = Column(String, nullable=False)

    # User can log in CWS only from this ip.
    ip = Column(String, nullable=True)

    # A hidden user is used only for debugging purpose.
    hidden = Column(Boolean, nullable=False)

    # Contest (id and object) to which the user is participating.
    contest_id = Column(Integer,
                        ForeignKey(Contest.id,
                                   onupdate="CASCADE", ondelete="CASCADE"),
                        nullable=False,
                        index=True)
    contest = relationship(
        Contest,
        backref=backref("users",
                        single_parent=True,
                        cascade="all, delete, delete-orphan"))

    # A JSON-encoded dictionary of lists of strings: statements["a"]
    # contains the language codes of the statments that will be
    # highlighted to this user for task "a".
    primary_statements = Column(String, nullable=False)

    # Timezone for the user. All timestamps in CWS will be shown using
    # the timezone associated to the logged-in user or (if it's None
    # or an invalid string) the timezone associated to the contest or
    # (if it's None or an invalid string) the local timezone of the
    # server. This value has to be a string like "Europe/Rome",
    # "Australia/Sydney", "America/New_York", etc.
    timezone = Column(String, nullable=True)

    # Starting time: for contests where every user has at most x hours
    # of the y > x hours totally available. This is the first time the
    # user logged in while the contest was active.
    starting_time = Column(DateTime, nullable=True)

    # An extra amount of time allocated for this user
    extra_time = Column(Interval, nullable=False)

    # Follows the description of the fields automatically added by
    # SQLAlchemy.
    # messages (list of Message objects)
    # questions (list of Question objects)
    # submissions (list of Submission objects)
    # user_tests (list of UserTest objects)

    # Moreover, we have the following methods.
    # get_tokens (defined in SQLAlchemyAll)

    def __init__(self, first_name, last_name, username, password=None,
                 email=None, ip=None, contest=None, hidden=False,
                 primary_statements=None, timezone=None,
                 starting_time=None, extra_time=timedelta(),
                 messages=None, questions=None, submissions=None):
        if password is None:
            import random
            chars = "abcdefghijklmnopqrstuvwxyz"
            password = "".join([random.choice(chars)
                                for unused_i in xrange(6)])

        self.first_name = first_name
        self.last_name = last_name
        self.username = username
        self.password = password
        self.email = email if email is not None else ""
        self.ip = ip if ip is not None else "0.0.0.0"
        self.hidden = hidden
        self.primary_statements = primary_statements if primary_statements is not None else "{}"
        self.timezone = timezone
        self.starting_time = starting_time
        self.extra_time = extra_time
        self.messages = messages if messages is not None else []
        self.questions = questions if questions is not None else []
        self.contest = contest
        self.submissions = submissions if submissions is not None else []

    def export_to_dict(self, skip_submissions=False):
        """Return object data as a dictionary.

        """
        submissions = []
        if not skip_submissions:
            submissions = [submission.export_to_dict()
                           for submission in self.submissions]
        return {'first_name':    self.first_name,
                'last_name':     self.last_name,
                'username':      self.username,
                'password':      self.password,
                'email':         self.email,
                'ip':            self.ip,
                'hidden':        self.hidden,
                'primary_statements': self.primary_statements,
                'timezone':      self.timezone,
                'starting_time': make_timestamp(self.starting_time)
                if self.starting_time is not None else None,
                'extra_time':    self.extra_time.total_seconds(),
                'messages':      [message.export_to_dict()
                                  for message in self.messages],
                'questions':     [question.export_to_dict()
                                  for question in self.questions],
                'submissions':   submissions}


class Message(Base):
    """Class to store a private message from the managers to the
    user. Not to be used directly (import it from SQLAlchemyAll).

    """
    __tablename__ = 'messages'

    # Auto increment primary key.
    id = Column(Integer, primary_key=True)

    # Time the message was sent.
    timestamp = Column(DateTime, nullable=False)

    # Subject and body of the message.
    subject = Column(String, nullable=False)
    text = Column(String, nullable=False)

    # User (id and object) owning the message.
    user_id = Column(Integer,
                     ForeignKey(User.id,
                                onupdate="CASCADE", ondelete="CASCADE"),
                     nullable=False,
                     index=True)
    user = relationship(
        User,
        backref=backref('messages',
                        single_parent=True,
                        order_by=[timestamp],
                        cascade="all, delete, delete-orphan"))

    def __init__(self, timestamp, subject, text, user=None):
        self.timestamp = timestamp
        self.subject = subject
        self.text = text
        self.user = user

    def export_to_dict(self):
        """Return object data as a dictionary.

        """
        return {'timestamp': make_timestamp(self.timestamp),
                'subject':   self.subject,
                'text':      self.text}

    @classmethod
    def import_from_dict(cls, data):
        """Build the object using data from a dictionary.

        """
        data['timestamp'] = make_datetime(data['timestamp'])
        return cls(**data)


class Question(Base):
    """Class to store a private question from the user to the
    managers, and its answer. Not to be used directly (import it from
    SQLAlchemyAll).

    """
    __tablename__ = 'questions'

    # Auto increment primary key.
    id = Column(Integer, primary_key=True)

    # Time the question was made.
    question_timestamp = Column(DateTime, nullable=False)

    # Subject and body of the question.
    subject = Column(String, nullable=False)
    text = Column(String, nullable=False)

    # Time the reply was sent.
    reply_timestamp = Column(DateTime, nullable=True)

    # Has this message been ignored by the admins?
    ignored = Column(Boolean, nullable=False)

    # Short (as in 'chosen amongst some predetermined choices') and
    # long answer.
    reply_subject = Column(String, nullable=True)
    reply_text = Column(String, nullable=True)

    # User (id and object) owning the question.
    user_id = Column(Integer,
                     ForeignKey(User.id,
                                onupdate="CASCADE", ondelete="CASCADE"),
                     nullable=False,
                     index=True)
    user = relationship(
        User,
        backref=backref('questions',
                        single_parent=True,
                        order_by=[question_timestamp, reply_timestamp],
                        cascade="all, delete, delete-orphan"))

    def __init__(self, question_timestamp, subject, text,
                 reply_timestamp=None, reply_subject=None, reply_text=None,
                 user=None, ignored=False):
        self.question_timestamp = question_timestamp
        self.subject = subject
        self.text = text
        self.reply_timestamp = reply_timestamp
        self.ignored = ignored
        self.reply_subject = reply_subject
        self.reply_text = reply_text
        self.user = user

    def export_to_dict(self):
        """Return object data as a dictionary.

        """
        return {'question_timestamp': make_timestamp(self.question_timestamp),
                'subject':            self.subject,
                'text':               self.text,
                'reply_timestamp':    make_timestamp(self.reply_timestamp)
                if self.reply_timestamp is not None else None,
                'reply_subject':      self.reply_subject,
                'reply_text':         self.reply_text,
                'ignored':            self.ignored}

    @classmethod
    def import_from_dict(cls, data):
        """Build the object using data from a dictionary.

        """
        data['question_timestamp'] = make_datetime(data['question_timestamp'])
        if data['reply_timestamp'] is not None:
            data['reply_timestamp'] = make_datetime(data['reply_timestamp'])
        return cls(**data)
