#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2012-2015 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2015-2016 Stefano Maggiolo <s.maggiolo@gmail.com>
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

from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.schema import Column, ForeignKey, ForeignKeyConstraint, \
    UniqueConstraint
from sqlalchemy.types import Integer, Float, String, Unicode, DateTime, \
    BigInteger

from . import Filename, FilenameSchema, Digest, Base, Participation, Task, \
    Dataset


class UserTest(Base):
    """Class to store a test requested by a user.

    """
    __tablename__ = 'user_tests'

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # User and Contest, thus Participation (id and object) that did the
    # submission.
    participation_id = Column(
        Integer,
        ForeignKey(Participation.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    participation = relationship(
        Participation,
        back_populates="user_tests")

    # Task (id and object) of the test.
    task_id = Column(
        Integer,
        ForeignKey(Task.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    task = relationship(
        Task,
        back_populates="user_tests")

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
        Digest,
        nullable=False)

    # These one-to-many relationships are the reversed directions of
    # the ones defined in the "child" classes using foreign keys.

    files = relationship(
        "UserTestFile",
        collection_class=attribute_mapped_collection("filename"),
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="user_test")

    managers = relationship(
        "UserTestManager",
        collection_class=attribute_mapped_collection("filename"),
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="user_test")

    results = relationship(
        "UserTestResult",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="user_test")

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
        back_populates="files")

    # Filename and digest of the submitted file.
    filename = Column(
        FilenameSchema,
        nullable=False)
    digest = Column(
        Digest,
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
        back_populates="managers")

    # Filename and digest of the submitted manager.
    filename = Column(
        Filename,
        nullable=False)
    digest = Column(
        Digest,
        nullable=False)


class UserTestResult(Base):
    """Class to store the execution results of a user_test.

    """
    # Possible statuses of a user test result. COMPILING and
    # EVALUATING do not necessarily imply we are going to schedule
    # compilation and run for these user test results: for
    # example, they might be for datasets not scheduled for
    # evaluation, or they might have passed the maximum number of
    # tries. If a user test result does not exists for a pair
    # (user test, dataset), its status can be implicitly assumed to
    # be COMPILING.
    COMPILING = 1
    COMPILATION_FAILED = 2
    EVALUATING = 3
    EVALUATED = 4

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
        back_populates="results")

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
        Digest,
        nullable=True)

    # Compilation outcome (can be None = yet to compile, "ok" =
    # compilation successful and we can evaluate, "fail" =
    # compilation unsuccessful, throw it away).
    compilation_outcome = Column(
        String,
        nullable=True)

    # The output from the sandbox (to allow localization the first item
    # of the list is a format string, possibly containing some "%s",
    # that will be filled in using the remaining items of the list).
    compilation_text = Column(
        ARRAY(String),
        nullable=False,
        default=[])

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
        BigInteger,
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

    # The output from the grader, usually "Correct", "Time limit", ...
    # (to allow localization the first item of the list is a format
    # string, possibly containing some "%s", that will be filled in
    # using the remaining items of the list).
    evaluation_text = Column(
        ARRAY(String),
        nullable=False,
        default=[])

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
        BigInteger,
        nullable=True)

    # Worker shard and sandbox where the evaluation was performed.
    evaluation_shard = Column(
        Integer,
        nullable=True)
    evaluation_sandbox = Column(
        String,
        nullable=True)

    # These one-to-many relationships are the reversed directions of
    # the ones defined in the "child" classes using foreign keys.

    executables = relationship(
        "UserTestExecutable",
        collection_class=attribute_mapped_collection("filename"),
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="user_test_result")

    def get_status(self):
        """Return the status of this object.

        """
        if not self.compiled():
            return UserTestResult.COMPILING
        elif self.compilation_failed():
            return UserTestResult.COMPILATION_FAILED
        elif not self.evaluated():
            return UserTestResult.EVALUATING
        else:
            return UserTestResult.EVALUATED

    def compiled(self):
        """Return whether the user test result has been compiled.

        return (bool): True if compiled, False otherwise.

        """
        return self.compilation_outcome is not None

    @staticmethod
    def filter_compiled():
        """Return a filtering expression for compiled user test results.

        """
        return UserTestResult.compilation_outcome.isnot(None)

    def compilation_failed(self):
        """Return whether the user test result did not compile.

        return (bool): True if the compilation failed (in the sense
            that there is a problem in the user's source), False if
            not yet compiled or compilation was successful.

        """
        return self.compilation_outcome == "fail"

    @staticmethod
    def filter_compilation_failed():
        """Return a filtering expression for user test results failing
        compilation.

        """
        return UserTestResult.compilation_outcome == "fail"

    def compilation_succeeded(self):
        """Return whether the user test compiled.

        return (bool): True if the compilation succeeded (in the sense
            that an executable was created), False if not yet compiled
            or compilation was unsuccessful.

        """
        return self.compilation_outcome == "ok"

    @staticmethod
    def filter_compilation_succeeded():
        """Return a filtering expression for user test results failing
        compilation.

        """
        return UserTestResult.compilation_outcome == "ok"

    def evaluated(self):
        """Return whether the user test result has been evaluated.

        return (bool): True if evaluated, False otherwise.

        """
        return self.evaluation_outcome is not None

    @staticmethod
    def filter_evaluated():
        """Return a filtering lambda for evaluated user test results.

        """
        return UserTestResult.evaluation_outcome.isnot(None)

    def invalidate_compilation(self):
        """Blank all compilation and evaluation outcomes.

        """
        self.invalidate_evaluation()
        self.compilation_outcome = None
        self.compilation_text = []
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
        self.evaluation_text = []
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
        UserTest,
        viewonly=True)

    # Dataset (id and object) owning the executable.
    dataset_id = Column(
        Integer,
        ForeignKey(Dataset.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    dataset = relationship(
        Dataset,
        viewonly=True)

    # UserTestResult owning the executable.
    user_test_result = relationship(
        UserTestResult,
        back_populates="executables")

    # Filename and digest of the generated executable.
    filename = Column(
        Filename,
        nullable=False)
    digest = Column(
        Digest,
        nullable=False)
