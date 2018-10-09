#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2015 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
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

from datetime import timedelta

from sqlalchemy.dialects.postgresql import ARRAY, CIDR
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Column, ForeignKey, CheckConstraint, \
    UniqueConstraint
from sqlalchemy.types import Boolean, Integer, String, Unicode, DateTime, \
    Interval

from cmscommon.crypto import generate_random_password, build_password
from . import CastingArray, Codename, Base, Admin, Contest


class User(Base):
    """Class to store a user.

    """

    __tablename__ = 'users'

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
        Codename,
        nullable=False,
        unique=True)
    password = Column(
        Unicode,
        nullable=False,
        default=lambda: build_password(generate_random_password()))

    # Email for any communications in case of remote contest.
    email = Column(
        Unicode,
        nullable=True)

    # Timezone for the user. All timestamps in CWS will be shown using
    # the timezone associated to the logged-in user or (if it's None
    # or an invalid string) the timezone associated to the contest or
    # (if it's None or an invalid string) the local timezone of the
    # server. This value has to be a string like "Europe/Rome",
    # "Australia/Sydney", "America/New_York", etc.
    timezone = Column(
        Unicode,
        nullable=True)

    # The language codes accepted by this user (from the "most
    # preferred" to the "least preferred"). If in a contest there is a
    # statement available in some of these languages, then the most
    # preferred of them will be highlighted.
    # FIXME: possibly move it to Participation and change it back to
    # primary_statements
    preferred_languages = Column(
        ARRAY(String),
        nullable=False,
        default=[])

    # These one-to-many relationships are the reversed directions of
    # the ones defined in the "child" classes using foreign keys.

    participations = relationship(
        "Participation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="user")


class Team(Base):
    """Class to store a team.

    A team is a way of grouping the users participating in a contest.
    This grouping has no effect on the contest itself; it is only used
    for display purposes in RWS.

    """

    __tablename__ = 'teams'

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # Team code (e.g. the ISO 3166-1 code of a country)
    code = Column(
        Codename,
        nullable=False,
        unique=True)

    # Human readable team name (e.g. the ISO 3166-1 short name of a country)
    name = Column(
        Unicode,
        nullable=False)

    participations = relationship(
        "Participation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="team")

    # TODO: decide if the flag images will eventually be stored here.
    # TODO: (hopefully, the same will apply for faces in User).


class Participation(Base):
    """Class to store a single participation of a user in a contest.

    """
    __tablename__ = 'participations'

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # If the IP lock is enabled the user can log into CWS only if their
    # requests come from an IP address that belongs to any of these
    # subnetworks. An empty list prevents the user from logging in,
    # None disables the IP lock for the user.
    ip = Column(
        CastingArray(CIDR),
        nullable=True)

    # Starting time: for contests where every user has at most x hours
    # of the y > x hours totally available, this is the time the user
    # decided to start their time-frame.
    starting_time = Column(
        DateTime,
        nullable=True)

    # A shift in the time interval during which the user is allowed to
    # submit.
    delay_time = Column(
        Interval,
        CheckConstraint("delay_time >= '0 seconds'"),
        nullable=False,
        default=timedelta())

    # An extra amount of time allocated for this user.
    extra_time = Column(
        Interval,
        CheckConstraint("extra_time >= '0 seconds'"),
        nullable=False,
        default=timedelta())

    # Contest-specific password. If this password is not null then the
    # traditional user.password field will be "replaced" by this field's
    # value (only for this participation).
    password = Column(
        Unicode,
        nullable=True)

    # A hidden participation (e.g. does not appear in public rankings), can
    # also be used for debugging purposes.
    hidden = Column(
        Boolean,
        nullable=False,
        default=False)

    # An unrestricted participation (e.g. contest time,
    # maximum number of submissions, minimum interval between submissions,
    # maximum number of user tests, minimum interval between user tests),
    # can also be used for debugging purposes.
    unrestricted = Column(
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
        back_populates="participations")

    # User (id and object) which is participating.
    user_id = Column(
        Integer,
        ForeignKey(User.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    user = relationship(
        User,
        back_populates="participations")
    __table_args__ = (UniqueConstraint('contest_id', 'user_id'),)

    # Team (id and object) that the user is representing with this
    # participation.
    team_id = Column(
        Integer,
        ForeignKey(Team.id,
                   onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=True)
    team = relationship(
        Team,
        back_populates="participations")

    # These one-to-many relationships are the reversed directions of
    # the ones defined in the "child" classes using foreign keys.

    messages = relationship(
        "Message",
        order_by="[Message.timestamp]",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="participation")

    questions = relationship(
        "Question",
        order_by="[Question.question_timestamp, Question.reply_timestamp]",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="participation")

    submissions = relationship(
        "Submission",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="participation")

    user_tests = relationship(
        "UserTest",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="participation")

    printjobs = relationship(
        "PrintJob",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="participation")


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

    # Participation (id and object) owning the message.
    participation_id = Column(
        Integer,
        ForeignKey(Participation.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    participation = relationship(
        Participation,
        back_populates="messages")

    # Admin that sent the message (or null if the admin has been later
    # deleted). Admins only loosely "own" a message, so we do not back
    # populate any field in Admin, nor we delete the message when the admin
    # gets deleted.
    admin_id = Column(
        Integer,
        ForeignKey(Admin.id,
                   onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
        index=True)
    admin = relationship(Admin)


class Question(Base):
    """Class to store a private question from the user to the
    managers, and its answer.

    """
    __tablename__ = 'questions'

    MAX_SUBJECT_LENGTH = 50
    MAX_TEXT_LENGTH = 2000

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

    # Participation (id and object) owning the question.
    participation_id = Column(
        Integer,
        ForeignKey(Participation.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    participation = relationship(
        Participation,
        back_populates="questions")

    # Latest admin to interact with the question (null if no interactions
    # yet, or if the admin has been later deleted). Admins only loosely "own" a
    # question, so we do not back populate any field in Admin, nor delete the
    # question if the admin gets deleted.
    admin_id = Column(
        Integer,
        ForeignKey(Admin.id,
                   onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
        index=True)
    admin = relationship(Admin)
