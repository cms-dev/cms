#!/usr/bin/env python2
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

from sqlalchemy.schema import Column, ForeignKey, UniqueConstraint
from sqlalchemy.types import Integer, Float, String, DateTime
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.orderinglist import ordering_list

from cms.db.SQLAlchemyUtils import Base
from cms.db.Task import Task
from cms.db.User import User
from cms.db.SmartMappedCollection import smart_mapped_collection

from cmscommon.DateTime import make_datetime, make_timestamp


class Submission(Base):
    """Class to store a submission. Not to be used directly (import it
    from SQLAlchemyAll).

    """
    __tablename__ = 'submissions'

    # Auto increment primary key.
    id = Column(
        Integer,
        primary_key=True)

    # User (id and object) that did the submission.
    user_id = Column(
        Integer,
        ForeignKey(User.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    user = relationship(
        User,
        backref=backref("submissions",
                        cascade="all, delete-orphan",
                        passive_deletes=True))

    # Task (id and object) of the submission.
    task_id = Column(
        Integer,
        ForeignKey(Task.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    task = relationship(
        Task,
        backref=backref("submissions",
                        cascade="all, delete-orphan",
                        passive_deletes=True))

    # Time of the submission.
    timestamp = Column(
        DateTime,
        nullable=False)

    # Language of submission, or None if not applicable.
    language = Column(
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
    # evaluation successful). At any time, this should be equal to
    # evaluations != [].
    evaluation_outcome = Column(
        String,
        nullable=True)

    # Number of attempts of evaluation.
    evaluation_tries = Column(
        Integer,
        nullable=False,
        default=0)

    # Score as computed by ScoringService. Null means not yet scored.
    score = Column(
        Float,
        nullable=True)

    # Score details. It's a JSON-encoded string containing information
    # that is given to ScoreType.get_html_details to generate an HTML
    # snippet that is shown on AWS and, if the user used a token, on
    # CWS to display the details of the submission.
    # For example, results for each testcases, subtask, etc.
    score_details = Column(
        String,
        nullable=True)

    # The same as the last two fields, but from the point of view of
    # the user (when he/she did not play a token).
    public_score = Column(
        Float,
        nullable=True)
    public_score_details = Column(
        String,
        nullable=True)

    # Ranking score details. It is a list of strings that are going to
    # be shown in a single row in the table of submission in RWS. JSON
    # encoded.
    ranking_score_details = Column(
        String,
        nullable=True)

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
        self.compilation_shard = None
        self.compilation_sandbox = None
        self.executables = {}

    def invalidate_evaluation(self):
        """Blank the evaluation outcomes and the score.

        """
        self.invalidate_score()
        self.evaluation_outcome = None
        self.evaluation_tries = 0
        self.evaluations = []

    def invalidate_score(self):
        """Blank the score.

        """
        self.score = None
        self.score_details = None
        self.public_score = None
        self.public_score_details = None
        self.ranking_score_details = None


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
    id = Column(
        Integer,
        primary_key=True)

    # Submission (id and object) the token has been used on.
    submission_id = Column(
        Integer,
        ForeignKey(Submission.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    submission = relationship(
        Submission,
        backref=backref(
            "token",
            uselist=False,
            cascade="all, delete-orphan",
            passive_deletes=True),
        single_parent=True)

    # Time the token was played.
    timestamp = Column(
        DateTime,
        nullable=False,
        default=make_datetime)


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

    # Submission (id and object) owning the file.
    submission_id = Column(
        Integer,
        ForeignKey(Submission.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    submission = relationship(
        Submission,
        backref=backref('files',
                        collection_class=smart_mapped_collection('filename'),
                        cascade="all, delete-orphan",
                        passive_deletes=True))


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

    # Submission (id and object) owning the executable.
    submission_id = Column(
        Integer,
        ForeignKey(Submission.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    submission = relationship(
        Submission,
        backref=backref('executables',
                        collection_class=smart_mapped_collection('filename'),
                        cascade="all, delete-orphan",
                        passive_deletes=True))


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
    id = Column(
        Integer,
        primary_key=True)

    # Number of the testcase this evaluation was performed on.
    num = Column(
        Integer,
        nullable=False)

    # Submission (id and object) owning the evaluation.
    submission_id = Column(
        Integer,
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
    text = Column(
        String,
        nullable=True)

    # String containing the outcome of the evaluation (usually 1.0,
    # ...) not necessary the points awarded, that will be computed by
    # the score type.
    outcome = Column(
        String,
        nullable=True)

    # Memory used by the evaluation, in bytes.
    memory_used = Column(
        Integer,
        nullable=True)

    # Evaluation's time and wall-clock time, in seconds.
    execution_time = Column(
        Float,
        nullable=True)
    execution_wall_clock_time = Column(
        Float,
        nullable=True)

    # Worker shard and sandbox where the evaluation was performed.
    evaluation_shard = Column(
        Integer,
        nullable=True)
    evaluation_sandbox = Column(
        String,
        nullable=True)
