#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
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

"""Submission-related database interface for SQLAlchemy. Not to be
used directly (import  from SQLAlchemyAll).

"""

import time
from datetime import datetime

from sqlalchemy import Column, ForeignKey, UniqueConstraint, \
     Integer, String, Float, DateTime
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.collections import column_mapped_collection
from sqlalchemy.ext.orderinglist import ordering_list

from cms.db.SQLAlchemyUtils import Base
from cms.db.Task import Task
from cms.db.User import User
from cmscommon.DateTime import make_datetime, make_timestamp


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
                                        cascade="all, delete-orphan",
                                        passive_deletes=True))

    # Task (id and object) of the submission.
    task_id = Column(Integer,
                     ForeignKey(Task.id,
                                onupdate="CASCADE", ondelete="CASCADE"),
                     nullable=False,
                     index=True)
    task = relationship(Task,
                        backref=backref("submissions",
                                        cascade="all, delete-orphan",
                                        passive_deletes=True))

    # Time of the submission.
    timestamp = Column(DateTime, nullable=False)

    # Language of submission, or None if not applicable.
    language = Column(String, nullable=True)

    # Compilation outcome (can be None = yet to compile, "ok" =
    # compilation successful and we can evaluate, "fail" =
    # compilation unsuccessful, throw it away).
    compilation_outcome = Column(String, nullable=True)

    # String containing output from the sandbox, and the compiler
    # stdout and stderr.
    compilation_text = Column(String, nullable=True)

    # Number of attempts of compilation.
    compilation_tries = Column(Integer, nullable=False)

    # Worker shard and sanbox where the compilation was performed
    compilation_shard = Column(Integer, nullable=True)
    compilation_sandbox = Column(String, nullable=True)

    # Evaluation outcome (can be None = yet to evaluate, "ok" =
    # evaluation successful). At any time, this should be equal to
    # evaluations != [].
    evaluation_outcome = Column(String, nullable=True)

    # Number of attempts of evaluation.
    evaluation_tries = Column(Integer, nullable=False)

    # Score as computed by ScoreService. Null means not yet scored.
    score = Column(Float, nullable=True)

    # Score details. It is a string containing *simple* HTML code that
    # AWS (and CWS if the user used a token) uses to display the
    # details of the submission. For example, results for each
    # testcases, subtask, etc.
    score_details = Column(String, nullable=True)

    # The same as the last two fields, but from the point of view of
    # the user (when he/she did not play a token).
    public_score = Column(Float, nullable=True)
    public_score_details = Column(String, nullable=True)

    # Ranking score details. It is a list of strings that are going to
    # be shown in a single row in the table of submission in RWS. JSON
    # encoded.
    ranking_score_details = Column(String, nullable=True)

    # Follows the description of the fields automatically added by
    # SQLAlchemy.
    # files (dict of File objects indexed by filename)
    # executables (dict of Executable objects indexed by filename)
    # evaluations (list of Evaluation objects, one for testcase)
    # token (Token object or None)

    LANGUAGES = ["c", "cpp", "pas"]
    LANGUAGES_MAP = {".c": "c",
                     ".cpp": "cpp",
                     ".cc": "cpp",
                     ".pas": "pas",
                     }

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
        self.executables = executables if executables is not None else {}
        self.compilation_text = compilation_text
        self.evaluation_outcome = evaluation_outcome
        self.evaluations = evaluations if evaluations is not None else []
        self.compilation_tries = compilation_tries
        self.evaluation_tries = evaluation_tries
        self.token = token
        self.compilation_shard = compilation_shard
        self.compilation_sandbox = compilation_sandbox

    def export_to_dict(self):
        """Return object data as a dictionary.

        """
        res = {
            'task': self.task.name,
            'timestamp': make_timestamp(self.timestamp),
            'files': [_file.export_to_dict()
                      for _file in self.files.itervalues()],
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
            'evaluations': [evaluation.export_to_dict()
                            for evaluation in self.evaluations],
            'evaluation_tries': self.evaluation_tries,
            'token': self.token
            }
        if self.token is not None:
            res['token'] = self.token.export_to_dict()
        return res

    @classmethod
    def import_from_dict(cls, data, tasks_by_name):
        """Build the object using data from a dictionary.

        """
        data['files'] = [File.import_from_dict(file_data)
                         for file_data in data['files']]
        data['files'] = dict([(_file.filename, _file)
                              for _file in data['files']])
        data['executables'] = [Executable.import_from_dict(executable_data)
                               for executable_data in data['executables']]
        data['executables'] = dict([(executable.filename, executable)
                                    for executable in data['executables']])
        data['evaluations'] = [Evaluation.import_from_dict(eval_data)
                               for eval_data in data['evaluations']]
        if data['token'] is not None:
            data['token'] = Token.import_from_dict(data['token'])
        data['task'] = tasks_by_name[data['task']]
        data['user'] = None
        data['timestamp'] = make_datetime(data['timestamp'])
        return cls(**data)

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

    def scored(self):
        """Return if the submission has been scored.

        return (bool): True if scored, False otherwise.

        """
        return self.score is not None

    def invalidate_compilation(self):
        """Blank all compilation and evaluation outcomes, and the score.

        """
        self.invalidate_evaluation()
        self.compilation_outcome = None
        self.compilation_text = None
        self.compilation_tries = 0
        self.executables = {}

    def invalidate_evaluation(self):
        """Blank the evaluation outcomes and the score.

        """
        self.invalidate_score()
        self.evaluation_outcome = None
        self.evaluations = []
        self.evaluation_tries = 0

    def invalidate_score(self):
        """Blank the score.

        """
        self.score = None
        self.score_details = None
        self.public_score = None
        self.public_score_details = None

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
    __table_args__ = (
        UniqueConstraint('submission_id',
                         name='cst_tokens_submission_id'),
        )

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
                                  cascade="all, delete-orphan",
                                  passive_deletes=True),
                              single_parent=True)

    # Time the token was played.
    timestamp = Column(DateTime, nullable=False)

    def __init__(self, timestamp=None, submission=None):
        if timestamp is None:
            timestamp = make_datetime()
        self.timestamp = timestamp
        self.submission = submission

    def export_to_dict(self):
        """Return object data as a dictionary.

        """
        return {
            'timestamp': make_timestamp(self.timestamp)
            }

    @classmethod
    def import_from_dict(cls, data):
        """Build the object using data from a dictionary.

        """
        data['timestamp'] = make_datetime(data['timestamp'])
        return cls(**data)


class File(Base):
    """Class to store information about one file submitted within a
    submission. Not to be used directly (import it from
    SQLAlchemyAll).

    """
    __tablename__ = 'files'
    __table_args__ = (
        UniqueConstraint('submission_id', 'filename',
                         name='cst_files_submission_id_filename'),
        )

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
                        cascade="all, delete-orphan",
                        passive_deletes=True))

    def __init__(self, digest, filename=None, submission=None):
        self.filename = filename
        self.digest = digest
        self.submission = submission

    def export_to_dict(self):
        """Return object data as a dictionary.

        """
        return {
            'filename': self.filename,
            'digest': self.digest
            }


class Executable(Base):
    """Class to store information about one file generated by the
    compilation of a submission. Not to be used directly (import it
    from SQLAlchemyAll).

    """
    __tablename__ = 'executables'
    __table_args__ = (
        UniqueConstraint('submission_id', 'filename',
                         name='cst_executables_submission_id_filename'),
        )

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
                        cascade="all, delete-orphan",
                        passive_deletes=True))

    def __init__(self, digest, filename=None, submission=None):
        self.filename = filename
        self.digest = digest
        self.submission = submission

    def export_to_dict(self):
        """Return object data as a dictionary.

        """
        return {
            'filename': self.filename,
            'digest': self.digest
            }


class Evaluation(Base):
    """Class to store information about the outcome of the evaluation
    of a submission against one testcase. Not to be used directly
    (import it from SQLAlchemyAll).

    """
    __tablename__ = 'evaluations'
    __table_args__ = (
        UniqueConstraint('submission_id', 'num',
                         name='cst_evaluations_submission_id_num'),
        )

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
                        cascade="all, delete-orphan",
                        passive_deletes=True))

    # String containing output from the grader (usually "Correct",
    # "Time limit", ...).
    text = Column(String, nullable=True)

    # String containing the outcome of the evaluation (usually 1.0,
    # ...) not necessary the points awarded, that will be computed by
    # the score type.
    outcome = Column(String, nullable=True)

    # Memory used by the evaluation, in bytes.
    memory_used = Column(Integer, nullable=True)

    # Evaluation's time and wall-clock time, in s.
    execution_time = Column(Float, nullable=True)
    execution_wall_clock_time = Column(Float, nullable=True)

    # Worker shard and sanbox where the evaluation was performed
    evaluation_shard = Column(Integer, nullable=True)
    evaluation_sandbox = Column(String, nullable=True)

    def __init__(self, text, outcome, num=None, submission=None,
                 memory_used=None, execution_time=None,
                 execution_wall_clock_time=None,
                 evaluation_shard=None, evaluation_sandbox=None):
        self.text = text
        self.outcome = outcome
        self.num = num
        self.submission = submission
        self.memory_used = memory_used
        self.execution_time = execution_time
        self.execution_wall_clock_time = execution_wall_clock_time
        self.evaluation_shard = evaluation_shard
        self.evaluation_sandbox = evaluation_sandbox

    def export_to_dict(self):
        """Return object data as a dictionary.

        """
        return {
            'text': self.text,
            'outcome': self.outcome,
            'num': self.num,
            'memory_used': self.memory_used,
            'execution_time': self.execution_time,
            'execution_wall_clock_time': self.execution_wall_clock_time,
            'evaluation_shard': self.evaluation_shard,
            'evaluation_sandbox': self.evaluation_sandbox
            }
