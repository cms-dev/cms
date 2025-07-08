#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2015 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2016 Amir Keivan Mohtashami <akmohtashami97@gmail.com>
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

"""Submission-related database interface for SQLAlchemy.

"""

from datetime import datetime
import random
from sqlalchemy import Boolean
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.schema import Column, ForeignKey, ForeignKeyConstraint, \
    UniqueConstraint
from sqlalchemy.types import Integer, Float, String, Unicode, DateTime, Enum, \
    BigInteger

from cmscommon.datetime import make_datetime
from . import Filename, FilenameSchema, Digest, Base, Participation, Task, \
    Dataset, Testcase


class Submission(Base):
    """Class to store a submission.

    """
    __tablename__ = 'submissions'
    __table_args__ = (
        UniqueConstraint("participation_id", "opaque_id",
                         name="participation_opaque_unique"),
    )

    # Opaque ID to be used to refer to this submission.
    opaque_id: int = Column(
        BigInteger,
        nullable=False)

    # Auto increment primary key.
    id: int = Column(
        Integer,
        primary_key=True)

    # User and Contest, thus Participation (id and object) that did the
    # submission.
    participation_id: int = Column(
        Integer,
        ForeignKey(Participation.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    participation: Participation = relationship(
        Participation,
        back_populates="submissions")

    # Task (id and object) of the submission.
    task_id: int = Column(
        Integer,
        ForeignKey(Task.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    task: Task = relationship(
        Task,
        back_populates="submissions")

    # Time of the submission.
    timestamp: datetime = Column(
        DateTime,
        nullable=False)

    # Language of submission, or None if not applicable.
    language: str | None = Column(
        String,
        nullable=True)

    # Comment from the administrator on the submission.
    comment: str = Column(
        Unicode,
        nullable=False,
        default="")

    # If false, submission will not be considered in contestant's score.
    official: bool = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    @property
    def short_comment(self) -> str:
        """The first line of the comment."""
        return self.comment.split("\n", 1)[0]

    # These one-to-many relationships are the reversed directions of
    # the ones defined in the "child" classes using foreign keys.

    files: dict[str, "File"] = relationship(
        "File",
        collection_class=attribute_mapped_collection("filename"),
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="submission")

    token: "Token | None" = relationship(
        "Token",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="submission")

    results: list["SubmissionResult"] = relationship(
        "SubmissionResult",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="submission")

    def get_result(self, dataset: Dataset | None = None) -> "SubmissionResult | None":
        """Return the result associated to a dataset.

        dataset: the dataset for which the caller wants
            the submission result; if None, the active one is used.

        return: the submission result
            associated to this submission and the given dataset, if it
            exists in the database, otherwise None.

        """
        if dataset is not None:
            # Use IDs to avoid triggering a lazy-load query.
            assert self.task_id == dataset.task_id
            dataset_id = dataset.id
        else:
            dataset_id = self.task.active_dataset_id

        return SubmissionResult.get_from_id(
            (self.id, dataset_id), self.sa_session)

    def get_result_or_create(self, dataset: Dataset | None = None) -> "SubmissionResult":
        """Return and, if necessary, create the result for a dataset.

        dataset: the dataset for which the caller wants
            the submission result; if None, the active one is used.

        return: the submission result associated to
            the this submission and the given dataset; if it
            does not exists, a new one is created.

        """
        if dataset is None:
            dataset = self.task.active_dataset

        submission_result = self.get_result(dataset)

        if submission_result is None:
            submission_result = SubmissionResult(submission=self,
                                                 dataset=dataset)

        return submission_result

    def tokened(self) -> bool:
        """Return if the user played a token against the submission.

        return: True if tokened, False otherwise.

        """
        return self.token is not None

    @classmethod
    def generate_opaque_id(cls, session, participation_id):
        randint_upper_bound = 2**63-1

        opaque_id = random.randint(0, randint_upper_bound)

        # Note that in theory this may cause the transaction to fail by
        # generating a non-actually-unique ID. This is however extremely
        # unlikely (prob. ~num_parallel_submissions_per_contestant^2/2**63).
        while (session
               .query(Submission)
               .filter(Submission.participation_id == participation_id)
               .filter(Submission.opaque_id == opaque_id)
               .first()
               is not None):
            opaque_id = random.randint(0, randint_upper_bound)

        return opaque_id


class File(Base):
    """Class to store information about one file submitted within a
    submission.

    """
    __tablename__ = 'files'
    __table_args__ = (
        UniqueConstraint('submission_id', 'filename'),
    )

    # Auto increment primary key.
    id: int = Column(
        Integer,
        primary_key=True)

    # Submission (id and object) owning the file.
    submission_id: int = Column(
        Integer,
        ForeignKey(Submission.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    submission: Submission = relationship(
        Submission,
        back_populates="files")

    # Filename and digest of the submitted file.
    filename: str = Column(
        FilenameSchema,
        nullable=False)
    digest: str = Column(
        Digest,
        nullable=False)


class Token(Base):
    """Class to store information about a token.

    """
    __tablename__ = 'tokens'
    __table_args__ = (
        UniqueConstraint('submission_id'),
    )

    # Auto increment primary key.
    id: int = Column(
        Integer,
        primary_key=True)

    # Submission (id and object) the token has been used on.
    submission_id: int = Column(
        Integer,
        ForeignKey(Submission.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    submission: Submission = relationship(
        Submission,
        back_populates="token",
        single_parent=True)

    # Time the token was played.
    timestamp: datetime = Column(
        DateTime,
        nullable=False,
        default=make_datetime)


class SubmissionResult(Base):
    """Class to store the evaluation results of a submission.

    """
    # Possible statuses of a submission result. COMPILING and
    # EVALUATING do not necessarily imply we are going to schedule
    # compilation and evalution for these submission results: for
    # example, they might be for datasets not scheduled for
    # evaluation, or they might have passed the maximum number of
    # tries. If a submission result does not exists for a pair
    # (submission, dataset), its status can be implicitly assumed to
    # be COMPILING.
    COMPILING = 1
    COMPILATION_FAILED = 2
    EVALUATING = 3
    SCORING = 4
    SCORED = 5

    __tablename__ = 'submission_results'
    __table_args__ = (
        UniqueConstraint('submission_id', 'dataset_id'),
    )

    # Primary key is (submission_id, dataset_id).
    submission_id: int = Column(
        Integer,
        ForeignKey(Submission.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        primary_key=True)
    submission: Submission = relationship(
        Submission,
        back_populates="results")

    dataset_id: int = Column(
        Integer,
        ForeignKey(Dataset.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        primary_key=True)
    dataset: Dataset = relationship(
        Dataset)

    # Now below follow the actual result fields.

    # Compilation outcome (can be None = yet to compile, "ok" =
    # compilation successful and we can evaluate, "fail" =
    # compilation unsuccessful, throw it away).
    compilation_outcome: str | None = Column(
        Enum("ok", "fail", name="compilation_outcome"),
        nullable=True)

    # The output from the sandbox (to allow localization the first item
    # of the list is a format string, possibly containing some "%s",
    # that will be filled in using the remaining items of the list).
    compilation_text: list[str] = Column(
        ARRAY(String),
        nullable=False,
        default=[])

    # Number of failures during compilation.
    compilation_tries: int = Column(
        Integer,
        nullable=False,
        default=0)

    # The compiler stdout and stderr.
    compilation_stdout: str | None = Column(
        Unicode,
        nullable=True)
    compilation_stderr: str | None = Column(
        Unicode,
        nullable=True)

    # Other information about the compilation.
    compilation_time: float | None = Column(
        Float,
        nullable=True)
    compilation_wall_clock_time: float | None = Column(
        Float,
        nullable=True)
    compilation_memory: int | None = Column(
        BigInteger,
        nullable=True)

    # Worker shard and sandbox where the compilation was performed.
    compilation_shard: int | None = Column(
        Integer,
        nullable=True)
    compilation_sandbox_paths: list[str] | None = Column(
        ARRAY(Unicode),
        nullable=True)
    compilation_sandbox_digests: list[str] | None = Column(
        ARRAY(String),
        nullable=True)

    # Evaluation outcome (can be None = yet to evaluate, "ok" =
    # evaluation successful). At any time, this should be equal to
    # evaluations != [].
    evaluation_outcome: str | None = Column(
        Enum("ok", name="evaluation_outcome"),
        nullable=True)

    # Number of failures during evaluation.
    evaluation_tries: int = Column(
        Integer,
        nullable=False,
        default=0)

    # Score as computed by ScoringService. Null means not yet scored.
    score: float | None = Column(
        Float,
        nullable=True)

    # Score details. It's a JSON-like structure containing information
    # that is given to ScoreType.get_html_details to generate an HTML
    # snippet that is shown on AWS and, if the user used a token, on
    # CWS to display the details of the submission.
    # For example, results for each testcases, subtask, etc.
    score_details: object | None = Column(
        JSONB,
        nullable=True)

    # Time when the submission is scored for the first time
    scored_at = Column(
        DateTime,
        nullable=True)

    # The same as the last two fields, but only showing information
    # visible to the user (assuming they did not use a token on this
    # submission).
    public_score: float | None = Column(
        Float,
        nullable=True)
    public_score_details: object | None = Column(
        JSONB,
        nullable=True)

    # Ranking score details. It is a list of strings that are going to
    # be shown in a single row in the table of submission in RWS.
    ranking_score_details: list[str] | None = Column(
        ARRAY(String),
        nullable=True)

    # These one-to-many relationships are the reversed directions of
    # the ones defined in the "child" classes using foreign keys.

    executables: dict[str, "Executable"] = relationship(
        "Executable",
        collection_class=attribute_mapped_collection("filename"),
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="submission_result")

    evaluations: list["Evaluation"] = relationship(
        "Evaluation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="submission_result")

    def get_status(self) -> int:
        """Return the status of this object.

        """
        if not self.compiled():
            return SubmissionResult.COMPILING
        elif self.compilation_failed():
            return SubmissionResult.COMPILATION_FAILED
        elif not self.evaluated():
            return SubmissionResult.EVALUATING
        elif not self.scored():
            return SubmissionResult.SCORING
        else:
            return SubmissionResult.SCORED

    def get_evaluation(self, testcase: Testcase) -> "Evaluation | None":
        """Return the Evaluation of this SR on the given Testcase, if any

        testcase: the testcase the returned evaluation will belong to.

        return: the (only!) evaluation of this submission result on the
            given testcase, or None if there isn't any.

        """
        # Use IDs to avoid triggering a lazy-load query.
        assert self.dataset_id == testcase.dataset_id

        # XXX If self.evaluations is already loaded we can walk over it
        # and spare a query.
        # (We could use .one() and avoid a LIMIT but we would need to
        # catch a NoResultFound exception.)
        return self.sa_session.query(Evaluation)\
            .filter(Evaluation.submission_result == self)\
            .filter(Evaluation.testcase == testcase)\
            .first()

    def get_max_evaluation_resources(self) -> tuple[float | None, int | None]:
        """Return the maximum time and memory used by this result

        return: max used time in seconds and memory in bytes,
            or None if data is incomplete or unavailable.

        """
        t, m = None, None
        if self.evaluated() and self.evaluations:
            for ev in self.evaluations:
                if ev.execution_time is not None \
                        and (t is None or t < ev.execution_time):
                    t = ev.execution_time
                if ev.execution_memory is not None \
                        and (m is None or m < ev.execution_memory):
                    m = ev.execution_memory
        return (t, m)

    def compiled(self) -> bool:
        """Return whether the submission result has been compiled.

        return: True if compiled, False otherwise.

        """
        return self.compilation_outcome is not None

    @staticmethod
    def filter_compiled():
        """Return a filtering expression for compiled submission results.

        """
        return SubmissionResult.compilation_outcome.isnot(None)

    def compilation_failed(self) -> bool:
        """Return whether the submission result did not compile.

        return: True if the compilation failed (in the sense
            that there is a problem in the user's source), False if
            not yet compiled or compilation was successful.

        """
        return self.compilation_outcome == "fail"

    @staticmethod
    def filter_compilation_failed():
        """Return a filtering expression for submission results failing
        compilation.

        """
        return SubmissionResult.compilation_outcome == "fail"

    def compilation_succeeded(self) -> bool:
        """Return whether the submission compiled.

        return: True if the compilation succeeded (in the sense
            that an executable was created), False if not yet compiled
            or compilation was unsuccessful.

        """
        return self.compilation_outcome == "ok"

    @staticmethod
    def filter_compilation_succeeded():
        """Return a filtering expression for submission results passing
        compilation.

        """
        return SubmissionResult.compilation_outcome == "ok"

    def evaluated(self) -> bool:
        """Return whether the submission result has been evaluated.

        return: True if evaluated, False otherwise.

        """
        return self.evaluation_outcome is not None

    @staticmethod
    def filter_evaluated():
        """Return a filtering lambda for evaluated submission results.

        """
        return SubmissionResult.evaluation_outcome.isnot(None)

    def needs_scoring(self) -> bool:
        """Return whether the submission result needs to be scored.

        return: True if in need of scoring, False otherwise.

        """
        return (self.compilation_failed() or self.evaluated()) and \
            not self.scored()

    def scored(self) -> bool:
        """Return whether the submission result has been scored.

        return: True if scored, False otherwise.

        """
        return all(getattr(self, k) is not None for k in [
            "score", "score_details",
            "public_score", "public_score_details",
            "ranking_score_details"])

    @staticmethod
    def filter_scored():
        """Return a filtering lambda for scored submission results.

        """
        return ((SubmissionResult.score.isnot(None))
                & (SubmissionResult.score_details.isnot(None))
                & (SubmissionResult.public_score.isnot(None))
                & (SubmissionResult.public_score_details.isnot(None))
                & (SubmissionResult.ranking_score_details.isnot(None)))

    def invalidate_compilation(self):
        """Blank all compilation and evaluation outcomes, and the score.

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
        self.compilation_sandbox_digests = []
        self.executables = {}

    def invalidate_evaluation(self, testcase_id: int | None = None):
        """Blank the evaluation outcomes and the score.

        testcase_id: ID of testcase to invalidate, or None to invalidate all.

        """
        self.invalidate_score()
        self.evaluation_outcome = None
        self.evaluation_tries = 0
        if testcase_id:
            self.evaluations = [e for e in self.evaluations if e.testcase_id != testcase_id]
        else:
            self.evaluations = []

    def invalidate_score(self):
        """Blank the score.

        """
        self.score = None
        self.score_details = None
        self.public_score = None
        self.public_score_details = None
        self.ranking_score_details = None

    def set_compilation_outcome(self, success: bool):
        """Set the compilation outcome based on the success.

        success: if the compilation was successful.

        """
        self.compilation_outcome = "ok" if success else "fail"

    def set_evaluation_outcome(self):
        """Set the evaluation outcome (always ok now).

        """
        self.evaluation_outcome = "ok"


class Executable(Base):
    """Class to store information about one file generated by the
    compilation of a submission.

    """
    __tablename__ = 'executables'
    __table_args__ = (
        ForeignKeyConstraint(
            ('submission_id', 'dataset_id'),
            (SubmissionResult.submission_id, SubmissionResult.dataset_id),
            onupdate="CASCADE", ondelete="CASCADE"),
        UniqueConstraint('submission_id', 'dataset_id', 'filename'),
    )

    # Auto increment primary key.
    id: int = Column(
        Integer,
        primary_key=True)

    # Submission (id and object) owning the executable.
    submission_id: int = Column(
        Integer,
        ForeignKey(Submission.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    submission: Submission = relationship(
        Submission,
        viewonly=True)

    # Dataset (id and object) owning the executable.
    dataset_id: int = Column(
        Integer,
        ForeignKey(Dataset.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    dataset: Dataset = relationship(
        Dataset,
        viewonly=True)

    # SubmissionResult owning the executable.
    submission_result: SubmissionResult = relationship(
        SubmissionResult,
        back_populates="executables")

    # Filename and digest of the generated executable.
    filename: str = Column(
        Filename,
        nullable=False)
    digest: str = Column(
        Digest,
        nullable=False)


class Evaluation(Base):
    """Class to store information about the outcome of the evaluation
    of a submission against one testcase.

    """
    __tablename__ = 'evaluations'
    __table_args__ = (
        ForeignKeyConstraint(
            ('submission_id', 'dataset_id'),
            (SubmissionResult.submission_id, SubmissionResult.dataset_id),
            onupdate="CASCADE", ondelete="CASCADE"),
        UniqueConstraint('submission_id', 'dataset_id', 'testcase_id'),
    )

    # Auto increment primary key.
    id: int = Column(
        Integer,
        primary_key=True)

    # Submission (id and object) owning the evaluation.
    submission_id: int = Column(
        Integer,
        ForeignKey(Submission.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    submission: Submission = relationship(
        Submission,
        viewonly=True)

    # Dataset (id and object) owning the evaluation.
    dataset_id: int = Column(
        Integer,
        ForeignKey(Dataset.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    dataset: Dataset = relationship(
        Dataset,
        viewonly=True)

    # SubmissionResult owning the evaluation.
    submission_result: SubmissionResult = relationship(
        SubmissionResult,
        back_populates="evaluations")

    # Testcase (id and object) this evaluation was performed on.
    testcase_id: int = Column(
        Integer,
        ForeignKey(Testcase.id,
                   onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True)
    testcase: Testcase = relationship(
        Testcase)

    # String containing the outcome of the evaluation (usually 1.0,
    # ...) not necessary the points awarded, that will be computed by
    # the score type.
    outcome: str | None = Column(
        Unicode,
        nullable=True)

    # The output from the grader, usually "Correct", "Time limit", ...
    # (to allow localization the first item of the list is a format
    # string, possibly containing some "%s", that will be filled in
    # using the remaining items of the list).
    text: list[str] = Column(
        ARRAY(String),
        nullable=False,
        default=[])

    # Evaluation's time and wall-clock time, in seconds.
    execution_time: float | None = Column(
        Float,
        nullable=True)
    execution_wall_clock_time: float | None = Column(
        Float,
        nullable=True)

    # Memory used by the evaluation, in bytes.
    execution_memory: int | None = Column(
        BigInteger,
        nullable=True)

    # Worker shard and sandbox where the evaluation was performed.
    evaluation_shard: int | None = Column(
        Integer,
        nullable=True)
    evaluation_sandbox_paths: list[str] | None = Column(
        ARRAY(Unicode),
        nullable=True)
    evaluation_sandbox_digests: list[str] | None = Column(
        ARRAY(String),
        nullable=True)

    @property
    def codename(self) -> str:
        """Return the codename of the testcase."""
        return self.testcase.codename
