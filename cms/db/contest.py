#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2016 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
# Copyright © 2016 Amir Keivan Mohtashami <akmohtashami97@gmail.com>
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

"""Contest-related database interface for SQLAlchemy.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa
from six import itervalues

from datetime import datetime, timedelta

from sqlalchemy.ext.orderinglist import ordering_list
from sqlalchemy.schema import Column, ForeignKey, CheckConstraint
from sqlalchemy.types import Integer, Unicode, DateTime, Interval, Enum, \
    Boolean, String
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ARRAY

from cms import TOKEN_MODE_DISABLED, TOKEN_MODE_FINITE, TOKEN_MODE_INFINITE

from . import Base, CodenameConstraint


class Contest(Base):
    """Class to store a contest (which is a single day of a
    programming competition).

    """
    __tablename__ = 'contests'
    __table_args__ = (
        CheckConstraint("start <= stop"),
        CheckConstraint("stop <= analysis_start"),
        CheckConstraint("analysis_start <= analysis_stop"),
        CheckConstraint("token_gen_initial <= token_gen_max"),
    )

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # Short name of the contest.
    name = Column(
        Unicode,
        CodenameConstraint("name"),
        nullable=False,
        unique=True)
    # Description of the contest (human readable).
    description = Column(
        Unicode,
        nullable=False)

    # The list of language codes of the localizations that contestants
    # are allowed to use (empty means all).
    allowed_localizations = Column(
        ARRAY(String),
        nullable=False,
        default=[])

    # The list of names of languages allowed in the contest.
    languages = Column(
        ARRAY(String),
        nullable=False,
        default=["C11 / gcc", "C++11 / g++", "Pascal / fpc"])

    # Whether contestants allowed to download their submissions.
    submissions_download_allowed = Column(
        Boolean,
        nullable=False,
        default=True)

    # Whether the user question is enabled.
    allow_questions = Column(
        Boolean,
        nullable=False,
        default=True)

    # Whether the user test interface is enabled.
    allow_user_tests = Column(
        Boolean,
        nullable=False,
        default=True)

    # Whether to prevent hidden participations to log in.
    block_hidden_participations = Column(
        Boolean,
        nullable=False,
        default=False)

    # Whether to allow username/password authentication
    allow_password_authentication = Column(
        Boolean,
        nullable=False,
        default=True)

    # Whether to enforce that the IP address of the request matches
    # the IP address or subnet specified for the participation (if
    # present).
    ip_restriction = Column(
        Boolean,
        nullable=False,
        default=True)

    # Whether to automatically log in users connecting from an IP
    # address specified in the ip field of a participation to this
    # contest.
    ip_autologin = Column(
        Boolean,
        nullable=False,
        default=False)

    # The parameters that control contest-tokens follow. Note that
    # their effect during the contest depends on the interaction with
    # the parameters that control task-tokens, defined on each Task.

    # The "kind" of token rules that will be active during the contest.
    # - disabled: The user will never be able to use any token.
    # - finite: The user has a finite amount of tokens and can choose
    #   when to use them, subject to some limitations. Tokens may not
    #   be all available at start, but given periodically during the
    #   contest instead.
    # - infinite: The user will always be able to use a token.
    token_mode = Column(
        Enum(TOKEN_MODE_DISABLED, TOKEN_MODE_FINITE, TOKEN_MODE_INFINITE,
             name="token_mode"),
        nullable=False,
        default="infinite")

    # The maximum number of tokens a contestant is allowed to use
    # during the whole contest (on all tasks).
    token_max_number = Column(
        Integer,
        CheckConstraint("token_max_number > 0"),
        nullable=True)

    # The minimum interval between two successive uses of tokens for
    # the same user (on any task).
    token_min_interval = Column(
        Interval,
        CheckConstraint("token_min_interval >= '0 seconds'"),
        nullable=False,
        default=timedelta())

    # The parameters that control generation (if mode is "finite"):
    # the user starts with "initial" tokens and receives "number" more
    # every "interval", but their total number is capped to "max".
    token_gen_initial = Column(
        Integer,
        CheckConstraint("token_gen_initial >= 0"),
        nullable=False,
        default=2)
    token_gen_number = Column(
        Integer,
        CheckConstraint("token_gen_number >= 0"),
        nullable=False,
        default=2)
    token_gen_interval = Column(
        Interval,
        CheckConstraint("token_gen_interval > '0 seconds'"),
        nullable=False,
        default=timedelta(minutes=30))
    token_gen_max = Column(
        Integer,
        CheckConstraint("token_gen_max > 0"),
        nullable=True)

    # Beginning and ending of the contest.
    start = Column(
        DateTime,
        nullable=False,
        default=datetime(2000, 1, 1))
    stop = Column(
        DateTime,
        nullable=False,
        default=datetime(2030, 1, 1))

    # Beginning and ending of the contest anaylsis mode.
    analysis_enabled = Column(
        Boolean,
        nullable=False,
        default=False)
    analysis_start = Column(
        DateTime,
        nullable=False,
        default=datetime(2030, 1, 1))
    analysis_stop = Column(
        DateTime,
        nullable=False,
        default=datetime(2030, 1, 1))

    # Timezone for the contest. All timestamps in CWS will be shown
    # using the timezone associated to the logged-in user or (if it's
    # None or an invalid string) the timezone associated to the
    # contest or (if it's None or an invalid string) the local
    # timezone of the server. This value has to be a string like
    # "Europe/Rome", "Australia/Sydney", "America/New_York", etc.
    timezone = Column(
        Unicode,
        nullable=True)

    # Max contest time for each user in seconds.
    per_user_time = Column(
        Interval,
        CheckConstraint("per_user_time >= '0 seconds'"),
        nullable=True)

    # Maximum number of submissions or user_tests allowed for each user
    # during the whole contest or None to not enforce this limitation.
    max_submission_number = Column(
        Integer,
        CheckConstraint("max_submission_number > 0"),
        nullable=True)
    max_user_test_number = Column(
        Integer,
        CheckConstraint("max_user_test_number > 0"),
        nullable=True)

    # Minimum interval between two submissions or user_tests, or None to
    # not enforce this limitation.
    min_submission_interval = Column(
        Interval,
        CheckConstraint("min_submission_interval > '0 seconds'"),
        nullable=True)
    min_user_test_interval = Column(
        Interval,
        CheckConstraint("min_user_test_interval > '0 seconds'"),
        nullable=True)

    # The scores for this contest will be rounded to this number of
    # decimal places.
    score_precision = Column(
        Integer,
        CheckConstraint("score_precision >= 0"),
        nullable=False,
        default=0)

    # These one-to-many relationships are the reversed directions of
    # the ones defined in the "child" classes using foreign keys.

    tasks = relationship(
        "Task",
        collection_class=ordering_list("num"),
        order_by="[Task.num]",
        cascade="all",
        passive_deletes=True,
        back_populates="contest")

    announcements = relationship(
        "Announcement",
        order_by="[Announcement.timestamp]",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="contest")

    participations = relationship(
        "Participation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="contest")

    def phase(self, timestamp):
        """Return: -1 if contest isn't started yet at time timestamp,
                    0 if the contest is active at time timestamp,
                    1 if the contest has ended but analysis mode
                      hasn't started yet
                    2 if the contest has ended and analysis mode is active
                    3 if the contest has ended and analysis mode is disabled or
                      has ended

        timestamp (datetime): the time we are iterested in.
        return (int): contest phase as above.

        """
        if timestamp < self.start:
            return -1
        if timestamp <= self.stop:
            return 0
        if self.analysis_enabled:
            if timestamp < self.analysis_start:
                return 1
            elif timestamp <= self.analysis_stop:
                return 2
        return 3


class Announcement(Base):
    """Class to store a messages sent by the contest managers to all
    the users.

    """
    __tablename__ = 'announcements'

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # Time, subject and text of the announcement.
    timestamp = Column(
        DateTime,
        nullable=False)
    subject = Column(
        Unicode,
        nullable=False)
    text = Column(
        Unicode,
        nullable=False)

    # Contest (id and object) owning the announcement.
    contest_id = Column(
        Integer,
        ForeignKey(Contest.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    contest = relationship(
        Contest,
        back_populates="announcements")
