#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2011 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2011 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2011 Matteo Boscariol <boscarim@hotmail.com>
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

"""Submission-related database interface for SQLAlchemy. Not to be
used directly (import  from SQLAlchemyAll).

"""

import time

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.collections import column_mapped_collection
from sqlalchemy.ext.orderinglist import ordering_list

from cms.db.SQLAlchemyUtils import Base
from cms.db.Task import Task
from cms.db.User import User


class Submission(Base):
    """Class to store a submission. Not to be used directly (import it
    from SQLAlchemyAll).

    """
    __tablename__ = 'submissions'

    # Auto increment primary key.
    id = Column(Integer, primary_key=True)

    # User (id and object) that did the submission.
    user_id = Column(Integer,
                     ForeignKey(User.id,
                                onupdate="CASCADE", ondelete="CASCADE"),
                     nullable=False,
                     index=True)
    user = relationship(User,
                        backref=backref("submissions",
                                        single_parent=True,
                                        cascade="all, delete, delete-orphan"))

    # Task (id and object) of the submission.
    task_id = Column(Integer,
                     ForeignKey(Task.id,
                                onupdate="CASCADE", ondelete="CASCADE"),
                     nullable=False,
                     index=True)
    task = relationship(Task,
                        backref=backref("submissions",
                                        single_parent=True,
                                        cascade="all, delete, delete-orphan"))

    # Time of the submission.
    timestamp = Column(Integer, nullable=False)

    # Language of submission, or None if not applicable.
    language = Column(String, nullable=True)

    # Compilation outcome (can be None = yet to compile, "ok" =
    # compilation successful and we can evaluate, "fail" =
    # compilation unsuccessful, thorow it away).
    compilation_outcome = Column(String, nullable=True)

    # String containing output from the sandbox, and the compiler
    # stdout and stderr.
    compilation_text = Column(String, nullable=True)

    # Number of tentatives of compilation.
    compilation_tries = Column(Integer, nullable=False)

    # Worker shard and sanbox where the compilation was performed
    compilation_shard = Column(Integer, nullable=True)
    compilation_sandbox = Column(String, nullable=True)

    # Evaluation outcome (can be None = yet to evaluate, "ok" =
    # evaluation successful). At any time, this should be equal to
    # evaluations != [].
    evaluation_outcome = Column(String, nullable=True)

    # Number of tentatives of evaluation.
    evaluation_tries = Column(Integer, nullable=False)

    # Follows the description of the fields automatically added by
    # SQLAlchemy.
    # files (dict of File objects indexed by filename)
    # executables (dict of Executable objects indexed by filename)
    # evaluations (list of Evaluation objects, one for testcase)
    # token (Token object or None)

    LANGUAGES = ["c", "cpp", "pas"]

    def __init__(self, user, task, timestamp, files, language=None,
                 compilation_outcome=None, compilation_text=None,
                 compilation_tries=0, executables=None,
                 evaluation_outcome=None, evaluation_tries=0,
                 evaluations=None, token=None, compilation_shard=None,
                 compilation_sandbox=None):
        self.user = user
        self.task = task
        self.timestamp = timestamp
        self.files = files
        self.language = language
        self.compilation_outcome = compilation_outcome
        if executables is None:
            executables = {}
        self.executables = executables
        self.compilation_text = compilation_text
        self.evaluation_outcome = evaluation_outcome
        if evaluations is None:
            evaluations = []
        self.evaluations = evaluations
        self.compilation_tries = compilation_tries
        self.evaluation_tries = evaluation_tries
        self.token = token
        self.compilation_shard = compilation_shard
        self.compilation_sandbox = compilation_sandbox

    def export_to_dict(self):
        """Return object data as a dictionary.

        """
        res = {'task':                self.task.name,
               'timestamp':           self.timestamp,
               'files':               [_file.export_to_dict()
                                       for _file in self.files.itervalues()],
               'language':            self.language,
               'compilation_outcome': self.compilation_outcome,
               'compilation_tries':   self.compilation_tries,
               'compilation_text':    self.compilation_text,
               'compilation_shard':   self.compilation_shard,
               'compilation_sandbox': self.compilation_sandbox,
               'executables':         [executable.export_to_dict()
                                       for executable
                                       in self.executables.itervalues()],
               'evaluation_outcome':  self.evaluation_outcome,
               'evaluations':         [evaluation.export_to_dict()
                                       for evaluation in self.evaluations],
               'evaluation_tries':    self.evaluation_tries,
               'token':               self.token}
        if self.token is not None:
            res['token'] = self.token.export_to_dict()
        return res

    def tokened(self):
        """Return if the user played a token against the submission.

        return (bool): True if tokened, False otherwise.

        """
        return self.token is not None

    def compiled(self):
        """Return if the submission has been compiled.

        return (bool): True if compiled, False otherwise.

        """
        return self.compilation_outcome is not None

    def evaluated(self):
        """Return if the submission has been evaluated.

        return (bool): True if evaluated, False otherwise.

        """
        return self.evaluation_outcome is not None

    def invalid(self):
        """Blank all compilation and evaluation outcomes, so that ES
        will reschedule the submission for compilation.

        """
        self.compilation_outcome = None
        self.compilation_text = None
        self.compilation_tries = 0
        self.executables = {}
        self.invalid_evaluation()

    def invalid_evaluation(self):
        """Blank only the evaluation outcomes, so ES will reschedule
        the submission for evaluation.

        """
        self.evaluation_outcome = None
        self.evaluations = []
        self.evaluation_tries = 0

    def play_token(self, timestamp=None):
        """Tell the submission that a token has been used.

        timestamp (int): the time the token has been played.

        """
        self.token = Token(timestamp=timestamp)


class Token(Base):
    """Class to store information about a token. Not to be used
    directly (import it from SQLAlchemyAll).

    """
    __tablename__ = 'tokens'

    # Auto increment primary key.
    id = Column(Integer, primary_key=True)

    # Submission (id and object) the token has been played against.
    submission_id = Column(Integer,
                           ForeignKey(Submission.id,
                                      onupdate="CASCADE", ondelete="CASCADE"),
                           nullable=False,
                           index=True)
    submission = relationship(Submission,
                              backref=backref(
                                  "token",
                                  uselist=False,
                                  single_parent=True,
                                  cascade="all, delete, delete-orphan"),
                              single_parent=True)

    # Time the token was played.
    timestamp = Column(Integer, nullable=False)

    def __init__(self, timestamp=None, submission=None):
        if timestamp is None:
            timestamp = int(time.time())
        self.timestamp = timestamp
        self.submission = submission

    def export_to_dict(self):
        """Return object data as a dictionary.

        """
        return {'timestamp': self.timestamp}


class File(Base):
    """Class to store information about one file submitted within a
    submission. Not to be used directly (import it from
    SQLAlchemyAll).

    """
    __tablename__ = 'files'

    # Auto increment primary key.
    id = Column(Integer, primary_key=True)

    # Filename and digest of the submitted file.
    filename = Column(String, nullable=False)
    digest = Column(String, nullable=False)

    # Submission (id and object) of the submission.
    submission_id = Column(Integer,
                           ForeignKey(Submission.id,
                                      onupdate="CASCADE", ondelete="CASCADE"),
                           nullable=False,
                           index=True)
    submission = relationship(
        Submission,
        backref=backref('files',
                        collection_class=column_mapped_collection(filename),
                        single_parent=True,
                        cascade="all, delete, delete-orphan"))

    def __init__(self, digest, filename=None, submission=None):
        self.filename = filename
        self.digest = digest
        self.submission = submission

    def export_to_dict(self):
        """Return object data as a dictionary.

        """
        return {'filename': self.filename,
                'digest':   self.digest}


class Executable(Base):
    """Class to store information about one file generated by the
    compilation of a submission. Not to be used directly (import it
    from SQLAlchemyAll).

    """
    __tablename__ = 'executables'

    # Auto increment primary key.
    id = Column(Integer, primary_key=True)

    # Filename and digest of the file.
    filename = Column(String, nullable=False)
    digest = Column(String, nullable=False)

    # Submission (id and object) of the submission.
    submission_id = Column(Integer,
                           ForeignKey(Submission.id,
                                      onupdate="CASCADE", ondelete="CASCADE"),
                           nullable=False,
                           index=True)
    submission = relationship(
        Submission,
        backref=backref('executables',
                        collection_class=column_mapped_collection(filename),
                        single_parent=True,
                        cascade="all, delete, delete-orphan"))

    def __init__(self, digest, filename=None, submission=None):
        self.filename = filename
        self.digest = digest
        self.submission = submission

    def export_to_dict(self):
        """Return object data as a dictionary.

        """
        return {'filename': self.filename,
                'digest':   self.digest}


class Evaluation(Base):
    """Class to store information about the outcome of the evaluation
    of a submission against one testcase. Not to be used directly
    (import it from SQLAlchemyAll).

    """
    __tablename__ = 'evaluations'

    # Auto increment primary key.
    id = Column(Integer, primary_key=True)

    # Number of the testcase
    num = Column(Integer, nullable=False)

    # Submission (id and object) of the submission.
    submission_id = Column(Integer,
                           ForeignKey(Submission.id,
                                      onupdate="CASCADE", ondelete="CASCADE"),
                           nullable=False,
                           index=True)
    submission = relationship(
        Submission,
        backref=backref('evaluations',
                        collection_class=ordering_list('num'),
                        order_by=[num],
                        single_parent=True,
                        cascade="all, delete, delete-orphan"))

    # String containing output from the grader (usually "Correct",
    # "Time limit", ...).
    text = Column(String, nullable=True)

    # String containing the outcome of the evaluation (usually 1.0,
    # ...) not necessary the points awarded, that will be computed by
    # the scorer.
    outcome = Column(String, nullable=True)

    # Worker shard and sanbox where the evaluation was performed
    evaluation_shard = Column(Integer, nullable=True)
    evaluation_sandbox = Column(String, nullable=True)

    def __init__(self, text, outcome, num=None, submission=None,
                 evaluation_shard=None, evaluation_sandbox=None):
        self.text = text
        self.outcome = outcome
        self.num = num
        self.submission = submission
        self.evaluation_shard = evaluation_shard
        self.evaluation_sandbox = evaluation_sandbox

    def export_to_dict(self):
        """Return object data as a dictionary.

        """
        return {'text':               self.text,
                'outcome':            self.outcome,
                'num':                self.num,
                'evaluation_shard':   self.evaluation_shard,
                'evaluation_sandbox': self.evaluation_sandbox}
