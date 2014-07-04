#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2012-2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""UserTest-related database interface for SQLAlchemy.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from sqlalchemy.schema import Column, ForeignKey, ForeignKeyConstraint, \
    UniqueConstraint
from sqlalchemy.types import Integer, Float, String, Unicode, DateTime
from sqlalchemy.orm import relationship, backref

from . import Base, User, Task, Dataset
from .smartmappedcollection import smart_mapped_collection


class UserTest(Base):
    """Class to store a test requested by a user.

    """
    __tablename__ = 'user_tests'

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # User (id and object) that requested the test.
    user_id = Column(
        Integer,
        ForeignKey(User.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    user = relationship(
        User,
        backref=backref("user_tests",
                        cascade="all, delete-orphan",
                        passive_deletes=True))

    # Task (id and object) of the test.
    task_id = Column(
        Integer,
        ForeignKey(Task.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    task = relationship(
        Task,
        backref=backref("user_tests",
                        cascade="all, delete-orphan",
                        passive_deletes=True))

    # Time of the request.
    timestamp = Column(
        DateTime,
        nullable=False)

    # Language of test, or None if not applicable.
    language = Column(
        String,
        nullable=True)

    # Input (provided by the user) file's digest for this test.
    input = Column(
        String,
        nullable=False)

    # Follows the description of the fields automatically added by
    # SQLAlchemy.
    # files (dict of UserTestFile objects indexed by filename)
    # managers (dict of UserTestManager objects indexed by filename)
    # results (list of UserTestResult objects)

    def get_result(self, dataset=None):
        """Return the result associated to a dataset.

        dataset (Dataset|None): the dataset for which the caller wants
            the user test result; if None, the active one is used.

        return (UserTestResult|None): the user test result associated
            to this user test and the given dataset, if it exists in
            the database, otherwise None.

        """
        if dataset is not None:
            # Use IDs to avoid triggering a lazy-load query.
            assert self.task_id == dataset.task_id
            dataset_id = dataset.id
        else:
            dataset_id = self.task.active_dataset_id

        return UserTestResult.get_from_id(
            (self.id, dataset_id), self.sa_session)

    def get_result_or_create(self, dataset=None):
        """Return and, if necessary, create the result for a dataset.

        dataset (Dataset|None): the dataset for which the caller wants
            the user test result; if None, the active one is used.

        return (UserTestResult): the user test result associated to
            the this user test and the given dataset; if it does not
            exists, a new one is created.

        """
        if dataset is None:
            dataset = self.task.active_dataset

        user_test_result = self.get_result(dataset)

        if user_test_result is None:
            user_test_result = UserTestResult(user_test=self,
                                              dataset=dataset)

        return user_test_result


class UserTestFile(Base):
    """Class to store information about one file submitted within a
    user_test.

    """
    __tablename__ = 'user_test_files'
    __table_args__ = (
        UniqueConstraint('user_test_id', 'filename'),
    )

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # UserTest (id and object) owning the file.
    user_test_id = Column(
        Integer,
        ForeignKey(UserTest.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    user_test = relationship(
        UserTest,
        backref=backref('files',
                        collection_class=smart_mapped_collection('filename'),
                        cascade="all, delete-orphan",
                        passive_deletes=True))

    # Filename and digest of the submitted file.
    filename = Column(
        String,
        nullable=False)
    digest = Column(
        String,
        nullable=False)


class UserTestManager(Base):
    """Class to store additional files needed to compile or evaluate a
    user test (e.g., graders).

    """
    __tablename__ = 'user_test_managers'
    __table_args__ = (
        UniqueConstraint('user_test_id', 'filename'),
    )

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # UserTest (id and object) owning the manager.
    user_test_id = Column(
        Integer,
        ForeignKey(UserTest.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    user_test = relationship(
        UserTest,
        backref=backref('managers',
                        collection_class=smart_mapped_collection('filename'),
                        cascade="all, delete-orphan",
                        passive_deletes=True))

    # Filename and digest of the submitted manager.
    filename = Column(
        String,
        nullable=False)
    digest = Column(
        String,
        nullable=False)


class UserTestResult(Base):
    """Class to store the execution results of a user_test.

    """
    __tablename__ = 'user_test_results'
    __table_args__ = (
        UniqueConstraint('user_test_id', 'dataset_id'),
    )

    # Primary key is (user_test_id, dataset_id).
    user_test_id = Column(
        Integer,
        ForeignKey(UserTest.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        primary_key=True)
    user_test = relationship(
        UserTest,
        backref=backref(
            "results",
            cascade="all, delete-orphan",
            passive_deletes=True))

    dataset_id = Column(
        Integer,
        ForeignKey(Dataset.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        primary_key=True)
    dataset = relationship(
        Dataset)

    # Now below follow the actual result fields.

    # Output file's digest for this test
    output = Column(
        String,
        nullable=True)

    # Compilation outcome (can be None = yet to compile, "ok" =
    # compilation successful and we can evaluate, "fail" =
    # compilation unsuccessful, throw it away).
    compilation_outcome = Column(
        String,
        nullable=True)

    # String containing output from the sandbox.
    compilation_text = Column(
        String,
        nullable=True)

    # Number of attempts of compilation.
    compilation_tries = Column(
        Integer,
        nullable=False,
        default=0)

    # The compiler stdout and stderr.
    compilation_stdout = Column(
        Unicode,
        nullable=True)
    compilation_stderr = Column(
        Unicode,
        nullable=True)

    # Other information about the compilation.
    compilation_time = Column(
        Float,
        nullable=True)
    compilation_wall_clock_time = Column(
        Float,
        nullable=True)
    compilation_memory = Column(
        Integer,
        nullable=True)

    # Worker shard and sandbox where the compilation was performed.
    compilation_shard = Column(
        Integer,
        nullable=True)
    compilation_sandbox = Column(
        String,
        nullable=True)

    # Evaluation outcome (can be None = yet to evaluate, "ok" =
    # evaluation successful).
    evaluation_outcome = Column(
        String,
        nullable=True)
    evaluation_text = Column(
        String,
        nullable=True)

    # Number of attempts of evaluation.
    evaluation_tries = Column(
        Integer,
        nullable=False,
        default=0)

    # Other information about the execution.
    execution_time = Column(
        Float,
        nullable=True)
    execution_wall_clock_time = Column(
        Float,
        nullable=True)
    execution_memory = Column(
        Integer,
        nullable=True)

    # Worker shard and sandbox where the evaluation was performed.
    evaluation_shard = Column(
        Integer,
        nullable=True)
    evaluation_sandbox = Column(
        String,
        nullable=True)

    # Follows the description of the fields automatically added by
    # SQLAlchemy.
    # executables (dict of UserTestExecutable objects indexed by filename)

    def compiled(self):
        """Return whether the user test result has been compiled.

        return (bool): True if compiled, False otherwise.

        """
        return self.compilation_outcome is not None

    def compilation_failed(self):
        """Return whether the user test result did not compile.

        return (bool): True if the compilation failed (in the sense
            that there is a problem in the user's source), False if
            not yet compiled or compilation was successful.

        """
        return self.compilation_outcome == "fail"

    def compilation_succeeded(self):
        """Return whether the user test compiled.

        return (bool): True if the compilation succeeded (in the sense
            that an executable was created), False if not yet compiled
            or compilation was unsuccessful.

        """
        return self.compilation_outcome == "ok"

    def evaluated(self):
        """Return whether the user test result has been evaluated.

        return (bool): True if evaluated, False otherwise.

        """
        return self.evaluation_outcome is not None

    def invalidate_compilation(self):
        """Blank all compilation and evaluation outcomes.

        """
        self.invalidate_evaluation()
        self.compilation_outcome = None
        self.compilation_text = None
        self.compilation_tries = 0
        self.compilation_time = None
        self.compilation_wall_clock_time = None
        self.compilation_memory = None
        self.compilation_shard = None
        self.compilation_sandbox = None
        self.executables = {}

    def invalidate_evaluation(self):
        """Blank the evaluation outcome.

        """
        self.evaluation_outcome = None
        self.evaluation_text = None
        self.evaluation_tries = 0
        self.execution_time = None
        self.execution_wall_clock_time = None
        self.execution_memory = None
        self.evaluation_shard = None
        self.evaluation_sandbox = None
        self.output = None

    def set_compilation_outcome(self, success):
        """Set the compilation outcome based on the success.

        success (bool): if the compilation was successful.

        """
        self.compilation_outcome = "ok" if success else "fail"

    def set_evaluation_outcome(self):
        """Set the evaluation outcome (always ok now).

        """
        self.evaluation_outcome = "ok"


class UserTestExecutable(Base):
    """Class to store information about one file generated by the
    compilation of a user test.

    """
    __tablename__ = 'user_test_executables'
    __table_args__ = (
        ForeignKeyConstraint(
            ('user_test_id', 'dataset_id'),
            (UserTestResult.user_test_id, UserTestResult.dataset_id),
            onupdate="CASCADE", ondelete="CASCADE"),
        UniqueConstraint('user_test_id', 'dataset_id', 'filename'),
    )

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # UserTest (id and object) owning the executable.
    user_test_id = Column(
        Integer,
        ForeignKey(UserTest.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    user_test = relationship(
        UserTest)

    # Dataset (id and object) owning the executable.
    dataset_id = Column(
        Integer,
        ForeignKey(Dataset.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    dataset = relationship(
        Dataset)

    # UserTestResult owning the executable.
    user_test_result = relationship(
        UserTestResult,
        backref=backref('executables',
                        collection_class=smart_mapped_collection('filename'),
                        cascade="all, delete-orphan",
                        passive_deletes=True))

    # Filename and digest of the generated executable.
    filename = Column(
        String,
        nullable=False)
    digest = Column(
        String,
        nullable=False)
