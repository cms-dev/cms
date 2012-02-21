#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
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

from sqlalchemy import Column, ForeignKey, Boolean, Integer, Float, String
from sqlalchemy.orm import relationship, backref

from cms.db.SQLAlchemyUtils import Base
from cms.db.Contest import Contest


class User(Base):
    """Class to store a 'user participating in a contest'. Not to be
    used directly (import it from SQLAlchemyAll).

    """
    # TODO: we really need to split this as a user (as in: not paired
    # with a contest) and a participation.
    __tablename__ = 'users'

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

    # For future use (read: APIO contest times depend on the timezone
    # of the user).
    timezone = Column(Float, nullable=False)

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

    # Starting time: for contests where every user has at most x hours
    # of the y > x hours totally available. This is the first time the
    # user logged in while the contest was active.
    starting_time = Column(Integer, nullable=True)

    # Follows the description of the fields automatically added by
    # SQLAlchemy.
    # messages (list of Message objects)
    # questions (list of Question objects)
    # submissions (list of Submission objects)

    # Moreover, we have the following methods.
    # get_tokens (defined in SQLAlchemyAll)

    def __init__(self, first_name, last_name, username, password=None,
                 email=None, ip=None, timezone=0.0, contest=None,
                 hidden=False, starting_time=None, messages=None,
                 questions=None, submissions=None):
        if password is None:
            import random
            chars = "abcdefghijklmnopqrstuvwxyz"
            password = "".join([random.choice(chars) for i in xrange(6)])

        self.first_name = first_name
        self.last_name = last_name
        self.username = username
        self.password = password
        self.timezone = timezone
        self.email = email if email is not None else ""
        self.ip = ip if ip is not None else "0.0.0.0"
        self.hidden = hidden
        self.starting_time = starting_time
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
                'email'   :      self.email,
                'timezone':      self.timezone,
                'ip':            self.ip,
                'hidden':        self.hidden,
                'starting_time': self.starting_time,
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
    timestamp = Column(Integer, nullable=False)

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
        return {'timestamp': self.timestamp,
                'subject':   self.subject,
                'text':      self.text}


class Question(Base):
    """Class to store a private question from the user to the
    managers, and its answer. Not to be used directly (import it from
    SQLAlchemyAll).

    """
    __tablename__ = 'questions'

    # Auto increment primary key.
    id = Column(Integer, primary_key=True)

    # Time the question was made.
    question_timestamp = Column(Integer, nullable=False)

    # Subject and body of the question.
    subject = Column(String, nullable=False)
    text = Column(String, nullable=False)

    # Time the reply was sent.
    reply_timestamp = Column(Integer, nullable=True)

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
        return {'question_timestamp': self.question_timestamp,
                'subject':            self.subject,
                'text':               self.text,
                'reply_timestamp':    self.reply_timestamp,
                'reply_subject':      self.reply_subject,
                'reply_text':         self.reply_text,
                'ignored':            self.ignored}
