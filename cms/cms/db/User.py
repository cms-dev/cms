#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2011 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2011 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2011 Matteo Boscariol <boscarim@hotmail.com>
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
    real_name = Column(String, nullable=False)

    # Username and password to log in the CWS.
    username = Column(String, nullable=False)
    password = Column(String, nullable=False)

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
                        nullable=False)
    contest = relationship(
        Contest,
        backref=backref("users",
                        single_parent=True,
                        cascade="all, delete, delete-orphan"))

    # Follows the description of the fields automatically added by
    # SQLAlchemy.
    # messages (list of Message objects)
    # questions (list of Question objects)
    # tokens (list of Token objects)

    def __init__(self, real_name, username, password, ip,
                 timezone=0.0, contest=None, tokens=None,
                 hidden=False, messages=None, questions=None):
        self.real_name = real_name
        self.username = username
        self.password = password
        self.timezone = timezone
        self.ip = ip
        if tokens == None:
            tokens = []
        self.tokens = tokens
        self.hidden = hidden
        if messages == None:
            messages = []
        self.messages = messages
        if questions == None:
            questions = []
        self.questions = questions
        self.contest = contest


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
                     nullable=False)
    user = relationship(
        User,
        backref=backref('messages',
                        single_parent=True,
                        cascade="all, delete, delete-orphan"))

    def __init__(self, timestamp, subject, text, user=None):
        self.timestamp = timestamp
        self.subject = subject
        self.text = text
        self.user = user


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

    # Short (as in 'chosen amongst some predetermined choices') and
    # long answer.
    short_reply = Column(String, nullable=True)
    long_reply = Column(String, nullable=True)

    # User (id and object) owning the question.
    user_id = Column(Integer,
                     ForeignKey(User.id,
                                onupdate="CASCADE", ondelete="CASCADE"),
                     nullable=False)
    user = relationship(
        User,
        backref=backref('questions',
                        single_parent=True,
                        cascade="all, delete, delete-orphan"))

    def __init__(self, question_timestamp, subject, text,
                 reply_timestamp=None, short_reply=None, long_reply=None,
                 user=None):
        self.question_timestamp = question_timestamp
        self.subject = subject
        self.text = text
        self.reply_timestamp = reply_timestamp
        self.short_reply = short_reply
        self.long_reply = long_reply
        self.user = user
