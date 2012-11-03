#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
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
from sqlalchemy.orm.collections import column_mapped_collection

from cms.db.SQLAlchemyUtils import Base
from cms.db.Task import Task
from cms.db.User import User

from cmscommon.DateTime import make_timestamp


class UserTest(Base):
    """Class to store a test requested by a user. Not to be used
    directly (import it from SQLAlchemyAll).

    """
    __tablename__ = 'user_tests'

    # Auto increment primary key.
    id = Column(Integer, primary_key=True)

    # User (id and object) that requested the test.
    user_id = Column(Integer,
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
    task_id = Column(Integer,
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
    timestamp = Column(DateTime, nullable=False)

    # Language of test, or None if not applicable.
    language = Column(String, nullable=True)

    # Input (provided by the user) and output files' digests for this
    # test
    input = Column(String, nullable=False)
    output = Column(String, nullable=True)

    # Compilation outcome (can be None = yet to compile, "ok" =
    # compilation successful and we can evaluate, "fail" =
    # compilation unsuccessful, throw it away).
    compilation_outcome = Column(String, nullable=True)

    # String containing output from the sandbox, and the compiler
    # stdout and stderr.
    compilation_text = Column(String, nullable=True)

    # Number of attempts of compilation.
    compilation_tries = Column(Integer, nullable=False)

    # Worker shard and sandbox where the compilation was performed
    compilation_shard = Column(Integer, nullable=True)
    compilation_sandbox = Column(String, nullable=True)

    # Evaluation outcome (can be None = yet to evaluate, "ok" =
    # evaluation successful).
    evaluation_outcome = Column(String, nullable=True)
    evaluation_text = Column(String, nullable=True)

    # Number of attempts of evaluation.
    evaluation_tries = Column(Integer, nullable=False)

    # Worker shard and sandbox wgere the evaluation was performed
    evaluation_shard = Column(Integer, nullable=True)
    evaluation_sandbox = Column(String, nullable=True)

    # Other information about the execution
    memory_used = Column(Integer, nullable=True)
    execution_time = Column(Float, nullable=True)

    # Follows the description of the fields automatically added by
    # SQLAlchemy.
    # files (dict of UserTestFile objects indexed by filename)
    # executables (dict of UserTestExecutable objects indexed by filename)
    # managers (dict of UserTestManager objects indexed by filename)

    def __init__(self, user, task, timestamp, files, managers,
                 input, output=None,
                 language=None, compilation_outcome=None,
                 compilation_text=None, compilation_tries=0,
                 executables=None,
                 compilation_shard=None, compilation_sandbox=None,
                 evaluation_outcome=None, evaluation_text=None,
                 evaluation_tries=0, evaluation_shard=None,
                 evaluation_sandbox=None, memory_used=None,
                 execution_time=None):
        self.user = user
        self.task = task
        self.timestamp = timestamp
        self.files = files
        self.managers = managers
        self.input = input
        self.output = output
        self.language = language
        self.compilation_outcome = compilation_outcome
        self.compilation_text = compilation_text
        self.compilation_tries = compilation_tries
        self.executables = executables if executables is not None else {}
        self.compilation_shard = compilation_shard
        self.compilation_sandbox = compilation_sandbox
        self.evaluation_outcome = evaluation_outcome
        self.evaluation_text = evaluation_text
        self.evaluation_tries = evaluation_tries
        self.evaluation_shard = evaluation_shard
        self.evaluation_sandbox = evaluation_sandbox
        self.memory_used = memory_used
        self.execution_time = execution_time

    def export_to_dict(self):
        """Return object data as a dictionary.

        """
        res = {
            'task': self.task.name,
            'timestamp': make_timestamp(self.timestamp),
            'files': [_file.export_to_dict()
                      for _file in self.files.itervalues()],
            'managers': [manager.export_to_dict()
                         for manager in self.managers.itervalues()],
            'input': self.input,
            'output': self.output,
            'language': self.language,
            'compilation_outcome': self.compilation_outcome,
            'compilation_tries': self.compilation_tries,
            'compilation_text': self.compilation_text,
            'compilation_shard': self.compilation_shard,
            'compilation_sandbox': self.compilation_sandbox,
            'executables': [executable.export_to_dict()
                            for executable
                            in self.executables.itervalues()],
            'evaluation_outcome': self.evaluation_outcome,
            'evaluation_text': self.evaluation_text,
            'evaluation_tries': self.evaluation_tries,
            'evaluation_shard': self.evalution_shard,
            'evaluation_sandbox': self.evaluation_sandbox,
            'memory_used': self.memory_used,
            'execution_time': self.execution_time,
            }
        return res

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
    id = Column(Integer, primary_key=True)

    # Filename and digest of the submitted file.
    filename = Column(String, nullable=False)
    digest = Column(String, nullable=False)

    # Submission (id and object) of the submission.
    user_test_id = Column(Integer,
                          ForeignKey(UserTest.id,
                                     onupdate="CASCADE", ondelete="CASCADE"),
                          nullable=False,
                          index=True)
    user_test = relationship(
        UserTest,
        backref=backref('files',
                        collection_class=column_mapped_collection(filename),
                        cascade="all, delete-orphan",
                        passive_deletes=True))

    def __init__(self, digest, filename=None, user_test=None):
        self.filename = filename
        self.digest = digest
        self.user_test = user_test

    def export_to_dict(self):
        """Return object data as a dictionary.

        """
        return {
            'filename': self.filename,
            'digest': self.digest
            }


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
    id = Column(Integer, primary_key=True)

    # Filename and digest of the file.
    filename = Column(String, nullable=False)
    digest = Column(String, nullable=False)

    # Submission (id and object) of the submission.
    user_test_id = Column(Integer,
                          ForeignKey(UserTest.id,
                                     onupdate="CASCADE", ondelete="CASCADE"),
                          nullable=False,
                          index=True)
    user_test = relationship(
        UserTest,
        backref=backref('executables',
                        collection_class=column_mapped_collection(filename),
                        cascade="all, delete-orphan",
                        passive_deletes=True))

    def __init__(self, digest, filename=None, user_test=None):
        self.filename = filename
        self.digest = digest
        self.user_test = user_test

    def export_to_dict(self):
        """Return object data as a dictionary.

        """
        return {
            'filename': self.filename,
            'digest': self.digest
            }


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
    id = Column(Integer, primary_key=True)

    # Filename and digest of the manager.
    filename = Column(String, nullable=False)
    digest = Column(String, nullable=False)

    # Task (id and object) owning the manager.
    user_test_id = Column(Integer,
                          ForeignKey(UserTest.id,
                                     onupdate="CASCADE", ondelete="CASCADE"),
                          nullable=False,
                          index=True)
    user_test = relationship(
        UserTest,
        backref=backref('managers',
                        collection_class=column_mapped_collection(filename),
                        cascade="all, delete-orphan",
                        passive_deletes=True))

    def __init__(self, digest, filename=None, user_test=None):
        self.filename = filename
        self.digest = digest
        self.user_test = user_test

    def export_to_dict(self):
        """Return object data as a dictionary.

        """
        return {'filename': self.filename,
                'digest':   self.digest}
