#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2014 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
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

"""Task-related database interface for SQLAlchemy.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from datetime import timedelta

from sqlalchemy.schema import Column, ForeignKey, CheckConstraint, \
    UniqueConstraint, ForeignKeyConstraint
from sqlalchemy.types import Boolean, Integer, Float, String, Unicode, \
    Interval, Enum
from sqlalchemy.orm import backref, relationship
from sqlalchemy.ext.orderinglist import ordering_list

from . import Base, Contest
from .smartmappedcollection import smart_mapped_collection, smc_sa10_workaround
from cms import SCORE_MODE_MAX, SCORE_MODE_MAX_TOKENED_LAST


class Task(Base):
    """Class to store a task.

    """
    __tablename__ = 'tasks'
    __table_args__ = (
        UniqueConstraint('contest_id', 'num'),
        UniqueConstraint('contest_id', 'name'),
        ForeignKeyConstraint(
            ("id", "active_dataset_id"),
            ("datasets.task_id", "datasets.id"),
            onupdate="SET NULL", ondelete="SET NULL",
            # Use an ALTER query to set this foreign key after
            # both tables have been CREATEd, to avoid circular
            # dependencies.
            use_alter=True,
            name="fk_active_dataset_id"
        ),
        ForeignKeyConstraint(
            ("id", "visualization_dataset_id"),
            ("datasets.task_id", "datasets.id"),
            onupdate="SET NULL", ondelete="SET NULL",
            # Use an ALTER query to set this foreign key after
            # both tables have been CREATEd, to avoid circular
            # dependencies.
            use_alter=True,
            name="fk_visualization_dataset_id"
        ),
        CheckConstraint("token_gen_initial <= token_gen_max"),
    )

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True,
        # Needed to enable autoincrement on integer primary keys that
        # are referenced by a foreign key defined on this table.
        autoincrement='ignore_fk')

    # Number of the task for sorting.
    num = Column(
        Integer,
        nullable=True)

    # Contest (id and object) owning the task.
    contest_id = Column(
        Integer,
        ForeignKey(Contest.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=True,
        index=True)
    contest = relationship(
        Contest,
        backref=backref('tasks',
                        collection_class=ordering_list('num'),
                        order_by=[num],
                        cascade="all",
                        passive_deletes=True))

    # Short name and long human readable title of the task.
    name = Column(
        Unicode,
        nullable=False,
        unique=True)
    title = Column(
        Unicode,
        nullable=False)

    # A JSON-encoded lists of strings: the language codes of the
    # statements that will be highlighted to all users for this task.
    primary_statements = Column(
        String,
        nullable=False,
        default="[]")

    # The parameters that control task-tokens follow. Note that their
    # effect during the contest depends on the interaction with the
    # parameters that control contest-tokens, defined on the Contest.

    # The "kind" of token rules that will be active during the contest.
    # - disabled: The user will never be able to use any token.
    # - finite: The user has a finite amount of tokens and can choose
    #   when to use them, subject to some limitations. Tokens may not
    #   be all available at start, but given periodically during the
    #   contest instead.
    # - infinite: The user will always be able to use a token.
    token_mode = Column(
        Enum("disabled", "finite", "infinite", name="token_mode"),
        nullable=False,
        default="disabled")

    # The maximum number of tokens a contestant is allowed to use
    # during the whole contest (on this tasks).
    token_max_number = Column(
        Integer,
        CheckConstraint("token_max_number > 0"),
        nullable=True)

    # The minimum interval between two successive uses of tokens for
    # the same user (on this task).
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

    # Maximum number of submissions or user_tests allowed for each user
    # on this task during the whole contest or None to not enforce
    # this limitation.
    max_submission_number = Column(
        Integer,
        CheckConstraint("max_submission_number > 0"),
        nullable=True)
    max_user_test_number = Column(
        Integer,
        CheckConstraint("max_user_test_number > 0"),
        nullable=True)

    # Minimum interval between two submissions or user_tests for this
    # task, or None to not enforce this limitation.
    min_submission_interval = Column(
        Interval,
        CheckConstraint("min_submission_interval > '0 seconds'"),
        nullable=True)
    min_user_test_interval = Column(
        Interval,
        CheckConstraint("min_user_test_interval > '0 seconds'"),
        nullable=True)

    # The scores for this task will be rounded to this number of
    # decimal places.
    score_precision = Column(
        Integer,
        CheckConstraint("score_precision >= 0"),
        nullable=False,
        default=0)

    # Score mode for the task.
    score_mode = Column(
        Enum(SCORE_MODE_MAX_TOKENED_LAST, SCORE_MODE_MAX,
             name="score_mode"),
        nullable=False,
        default=SCORE_MODE_MAX_TOKENED_LAST)

    # Active Dataset (id and object) currently being used for scoring.
    # The ForeignKeyConstraint for this column is set at table-level.
    active_dataset_id = Column(
        Integer,
        nullable=True)
    active_dataset = relationship(
        'Dataset',
        foreign_keys=[active_dataset_id],
        # Use an UPDATE query *after* an INSERT query (and *before* a
        # DELETE query) to set (and unset) the column associated to
        # this relationship.
        post_update=True)

    # Visualization Dataset (id and object) used.
    # The ForeignKeyConstraint for this column is set at table-level.
    visualization_dataset_id = Column(
        Integer,
        nullable=True)
    visualization_dataset = relationship(
        'Dataset',
        foreign_keys=[visualization_dataset_id],
        # XXX In SQLAlchemy 0.8 we could remove this:
        primaryjoin='Task.visualization_dataset_id == Dataset.id',
        # Use an UPDATE query *after* an INSERT query (and *before* a
        # DELETE query) to set (and unset) the column associated to
        # this relationship.
        post_update=True)

    # Visualization script used.
    visualization_script = Column(
        String,
        nullable=True)

    # Follows the description of the fields automatically added by
    # SQLAlchemy.
    # datasets (list of Dataset objects)
    # statements (dict of Statement objects indexed by language code)
    # attachments (dict of Attachment objects indexed by filename)
    # submission_format (list of SubmissionFormatElement objects)
    # submissions (list of Submission objects)
    # user_tests (list of UserTest objects)


class Statement(Base):
    """Class to store a translation of the task statement.

    """
    __tablename__ = 'statements'
    __table_args__ = (
        UniqueConstraint('task_id', 'language'),
    )

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # Task (id and object) the statement is for.
    task_id = Column(
        Integer,
        ForeignKey(Task.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    task = smc_sa10_workaround(relationship(
        Task,
        backref=backref('statements',
                        collection_class=smart_mapped_collection('language'),
                        cascade="all, delete-orphan",
                        passive_deletes=True)))

    # Code for the language the statement is written in.
    # It can be an arbitrary string, but if it's in the form "en" or "en_US"
    # it will be rendered appropriately on the interface (i.e. "English" and
    # "English (United States of America)"). These codes need to be taken from
    # ISO 639-1 and ISO 3166-1 respectively.
    language = Column(
        Unicode,
        nullable=False)

    # Digest of the file.
    digest = Column(
        String,
        nullable=False)


class Attachment(Base):
    """Class to store additional files to give to the user together
    with the statement of the task.

    """
    __tablename__ = 'attachments'
    __table_args__ = (
        UniqueConstraint('task_id', 'filename'),
    )

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # Task (id and object) owning the attachment.
    task_id = Column(
        Integer,
        ForeignKey(Task.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    task = smc_sa10_workaround(relationship(
        Task,
        backref=backref('attachments',
                        collection_class=smart_mapped_collection('filename'),
                        cascade="all, delete-orphan",
                        passive_deletes=True)))

    # Filename and digest of the provided attachment.
    filename = Column(
        Unicode,
        nullable=False)
    digest = Column(
        String,
        nullable=False)


class SubmissionFormatElement(Base):
    """Class to store the requested files that a submission must
    include. Filenames may include %l to represent an accepted
    language extension.

    """
    __tablename__ = 'submission_format_elements'

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # Task (id and object) owning the submission format element.
    task_id = Column(
        Integer,
        ForeignKey(Task.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    task = relationship(
        Task,
        backref=backref('submission_format',
                        cascade="all, delete-orphan",
                        passive_deletes=True))

    # Format of the given submission file.
    filename = Column(
        Unicode,
        nullable=False)


class Dataset(Base):
    """Class to store the information about a data set.

    """
    __tablename__ = 'datasets'
    __table_args__ = (
        UniqueConstraint('task_id', 'description'),
        # Useless, in theory, because 'id' is already unique. Yet, we
        # need this because it's a target of a foreign key.
        UniqueConstraint('id', 'task_id'),
    )

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # Task (id and object) owning the dataset.
    task_id = Column(
        Integer,
        ForeignKey(Task.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False)
    task = relationship(
        Task,
        foreign_keys=[task_id],
        backref=backref('datasets',
                        cascade="all, delete-orphan",
                        passive_deletes=True))

    # A human-readable text describing the dataset.
    description = Column(
        Unicode,
        nullable=False)

    # Whether this dataset will be automatically judged by ES and SS
    # "in background", together with the active dataset of each task.
    autojudge = Column(
        Boolean,
        nullable=False,
        default=False)

    # Time and memory limits for every testcase.
    time_limit = Column(
        Float,
        nullable=True)
    memory_limit = Column(
        Integer,
        nullable=True)

    # Name of the TaskType child class suited for the task.
    task_type = Column(
        String,
        nullable=False)

    # Parameters for the task type class, JSON encoded.
    task_type_parameters = Column(
        String,
        nullable=False)

    # Name of the ScoreType child class suited for the task.
    score_type = Column(
        String,
        nullable=False)

    # Parameters for the score type class, JSON encoded.
    score_type_parameters = Column(
        String,
        nullable=False)

    # Follows the description of the fields automatically added by
    # SQLAlchemy.
    # managers (dict of Manager objects indexed by filename)
    # testcases (dict of Testcase objects indexed by codename)

    @property
    def active(self):
        """Shorthand for detecting if the dataset is active.

        return (bool): True if this dataset is the active one for its
            task.

        """
        return self is self.task.active_dataset

    @property
    def visualized(self):
        """Shorthand for detecting if the dataset is the one visualized.

        return (bool): True if this dataset is the one for the visualization
            of its task.

        """
        return self is self.task.visualization_dataset

    def clone_from(self, old_dataset, clone_managers=True,
                   clone_testcases=True, clone_results=False):
        """Overwrite the data with that in dataset.

        old_dataset (Dataset): original dataset to copy from.
        clone_managers (bool): copy dataset managers.
        clone_testcases (bool): copy dataset testcases.
        clone_results (bool): copy submission results (will also copy
            managers and testcases).

        """
        new_testcases = dict()
        if clone_testcases or clone_results:
            for old_t in old_dataset.testcases.itervalues():
                new_t = old_t.clone()
                new_t.dataset = self
                new_testcases[new_t.codename] = new_t

        if clone_managers or clone_results:
            for old_m in old_dataset.managers.itervalues():
                new_m = old_m.clone()
                new_m.dataset = self

        # TODO: why is this needed?
        self.sa_session.flush()

        if clone_results:
            old_results = self.get_submission_results(old_dataset)

            for old_sr in old_results:
                # Create the submission result.
                new_sr = old_sr.clone()
                new_sr.submission = old_sr.submission
                new_sr.dataset = self

                # Create executables.
                for old_e in old_sr.executables.itervalues():
                    new_e = old_e.clone()
                    new_e.submission_result = new_sr

                # Create evaluations.
                for old_e in old_sr.evaluations:
                    new_e = old_e.clone()
                    new_e.submission_result = new_sr
                    new_e.testcase = new_testcases[old_e.codename]

        self.sa_session.flush()


class Manager(Base):
    """Class to store additional files needed to compile or evaluate a
    submission (e.g., graders).

    """
    __tablename__ = 'managers'
    __table_args__ = (
        UniqueConstraint('dataset_id', 'filename'),
    )

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # Dataset (id and object) owning the manager.
    dataset_id = Column(
        Integer,
        ForeignKey(Dataset.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    dataset = smc_sa10_workaround(relationship(
        Dataset,
        backref=backref('managers',
                        collection_class=smart_mapped_collection('filename'),
                        cascade="all, delete-orphan",
                        passive_deletes=True)))

    # Filename and digest of the provided manager.
    filename = Column(
        Unicode,
        nullable=False)
    digest = Column(
        String,
        nullable=False)


class Testcase(Base):
    """Class to store the information about a testcase.

    """
    __tablename__ = 'testcases'
    __table_args__ = (
        UniqueConstraint('dataset_id', 'codename'),
    )

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # Dataset (id and object) owning the testcase.
    dataset_id = Column(
        Integer,
        ForeignKey(Dataset.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    dataset = smc_sa10_workaround(relationship(
        Dataset,
        backref=backref('testcases',
                        collection_class=smart_mapped_collection('codename'),
                        cascade="all, delete-orphan",
                        passive_deletes=True)))

    # Codename identifying the testcase.
    codename = Column(
        Unicode,
        nullable=False)

    # If the testcase outcome is going to be showed to the user (even
    # without playing a token).
    public = Column(
        Boolean,
        nullable=False,
        default=False)

    # Digests of the input and output files.
    input = Column(
        String,
        nullable=False)
    output = Column(
        String,
        nullable=False)
