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
                     nullable=False)
    user = relationship(User,
                        backref=backref("tokens",
                                        single_parent=True,
                                        cascade="all, delete, delete-orphan"))

    # Task (id and object) of the submission.
    task_id = Column(Integer,
                     ForeignKey(Task.id,
                                onupdate="CASCADE", ondelete="CASCADE"),
                     nullable=False)
    task = relationship(Task)

    # Time of the submission.
    timestamp = Column(Integer, nullable=False)

    # Compilation outcome (can be None = yet to compile, "ok" =
    # compilation successfull and we can evaluate, "fail" =
    # compilation unsuccessfull, thorow it away).
    compilation_outcome = Column(String, nullable=True)

    # String containing output from the sandbox, and the compiler
    # stdout and stderr.
    compilation_text = Column(String, nullable=True)

    # Number of tentatives of compilation.
    compilation_tries = Column(Integer, nullable=False)

    # Number of tentatives of evaluation.
    evaluation_tries = Column(Integer, nullable=False)

    # Follows the description of the fields automatically added by
    # SQLAlchemy.
    # files (dict of File objects indexes by filename)
    # executables (dict of Executable objects indexes by filename)
    # evaluations (list of Evaluation objects, one for testcase)
    # token_timestamp (Token object)
    # FIXME the backref is to the token, not to the timestamp

    LANGUAGES = ["c", "cpp", "pas"]

    def __init__(self, user, task, timestamp, files,
                 compilation_outcome=None, compilation_text=None,
                 compilation_tries=0, executables=None,
                 evaluation_tries=0, evaluations=None,
                 token_timestamp=None):
        self.user = user
        self.task = task
        self.timestamp = timestamp
        self.files = files
        self.compilation_outcome = compilation_outcome
        if executables == None:
            executables = {}
        self.executables = executables
        self.compilation_text = compilation_text
        if evaluations == None:
            evaluations = []
        self.evaluations = evaluations
        self.compilation_tries = compilation_tries
        self.evaluation_tries = evaluation_tries
        self.token_timestamp = token_timestamp

    def tokened(self):
        """Return if the user played a token against the submission.

        returns (bool): True if tokened, False otherwise.

        """
        return self.token_timestamp != None

    def evaluated(self):
        """Return if the submission has been evaluated.

        returns (bool): True if evaluated, False otherwise.

        """
        return self.evaluations != []

    def invalid(self):
        """Blanks all compilation and evaluation outcomes, so that ES
        will reschedule the submission for compilation.

        """
        self.compilation_outcome = None
        self.compilation_text = None
        self.evaluations = []
        self.executables = {}

    def invalid_evaluation(self):
        """Blanks only the evaluation outcomes, so ES will reschedule
        the submission for evaluation.

        """
        self.evaluations = []

    def verify_source(self, session):
        """Ensure that the submitted files agree with the format
        requested by the task.

        session (SQLAlchemy session): needed because we want to change
                                      the name of the files to map
                                      correctly with the submission
                                      format; be aware that this
                                      method DOES NOT COMMIT.
        returns (bool): True if the format is correct, False otherwise

        """
        if len(self.files) != len(self.task.submission_format):
            return (False, "Wrong number of files")
        language = None
        test_file = None

        submission_format = [x.filename for x in self.task.submission_format]

        # Try to understand if the task type is language dependent
        for name in submission_format:
            if name.find("%l") != -1:
                test_file = name

        # Try to detect the language used in the submission
        for test_lang in Submission.LANGUAGES:
            if test_file.replace("%l", test_lang) in self.files:
                language = test_lang
        if test_file != None and language == None:
            # If the task requires only one source file, be more
            # relaxed on the verification
            if len(submission_format) == 1:
                submitted_file = self.files.keys()[0]
                submitted_file_part = submitted_file.split(".")
                if len(submitted_file_part) > 1 and \
                        submitted_file_part[-1] in Submission.LANGUAGES:
                    language = submitted_file_part[-1]
                    # Wa adapt submission
                    correct_file = submission_format[0].replace("%l", language)
                    session.add(File(self.files[submitted_file].digest,
                                     correct_file,
                                     self))
                    del self.files[submitted_file]

                    # TODO: was there a better way than add-delete-del?
                else:
                    return (False, "Could not detect submission language")
            else:
                return (False, "Could not detect submission language")

        # Check the mapping between the submission format and the
        # actual submission
        for name in submission_format:
            if name.replace("%l", language) not in self.files:
                return (False, "Files not corresponding to submission format")

        return (True, language)

    def play_token(self, timestamp=None):
        """Tell the submission that a token has been used.

        timestamp (int): the time the token has been played.

        """
        Token(timestamp=timestamp, submission=self)


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
                           nullable=False)
    submission = relationship(Submission,
                              backref=backref("token_timestamp",
                                              uselist=False,
                                              single_parent=True,
                                              cascade="all, delete, delete-orphan"),
                              single_parent=True)

    # Time the token was played.
    timestamp = Column(Integer, nullable=False)

    def __init__(self, timestamp=None, submission=None):
        if timestamp == None:
            timestamp = time.time()
        self.timestamp = timestamp
        self.submission = submission


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
                           nullable=False)
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
                           nullable=False)
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
                           nullable=False)
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

    def __init__(self, text, outcome, num=None, submission=None, tries=0):
        self.text = text
        self.outcome = outcome
        self.num = num
        self.submission = submission
        self.tries = tries
