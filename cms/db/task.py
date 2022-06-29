#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

import copy
from datetime import timedelta

from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.schema import Column, ForeignKey, CheckConstraint, \
    UniqueConstraint, ForeignKeyConstraint
from sqlalchemy.types import Boolean, Integer, Float, String, Unicode, \
    Interval, Enum, BigInteger

from cms import TOKEN_MODE_DISABLED, TOKEN_MODE_FINITE, TOKEN_MODE_INFINITE, \
    FEEDBACK_LEVEL_FULL, FEEDBACK_LEVEL_RESTRICTED
from cmscommon.constants import \
    SCORE_MODE_MAX, SCORE_MODE_MAX_SUBTASK, SCORE_MODE_MAX_TOKENED_LAST
from . import Codename, Filename, FilenameSchemaArray, Digest, Base, Contest


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
        back_populates="tasks")

    # Short name and long human readable title of the task.
    name = Column(
        Codename,
        nullable=False,
        unique=True)
    title = Column(
        Unicode,
        nullable=False)

    # The names of the files that the contestant needs to submit (with
    # language-specific extensions replaced by "%l").
    submission_format = Column(
        FilenameSchemaArray,
        nullable=False,
        default=[])
    
    # The list of names of languages allowed for this task.
    # None means no limit
    languages = Column(
        ARRAY(String),
        nullable=True,
        default=None)


    # The language codes of the statements that will be highlighted to
    # all users for this task.
    primary_statements = Column(
        ARRAY(String),
        nullable=False,
        default=[])

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
        Enum(TOKEN_MODE_DISABLED, TOKEN_MODE_FINITE, TOKEN_MODE_INFINITE,
             name="token_mode"),
        nullable=False,
        default=TOKEN_MODE_DISABLED)

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

    # What information users can see about the evaluations of their
    # submissions. Offering full information might help some users to
    # reverse engineer task data.
    feedback_level = Column(
        Enum(FEEDBACK_LEVEL_FULL, FEEDBACK_LEVEL_RESTRICTED,
             name="feedback_level"),
        nullable=False,
        default=FEEDBACK_LEVEL_RESTRICTED)

    # The scores for this task will be rounded to this number of
    # decimal places.
    score_precision = Column(
        Integer,
        CheckConstraint("score_precision >= 0"),
        nullable=False,
        default=0)

    # Score mode for the task.
    score_mode = Column(
        Enum(SCORE_MODE_MAX_TOKENED_LAST,
             SCORE_MODE_MAX,
             SCORE_MODE_MAX_SUBTASK,
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

    # These one-to-many relationships are the reversed directions of
    # the ones defined in the "child" classes using foreign keys.

    statements = relationship(
        "Statement",
        collection_class=attribute_mapped_collection("language"),
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="task")

    attachments = relationship(
        "Attachment",
        collection_class=attribute_mapped_collection("filename"),
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="task")

    datasets = relationship(
        "Dataset",
        # Due to active_dataset_id, SQLAlchemy cannot unambiguously
        # figure out by itself which foreign key to use.
        foreign_keys="[Dataset.task_id]",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="task")

    submissions = relationship(
        "Submission",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="task")

    user_tests = relationship(
        "UserTest",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="task")


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
    task = relationship(
        Task,
        back_populates="statements")

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
        Digest,
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
    task = relationship(
        Task,
        back_populates="attachments")

    # Filename and digest of the provided attachment.
    filename = Column(
        Filename,
        nullable=False)
    digest = Column(
        Digest,
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
        back_populates="datasets")

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

    # Time and memory limits (in seconds and bytes) for every testcase.
    time_limit = Column(
        Float,
        CheckConstraint("time_limit > 0"),
        nullable=True)
    memory_limit = Column(
        BigInteger,
        CheckConstraint("memory_limit > 0"),
        CheckConstraint("MOD(memory_limit, 1048576) = 0"),
        nullable=True)

    # Name of the TaskType child class suited for the task.
    task_type = Column(
        String,
        nullable=False)

    # Parameters for the task type class.
    task_type_parameters = Column(
        JSONB,
        nullable=False)

    # Name of the ScoreType child class suited for the task.
    score_type = Column(
        String,
        nullable=False)

    # Parameters for the score type class.
    score_type_parameters = Column(
        JSONB,
        nullable=False)

    # These one-to-many relationships are the reversed directions of
    # the ones defined in the "child" classes using foreign keys.

    managers = relationship(
        "Manager",
        collection_class=attribute_mapped_collection("filename"),
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="dataset")

    testcases = relationship(
        "Testcase",
        collection_class=attribute_mapped_collection("codename"),
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="dataset")

    @property
    def active(self):
        """Shorthand for detecting if the dataset is active.

        return (bool): True if this dataset is the active one for its
            task.

        """
        return self is self.task.active_dataset

    @property
    def task_type_object(self):
        if not hasattr(self, "_cached_task_type_object") \
                or self.task_type != self._cached_task_type \
                or (self.task_type_parameters
                    != self._cached_task_type_parameters):
            # Import late to avoid a circular dependency.
            from cms.grading.tasktypes import get_task_type
            # This can raise.
            self._cached_task_type_object = get_task_type(
                self.task_type, self.task_type_parameters)
            # If an exception is raised these updates don't take place:
            # that way, next time this property is accessed, we get a
            # cache miss again and the same exception is raised again.
            self._cached_task_type = self.task_type
            self._cached_task_type_parameters = \
                copy.deepcopy(self.task_type_parameters)
        return self._cached_task_type_object

    @property
    def score_type_object(self):
        public_testcases = {k: tc.public
                            for k, tc in self.testcases.items()}
        if not hasattr(self, "_cached_score_type_object") \
                or self.score_type != self._cached_score_type \
                or (self.score_type_parameters
                    != self._cached_score_type_parameters) \
                or public_testcases != self._cached_public_testcases:
            # Import late to avoid a circular dependency.
            from cms.grading.scoretypes import get_score_type
            # This can raise.
            self._cached_score_type_object = get_score_type(
                self.score_type, self.score_type_parameters, public_testcases)
            # If an exception is raised these updates don't take place:
            # that way, next time this property is accessed, we get a
            # cache miss again and the same exception is raised again.
            self._cached_score_type = self.score_type
            self._cached_score_type_parameters = \
                copy.deepcopy(self.score_type_parameters)
            self._cached_public_testcases = public_testcases
        return self._cached_score_type_object

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
            for old_t in old_dataset.testcases.values():
                new_t = old_t.clone()
                new_t.dataset = self
                new_testcases[new_t.codename] = new_t

        if clone_managers or clone_results:
            for old_m in old_dataset.managers.values():
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
                for old_e in old_sr.executables.values():
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
    dataset = relationship(
        Dataset,
        back_populates="managers")

    # Filename and digest of the provided manager.
    filename = Column(
        Filename,
        nullable=False)
    digest = Column(
        Digest,
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
    dataset = relationship(
        Dataset,
        back_populates="testcases")

    # Codename identifying the testcase.
    codename = Column(
        Codename,
        nullable=False)

    # If the testcase outcome is going to be showed to the user (even
    # without playing a token).
    public = Column(
        Boolean,
        nullable=False,
        default=False)

    # Digests of the input and output files.
    input = Column(
        Digest,
        nullable=False)
    output = Column(
        Digest,
        nullable=False)
