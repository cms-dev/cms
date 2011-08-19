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

"""Task-related database interface for SQLAlchemy. Not to be used
directly (import it from SQLAlchemyAll).

"""

from sqlalchemy import Column, ForeignKey, Integer, String, Float
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.collections import column_mapped_collection
from sqlalchemy.ext.orderinglist import ordering_list

from cms.db.SQLAlchemyUtils import Base
from cms.db.Contest import Contest
from cms.service.ScoreType import ScoreTypes


class Task(Base):
    """Class to store a task. Not to be used directly (import it from
    SQLAlchemyAll).

    """
    __tablename__ = 'tasks'

    # Auto increment primary key.
    id = Column(Integer, primary_key=True)

    # Number of the task for sorting.
    num = Column(Integer, nullable=False)

    # Contest (id and object) owning the task.
    contest_id = Column(Integer,
                        ForeignKey(Contest.id,
                                   onupdate="CASCADE", ondelete="CASCADE"),
                        nullable=False)
    contest = relationship(
        Contest,
        backref=backref('tasks',
                        collection_class=ordering_list('num'), order_by=[num],
                        single_parent=True,
                        cascade="all, delete, delete-orphan"))

    # Short name and long human readable title of the task.
    name = Column(String, nullable=False)
    title = Column(String, nullable=False)

    # Digest of the pdf statement.
    statement = Column(String, nullable=False)

    # Time and memory limits for every testcase.
    time_limit = Column(Float, nullable=False)
    memory_limit = Column(Integer, nullable=False)

    # Name of the TaskType child class suited for the task.
    task_type = Column(String, nullable=False)

    # Name of the ScoreType child class suited for the task.
    score_type = Column(String, nullable=False)

    # Parameters for the scorer class.
    score_parameters = Column(String, nullable=False)

    # Parameter to define the token behaviour. See Contest.py for
    # details. The only change is that these parameters influence the
    # contest in a task-per-task behavious. To play a token on a given
    # task, a user must satisfy the condition of the contest and the
    # one of the task.
    token_initial = Column(Integer, nullable=False)
    token_max = Column(Integer, nullable=False)
    token_total = Column(Integer, nullable=False)
    token_min_interval = Column(Integer, nullable=False)
    token_gen_time = Column(Integer, nullable=False)
    token_gen_number = Column(Integer, nullable=False)

    # Follows the description of the fields automatically added by
    # SQLAlchemy.
    # submission_format (list of SubmissionFormatElement objects)
    # public_testcases (list of PublicTestcase objects)
    # testcases (list of Testcase objects)
    # attachments (dict of Attachment objects indexed by filename)
    # managers (dict of Manager objects indexed by filename)

    # This object (independent from SQLAlchemy) is the instance of the
    # ScoreType class with the given parameters, taking care of
    # building the scores of the submissions..
    scorer = None

    TASK_TYPE_BATCH = "TaskTypeBatch"
    TASK_TYPE_PROGRAMMING = "TaskTypeProgramming"
    TASK_TYPE_OUTPUT_ONLY = "TaskTypeOutputOnly"

    def __init__(self, name, title, attachments, statement,
                 time_limit, memory_limit,
                 task_type, submission_format, managers,
                 score_type, score_parameters,
                 testcases, public_testcases,
                 token_initial, token_max, token_total,
                 token_min_interval, token_gen_time, token_gen_number,
                 contest=None):
        for filename, attachment in attachments.iteritems():
            attachment.filename = filename
        for filename, manager in managers.iteritems():
            manager.filename = filename

        self.name = name
        self.title = title
        self.attachments = attachments
        self.statement = statement
        self.time_limit = time_limit
        self.memory_limit = memory_limit
        self.task_type = task_type
        self.submission_format = submission_format
        self.managers = managers
        self.score_type = score_type
        self.score_parameters = score_parameters
        self.testcases = testcases
        self.public_testcases = public_testcases
        self.token_initial = token_initial
        self.token_max = token_max
        self.token_total = token_total
        self.token_min_interval = token_min_interval
        self.token_gen_time = token_gen_time
        self.token_gen_number = token_gen_number
        self.contest = contest

    def get_scorer(self):
        """Returns an appropriare ScoreType instance with the right parameters.

        return (object): an appropriate ScoreType instance

        """
        if self.scorer is None:
            self.scorer = ScoreTypes.get_score_type(self.score_type,
                                                    self.score_parameters,
                                                    len(self.testcases))
        return self.scorer


class Testcase(Base):
    """Class to store the information about a testcase. Not to be used
    directly (import it from SQLAlchemyAll).

    """
    __tablename__ = 'task_testcases'

    # Auto increment primary key.
    id = Column(Integer, primary_key=True)

    # Number of the task for sorting.
    num = Column(Integer, nullable=False)

    # Digests of the input and output files.
    input = Column(String, nullable=False)
    output = Column(String, nullable=False)

    # Task (id and object) owning the testcase.
    task_id = Column(Integer,
                     ForeignKey(Task.id,
                                onupdate="CASCADE", ondelete="CASCADE"),
                     nullable=False)
    task = relationship(
        Task,
        backref=backref('testcases',
                        collection_class=ordering_list('num'), order_by=[num],
                        single_parent=True,
                        cascade="all, delete, delete-orphan"))

    def __init__(self, input, output, num=None, task=None):
        self.input = input
        self.output = output
        self.num = num
        self.task = task


class Attachment(Base):
    """Class to store additional files to give to the user together
    with the statement of the task. Not to be used directly (import it
    from SQLAlchemyAll).

    """
    __tablename__ = 'attachments'

    # Auto increment primary key.
    id = Column(Integer, primary_key=True)

    # Filename and digest of the manager.
    filename = Column(String, nullable=False)
    digest = Column(String, nullable=False)

    # Task (id and object) owning the attachment.
    task_id = Column(Integer,
                     ForeignKey(Task.id,
                                onupdate="CASCADE", ondelete="CASCADE"),
                     nullable=False)
    task = relationship(
        Task,
        backref=backref('attachments',
                        collection_class=column_mapped_collection(filename),
                        single_parent=True,
                        cascade="all, delete, delete-orphan"))

    def __init__(self, digest, filename=None, task=None):
        self.filename = filename
        self.digest = digest
        self.task = task


class Manager(Base):
    """Class to store additional files needed to compile or evaluate a
    submission (e.g., graders). Not to be used directly (import it from
    SQLAlchemyAll).

    """
    __tablename__ = 'managers'

    # Auto increment primary key.
    id = Column(Integer, primary_key=True)

    # Filename and digest of the manager.
    filename = Column(String, nullable=False)
    digest = Column(String, nullable=False)

    # Task (id and object) owning the manager.
    task_id = Column(Integer,
                     ForeignKey(Task.id,
                                onupdate="CASCADE", ondelete="CASCADE"),
                     nullable=False)
    task = relationship(
        Task,
        backref=backref('managers',
                        collection_class=column_mapped_collection(filename),
                        single_parent=True,
                        cascade="all, delete, delete-orphan"))

    def __init__(self, digest, filename=None, task=None):
        self.filename = filename
        self.digest = digest
        self.task = task


class PublicTestcase(Base):
    """Class to store which testcase outcomes are going to be showed
    to the user (even without playing a token). Not to be used directly
    (import it from SQLAlchemyAll).

    """
    __tablename__ = 'public_testcases'

    # Auto increment primary key.
    id = Column(Integer, primary_key=True)

    # Task (id and object) owning the public testcase.
    task_id = Column(Integer,
                     ForeignKey(Task.id,
                                onupdate="CASCADE", ondelete="CASCADE"),
                     nullable=False)
    task = relationship(Task,
                        backref=backref('public_testcases',
                                        single_parent=True,
                                        cascade="all, delete, delete-orphan"))

    # Number of the testcase to be made public.
    testcase = Column(Integer, nullable=False)

    def __init__(self, testcase, task=None):
        self.testcase = testcase
        self.task = task


class SubmissionFormatElement(Base):
    """Class to store the requested files that a submission must
    include. Filenames may include %l to represent an accepted
    language extension. Not to be used directly (import it from
    SQLAlchemyAll).

    """
    __tablename__ = 'submission_format_elements'

    # Auto increment primary key.
    id = Column(Integer, primary_key=True)

    # Task (id and object) owning the submission format.
    task_id = Column(Integer,
                     ForeignKey(Task.id,
                                onupdate="CASCADE", ondelete="CASCADE"),
                     nullable=False)
    task = relationship(Task,
                        backref=backref('submission_format',
                                        single_parent=True,
                                        cascade="all, delete, delete-orphan"))

    # Format of the given submission file.
    filename = Column(String)

    def __init__(self, filename, task=None):
        self.filename = filename
        self.task = task
