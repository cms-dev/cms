#!/usr/bin/env python2
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

"""User-related database interface for SQLAlchemy.

"""

from __future__ import absolute_import

from datetime import timedelta

from sqlalchemy.schema import Column, ForeignKey, UniqueConstraint
from sqlalchemy.types import Boolean, Integer, String, Unicode, DateTime, \
    Interval
from sqlalchemy.orm import relationship, backref

from . import Base, Contest


def generate_random_password():
    import random
    chars = "abcdefghijklmnopqrstuvwxyz"
    return "".join([random.choice(chars) for _ in xrange(6)])


class Group(Base):
    """Class to store a group of users (for timing, etc.).

    """
    __tablename__ = 'group'
    __table_args__ = (
        UniqueConstraint('contest_id', 'name'),
    )

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    name = Column(
        Unicode,
        nullable=False)

    # Beginning and ending of the contest.
    start = Column(
        DateTime,
        nullable=True)
    stop = Column(
        DateTime,
        nullable=True)

    # Max contest time for each user in seconds.
    per_user_time = Column(
        Interval,
        nullable=True)

    # Contest (id and object) to which this user group belongs.
    contest_id = Column(
        Integer,
        ForeignKey(Contest.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        index=True) # nullable=True does not work due to a circular dependency
    contest = relationship(
        Contest,
        backref=backref('groups',
                        cascade="all, delete-orphan",
                        passive_deletes=True),
        primaryjoin="Contest.id==Group.contest_id",
        post_update=True)

    def phase(self, timestamp):
        """Return: -1 if contest isn't started yet at time timestamp,
                    0 if the contest is active at time timestamp,
                    1 if the contest has ended.
                            (for this group)

        timestamp (int): the time we are iterested in.
        return (int): contest phase as above.

        """
        if self.start is not None and self.start > timestamp:
            return -1
        if self.stop is None or self.stop > timestamp:
            return 0
        return 1


class User(Base):
    """Class to store a 'user participating in a contest'.

    """
    # TODO: we really need to split this as a user (as in: not paired
    # with a contest) and a participation.
    __tablename__ = 'users'
    __table_args__ = (
        UniqueConstraint('contest_id', 'username'),
    )

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # Real name (human readable) of the user.
    first_name = Column(
        Unicode,
        nullable=False)
    last_name = Column(
        Unicode,
        nullable=False)

    # Username and password to log in the CWS.
    username = Column(
        Unicode,
        nullable=False)
    password = Column(
        Unicode,
        nullable=False,
        default=generate_random_password)

    # Email for any communications in case of remote contest.
    email = Column(
        Unicode,
        nullable=True)

    # User can log in CWS only from this ip.
    ip = Column(
        Unicode,
        nullable=True)

    # A hidden user is used only for debugging purpose.
    hidden = Column(
        Boolean,
        nullable=False,
        default=False)

    # Contest (id and object) to which the user is participating.
    contest_id = Column(
        Integer,
        ForeignKey(Contest.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    contest = relationship(
        Contest,
        backref=backref("users",
                        cascade="all, delete-orphan",
                        passive_deletes=True))

    # Group this user belongs to
    group_id = Column(
        Integer,
        ForeignKey(Group.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    group = relationship(
        Group,
        backref=backref("users",
                        cascade="all, delete-orphan",
                        passive_deletes=True))

    # A JSON-encoded dictionary of lists of strings: statements["a"]
    # contains the language codes of the statements that will be
    # highlighted to this user for task "a".
    primary_statements = Column(
        String,
        nullable=False,
        default="{}")

    # Timezone for the user. All timestamps in CWS will be shown using
    # the timezone associated to the logged-in user or (if it's None
    # or an invalid string) the timezone associated to the contest or
    # (if it's None or an invalid string) the local timezone of the
    # server. This value has to be a string like "Europe/Rome",
    # "Australia/Sydney", "America/New_York", etc.
    timezone = Column(
        Unicode,
        nullable=True)

    # Starting time: for contests where every user has at most x hours
    # of the y > x hours totally available, this is the time the user
    # decided to start his/her time-frame.
    starting_time = Column(
        DateTime,
        nullable=True)

    # An extra amount of time allocated for this user.
    extra_time = Column(
        Interval,
        nullable=False,
        default=timedelta())

    # Follows the description of the fields automatically added by
    # SQLAlchemy.
    # messages (list of Message objects)
    # questions (list of Question objects)
    # submissions (list of Submission objects)
    # user_tests (list of UserTest objects)

    # Moreover, we have the following methods.
    # get_tokens (defined in __init__.py)


class Message(Base):
    """Class to store a private message from the managers to the
    user.

    """
    __tablename__ = 'messages'

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # Time the message was sent.
    timestamp = Column(
        DateTime,
        nullable=False)

    # Subject and body of the message.
    subject = Column(
        Unicode,
        nullable=False)
    text = Column(
        Unicode,
        nullable=False)

    # User (id and object) owning the message.
    user_id = Column(
        Integer,
        ForeignKey(User.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    user = relationship(
        User,
        backref=backref('messages',
                        order_by=[timestamp],
                        cascade="all, delete-orphan",
                        passive_deletes=True))


class Question(Base):
    """Class to store a private question from the user to the
    managers, and its answer.

    """
    __tablename__ = 'questions'

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # Time the question was made.
    question_timestamp = Column(
        DateTime,
        nullable=False)

    # Subject and body of the question.
    subject = Column(
        Unicode,
        nullable=False)
    text = Column(
        Unicode,
        nullable=False)

    # Time the reply was sent.
    reply_timestamp = Column(
        DateTime,
        nullable=True)

    # Has this message been ignored by the admins?
    ignored = Column(
        Boolean,
        nullable=False,
        default=False)

    # Short (as in 'chosen amongst some predetermined choices') and
    # long answer.
    reply_subject = Column(
        Unicode,
        nullable=True)
    reply_text = Column(
        Unicode,
        nullable=True)

    # User (id and object) owning the question.
    user_id = Column(
        Integer,
        ForeignKey(User.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    user = relationship(
        User,
        backref=backref('questions',
                        order_by=[question_timestamp, reply_timestamp],
                        cascade="all, delete-orphan",
                        passive_deletes=True))
