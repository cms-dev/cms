#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
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

"""UserTest-related database interface for SQLAlchemy. Not to be used
directly (import from SQLAlchemyAll).

"""

from sqlalchemy.schema import Column, ForeignKey, UniqueConstraint
from sqlalchemy.types import Integer, Float, String, DateTime
from sqlalchemy.orm import relationship, backref

from cms.db.SQLAlchemyUtils import Base
from cms.db.Task import Task
from cms.db.User import User
from cms.db.SmartMappedCollection import smart_mapped_collection

from cmscommon.DateTime import make_datetime, make_timestamp


class UserTest(Base):
    """Class to store a test requested by a user. Not to be used
    directly (import it from SQLAlchemyAll).

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

    # Input (provided by the user) and output files' digests for this
    # test.
    input = Column(
        String,
        nullable=False)
    output = Column(
        String,
        nullable=True)

    # Compilation outcome (can be None = yet to compile, "ok" =
    # compilation successful and we can evaluate, "fail" =
    # compilation unsuccessful, throw it away).
    compilation_outcome = Column(
        String,
        nullable=True)

    # String containing output from the sandbox, and the compiler
    # stdout and stderr.
    compilation_text = Column(
        String,
        nullable=True)

    # Number of attempts of compilation.
    compilation_tries = Column(
        Integer,
        nullable=False,
        default=0)

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

    # Worker shard and sandbox where the evaluation was performed.
    evaluation_shard = Column(
        Integer,
        nullable=True)
    evaluation_sandbox = Column(
        String,
        nullable=True)

    # Other information about the execution.
    memory_used = Column(
        Integer,
        nullable=True)
    execution_time = Column(
        Float,
        nullable=True)

    # Follows the description of the fields automatically added by
    # SQLAlchemy.
    # files (dict of UserTestFile objects indexed by filename)
    # executables (dict of UserTestExecutable objects indexed by filename)
    # managers (dict of UserTestManager objects indexed by filename)

    def compiled(self):
        """Return if the user test has been compiled.

        return (bool): True if compiled, False otherwise.

        """
        return self.compilation_outcome is not None

    def evaluated(self):
        """Return if the user test has been evaluated.

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
        self.compilation_shard = None
        self.compilation_sandbox = None
        self.executables = {}

    def invalidate_evaluation(self):
        """Blank the evaluation outcome.

        """
        self.evaluation_outcome = None
        self.evaluation_text = None
        self.evaluation_tries = 0
        self.evaluation_shard = None
        self.evaluation_sandbox = None
        self.output = None
        self.memory_used = None
        self.evaluation_time = None


class UserTestFile(Base):
    """Class to store information about one file submitted within a
    user_test. Not to be used directly (import it from SQLAlchemyAll).

    """
    __tablename__ = 'user_test_files'
    __table_args__ = (
        UniqueConstraint('user_test_id', 'filename',
                         name='cst_files_user_test_id_filename'),
    )

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # Filename and digest of the submitted file.
    filename = Column(
        String,
        nullable=False)
    digest = Column(
        String,
        nullable=False)

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


class UserTestExecutable(Base):
    """Class to store information about one file generated by the
    compilation of a user test. Not to be used directly (import it
    from SQLAlchemyAll).

    """
    __tablename__ = 'user_test_executables'
    __table_args__ = (
        UniqueConstraint('user_test_id', 'filename',
                         name='cst_executables_user_test_id_filename'),
    )

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # Filename and digest of the generated executable.
    filename = Column(
        String,
        nullable=False)
    digest = Column(
        String,
        nullable=False)

    # UserTest (id and object) owning the executable.
    user_test_id = Column(
        Integer,
        ForeignKey(UserTest.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    user_test = relationship(
        UserTest,
        backref=backref('executables',
                        collection_class=smart_mapped_collection('filename'),
                        cascade="all, delete-orphan",
                        passive_deletes=True))


class UserTestManager(Base):
    """Class to store additional files needed to compile or evaluate a
    user test (e.g., graders). Not to be used directly (import it from
    SQLAlchemyAll).

    """
    __tablename__ = 'user_test_managers'
    __table_args__ = (
        UniqueConstraint('user_test_id', 'filename',
                         name='cst_managers_user_test_id_filename'),
    )

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # Filename and digest of the submitted manager.
    filename = Column(
        String,
        nullable=False)
    digest = Column(
        String,
        nullable=False)

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
