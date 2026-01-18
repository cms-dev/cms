#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2015 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
# Copyright © 2016 Amir Keivan Mohtashami <akmohtashami97@gmail.com>
# Copyright © 2017-2026 Tobias Lenz <t_lenz94@web.de>
# Copyright © 2018 William Di Luigi <williamdiluigi@gmail.com>
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

from datetime import datetime, timedelta

from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.orderinglist import ordering_list
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Column, ForeignKey, CheckConstraint
from sqlalchemy.types import Integer, Unicode, DateTime, Interval, Enum, \
    Boolean, String

from cms import TOKEN_MODE_DISABLED, TOKEN_MODE_FINITE, TOKEN_MODE_INFINITE
from . import Codename, Base, Admin
import typing
if typing.TYPE_CHECKING:
    from . import Task, Participation


class Contest(Base):
    """Class to store a contest (which is a single day of a
    programming competition).

    """
    __tablename__ = 'contests'
    __table_args__ = (
        CheckConstraint("token_gen_initial <= token_gen_max"),
    )

    # Auto increment primary key.
    id: int = Column(
        Integer,
        primary_key=True)

    # Short name of the contest.
    name: str = Column(
        Codename,
        nullable=False,
        unique=True)
    # Description of the contest (human readable).
    description: str = Column(
        Unicode,
        nullable=False)

    # The list of language codes of the localizations that contestants
    # are allowed to use (empty means all).
    allowed_localizations: list[str] = Column(
        ARRAY(String),
        nullable=False,
        default=[])

    # The list of names of languages allowed in the contest.
    languages: list[str] = Column(
        ARRAY(String),
        nullable=False,
        default=["C11 / gcc", "C++20 / g++", "Pascal / fpc"])

    # Whether contestants allowed to download their submissions.
    submissions_download_allowed: bool = Column(
        Boolean,
        nullable=False,
        default=True)

    # Whether the user question is enabled.
    allow_questions: bool = Column(
        Boolean,
        nullable=False,
        default=True)

    # Whether the user test interface is enabled.
    allow_user_tests: bool = Column(
        Boolean,
        nullable=False,
        default=True)

    # Allow unofficial submission before analysis mode
    allow_unofficial_submission_before_analysis_mode = Column(
        Boolean,
        nullable=False,
        default=False)

    # Whether to prevent hidden participations to log in.
    block_hidden_participations: bool = Column(
        Boolean,
        nullable=False,
        default=False)

    # Whether to allow username/password authentication
    allow_password_authentication: bool = Column(
        Boolean,
        nullable=False,
        default=True)

    # Whether the registration of new users is enabled.
    allow_registration: bool = Column(
        Boolean,
        nullable=False,
        default=False)

    # Whether to enforce that the IP address of the request matches
    # the IP address or subnet specified for the participation (if
    # present).
    ip_restriction: bool = Column(
        Boolean,
        nullable=False,
        default=True)

    # Whether to automatically log in users connecting from an IP
    # address specified in the ip field of a participation to this
    # contest.
    ip_autologin: bool = Column(
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
    token_mode: str = Column(
        Enum(TOKEN_MODE_DISABLED, TOKEN_MODE_FINITE, TOKEN_MODE_INFINITE,
             name="token_mode"),
        nullable=False,
        default=TOKEN_MODE_INFINITE)

    # The maximum number of tokens a contestant is allowed to use
    # during the whole contest (on all tasks).
    token_max_number: int | None = Column(
        Integer,
        CheckConstraint("token_max_number > 0"),
        nullable=True)

    # The minimum interval between two successive uses of tokens for
    # the same user (on any task).
    token_min_interval: timedelta = Column(
        Interval,
        CheckConstraint("token_min_interval >= '0 seconds'"),
        nullable=False,
        default=timedelta())

    # The parameters that control generation (if mode is "finite"):
    # the user starts with "initial" tokens and receives "number" more
    # every "interval", but their total number is capped to "max".
    token_gen_initial: int = Column(
        Integer,
        CheckConstraint("token_gen_initial >= 0"),
        nullable=False,
        default=2)
    token_gen_number: int = Column(
        Integer,
        CheckConstraint("token_gen_number >= 0"),
        nullable=False,
        default=2)
    token_gen_interval: timedelta = Column(
        Interval,
        CheckConstraint("token_gen_interval > '0 seconds'"),
        nullable=False,
        default=timedelta(minutes=30))
    token_gen_max: int | None = Column(
        Integer,
        CheckConstraint("token_gen_max > 0"),
        nullable=True)

    # Timezone for the contest. All timestamps in CWS will be shown
    # using the timezone associated to the logged-in user or (if it's
    # None or an invalid string) the timezone associated to the
    # contest or (if it's None or an invalid string) the local
    # timezone of the server. This value has to be a string like
    # "Europe/Rome", "Australia/Sydney", "America/New_York", etc.
    timezone: str | None = Column(
        Unicode,
        nullable=True)

    # Max contest time for each user in seconds.
    per_user_time: timedelta | None = Column(
        Interval,
        CheckConstraint("per_user_time >= '0 seconds'"),
        nullable=True)

    # Maximum number of submissions or user_tests allowed for each user
    # during the whole contest or None to not enforce this limitation.
    max_submission_number: int | None = Column(
        Integer,
        CheckConstraint("max_submission_number > 0"),
        nullable=True)
    max_user_test_number: int | None = Column(
        Integer,
        CheckConstraint("max_user_test_number > 0"),
        nullable=True)

    # Minimum interval between two submissions or user_tests, or None to
    # not enforce this limitation.
    min_submission_interval: timedelta | None = Column(
        Interval,
        CheckConstraint("min_submission_interval > '0 seconds'"),
        nullable=True)
    min_submission_interval_grace_period: timedelta | None = Column(
        Interval,
        CheckConstraint("min_submission_interval_grace_period > '0 seconds'"),
        nullable=True)
    min_user_test_interval: timedelta | None = Column(
        Interval,
        CheckConstraint("min_user_test_interval > '0 seconds'"),
        nullable=True)

    # The scores for this contest will be rounded to this number of
    # decimal places.
    score_precision: int = Column(
        Integer,
        CheckConstraint("score_precision >= 0"),
        nullable=False,
        default=0)

    # Main group (id and Group object) of this contest
    main_group_id: int = Column(
        Integer,
        ForeignKey("group.id", use_alter=True, name="fk_contest_main_group_id",
                   onupdate="CASCADE", ondelete="SET NULL"),
        index=True)
    main_group = relationship(
        "Group",
        primaryjoin="Group.id==Contest.main_group_id",
        post_update=True)

    # Follows the description of the fields automatically added by
    # SQLAlchemy.
    # groups (list of Group objects)
    # These one-to-many relationships are the reversed directions of
    # the ones defined in the "child" classes using foreign keys.

    tasks: list["Task"] = relationship(
        "Task",
        collection_class=ordering_list("num"),
        order_by="[Task.num]",
        cascade="all",
        passive_deletes=True,
        back_populates="contest")

    announcements: list["Announcement"] = relationship(
        "Announcement",
        order_by="[Announcement.timestamp]",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="contest")

    participations: list["Participation"] = relationship(
        "Participation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="contest")


class Announcement(Base):
    """Class to store a messages sent by the contest managers to all
    the users.

    """
    __tablename__ = 'announcements'

    # Auto increment primary key.
    id: int = Column(
        Integer,
        primary_key=True)

    # Time, subject and text of the announcement.
    timestamp: datetime = Column(
        DateTime,
        nullable=False)
    subject: str = Column(
        Unicode,
        nullable=False)
    text: str = Column(
        Unicode,
        nullable=False)

    # Contest (id and object) owning the announcement.
    contest_id: int = Column(
        Integer,
        ForeignKey(Contest.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    contest: Contest = relationship(
        Contest,
        back_populates="announcements")

    # Admin that created the announcement (or null if the admin has been
    # later deleted). Admins only loosely "own" an announcement, so we do not
    # back populate any field in Admin, nor delete the announcement if the
    # admin gets deleted.
    admin_id: int | None = Column(
        Integer,
        ForeignKey(Admin.id,
                   onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
        index=True)
    admin: Admin | None = relationship(Admin)
