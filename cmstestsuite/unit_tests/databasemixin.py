#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""A unittest.TestCase mixin for tests interacting with the database.

This mixin will connect to a different DB, recreating it for each
testing class; it will also create a session at each test setup.

The mixin also offers a series of get_<object> (to build an object, not
attached to any session) and add_<object> (to build and add the object
to the default session) methods. Without arguments, these will create
minimal objects with random values in the fields, and callers can
specify as many fields as they like.

When the object depends on a "parent" object, the caller can specify
it, or leave it for the function to create. When there is a common
ancestor through multiple paths, the functions check that it is the
same regardless of the path used to reach it.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa
from six import itervalues

from datetime import timedelta

import cms

# Monkeypatch the db string.
# Noqa to avoid complaints due to imports after a statement.
cms.config.database += "fortesting"  # noqa

import cms.db

from cmstestsuite.unit_tests.testidgenerator import unique_long_id, \
    unique_unicode_id, unique_digest

from cms.db import Announcement, Base, Contest, Dataset, Evaluation, \
    Executable, File, Message, Participation, Question, Session, Statement, \
    Submission, SubmissionFormatElement, SubmissionResult, Task, Team, \
    Testcase, User, UserTest, UserTestResult, drop_db, init_db
from cms.db.filecacher import DBBackend


class DatabaseMixin(object):
    """Mixin for tests with database access."""

    @classmethod
    def setUpClass(cls):
        super(DatabaseMixin, cls).setUpClass()
        assert "fortesting" in str(cms.db.engine), \
            "Monkey patching of DB connection string failed"
        drop_db()
        init_db()
        cls.connection = cms.db.engine.connect()
        cms.db.metadata.create_all(cls.connection)

    @classmethod
    def tearDownClass(cls):
        drop_db()
        cls.connection.close()
        cms.db.engine.dispose()
        super(DatabaseMixin, cls).tearDownClass()

    def setUp(self):
        super(DatabaseMixin, self).setUp()
        self.session = Session()

    def tearDown(self):
        self.session.rollback()
        super(DatabaseMixin, self).tearDown()

    def delete_data(self):
        """Delete all the data in the DB.

        This is useful to call during tear down, for tests that rely on
        starting from a clean DB.

        """
        for table in itervalues(Base.metadata.tables):
            self.session.execute(table.delete())
        self.session.commit()

    @staticmethod
    def add_fsobject(digest, content):
        dbbackend = DBBackend()
        fobj = dbbackend.create_file(digest)
        fobj.write(content)
        dbbackend.commit_file(fobj, digest)

    @staticmethod
    def get_contest(**kwargs):
        """Create a contest"""
        args = {
            "name": unique_unicode_id(),
            "description": unique_unicode_id(),
        }
        args.update(kwargs)
        contest = Contest(**args)
        return contest

    def add_contest(self, **kwargs):
        """Create a contest and add it to the session"""
        contest = self.get_contest(**kwargs)
        self.session.add(contest)
        return contest

    @staticmethod
    def get_announcement(contest=None, **kwargs):
        """Create an announcement"""
        contest = contest \
            if contest is not None else DatabaseMixin.get_contest()
        args = {
            "contest": contest,
            "subject": unique_unicode_id(),
            "text": unique_unicode_id(),
            "timestamp": (contest.start + timedelta(0, unique_long_id())),
        }
        args.update(kwargs)
        announcement = Announcement(**args)
        return announcement

    def add_announcement(self, **kwargs):
        """Create an announcement and add it to the session"""
        announcement = self.get_announcement(**kwargs)
        self.session.add(announcement)
        return announcement

    @staticmethod
    def get_user(**kwargs):
        """Create a user"""
        args = {
            "username": unique_unicode_id(),
            "password": "",
            "first_name": unique_unicode_id(),
            "last_name": unique_unicode_id(),
        }
        args.update(kwargs)
        user = User(**args)
        return user

    def add_user(self, **kwargs):
        """Create a user and add it to the session"""
        user = self.get_user(**kwargs)
        self.session.add(user)
        return user

    @staticmethod
    def get_participation(user=None, contest=None, **kwargs):
        """Create a participation"""
        user = user if user is not None else DatabaseMixin.get_user()
        contest = contest \
            if contest is not None else DatabaseMixin.get_contest()
        args = {
            "user": user,
            "contest": contest,
        }
        args.update(kwargs)
        participation = Participation(**args)
        return participation

    def add_participation(self, **kwargs):
        """Create a participation and add it to the session"""
        participation = self.get_participation(**kwargs)
        self.session.add(participation)
        return participation

    @staticmethod
    def get_message(participation=None, **kwargs):
        """Create a message."""
        participation = participation \
            if participation is not None else DatabaseMixin.get_participation()
        args = {
            "participation": participation,
            "subject": unique_unicode_id(),
            "text": unique_unicode_id(),
            "timestamp": (participation.contest.start
                          + timedelta(0, unique_long_id())),
        }
        args.update(kwargs)
        message = Message(**args)
        return message

    def add_message(self, **kwargs):
        """Create a message and add it to the session"""
        message = self.get_message(**kwargs)
        self.session.add(message)
        return message

    @staticmethod
    def get_question(participation=None, **kwargs):
        """Create a question."""
        participation = participation \
            if participation is not None else DatabaseMixin.get_participation()
        args = {
            "participation": participation,
            "subject": unique_unicode_id(),
            "text": unique_unicode_id(),
            "question_timestamp": (participation.contest.start
                                   + timedelta(0, unique_long_id())),
        }
        args.update(kwargs)
        question = Question(**args)
        return question

    def add_question(self, **kwargs):
        """Create a question and add it to the session"""
        question = self.get_question(**kwargs)
        self.session.add(question)
        return question

    @staticmethod
    def get_task(**kwargs):
        """Create a task"""
        args = {
            "name": unique_unicode_id(),
            "title": unique_unicode_id(),
        }
        args.update(kwargs)
        task = Task(**args)
        return task

    def add_task(self, **kwargs):
        """Create a task and add it to the session"""
        task = self.get_task(**kwargs)
        self.session.add(task)
        return task

    def add_submission_format_element(self, task=None, **kwargs):
        """Create a submission format element and add it to the session"""
        task = task if task is not None else self.add_task()
        args = {
            "task": task,
            "filename": unique_unicode_id(),
        }
        args.update(kwargs)
        sfe = SubmissionFormatElement(**args)
        self.session.add(sfe)
        return sfe

    def add_statement(self, task=None, **kwargs):
        """Create a statement and add it to the session"""
        task = task if task is not None else self.add_task()
        args = {
            "task": task,
            "digest": unique_digest(),
            "language": unique_unicode_id(),
        }
        args.update(kwargs)
        statement = Statement(**args)
        self.session.add(statement)
        return statement

    @staticmethod
    def get_dataset(task=None, **kwargs):
        """Create a dataset"""
        task = task if task is not None else DatabaseMixin.get_task()
        args = {
            "task": task,
            "description": unique_unicode_id(),
            "task_type": "",
            # "None" won't work here as the column is defined as non
            # nullable. As soon as we'll depend on SQLAlchemy 1.1 we
            # will be able to put JSON.NULL here instead.
            "task_type_parameters": {},
            "score_type": "",
            # Same here.
            "score_type_parameters": {},
        }
        args.update(kwargs)
        dataset = Dataset(**args)
        return dataset

    def add_dataset(self, **kwargs):
        """Create a dataset and add it to the session"""
        dataset = self.get_dataset(**kwargs)
        self.session.add(dataset)
        return dataset

    def add_testcase(self, dataset=None, **kwargs):
        """Add a testcase."""
        dataset = dataset if dataset is not None else self.add_dataset()
        args = {
            "dataset": dataset,
            "codename": unique_unicode_id(),
            "input": unique_digest(),
            "output": unique_digest(),
        }
        args.update(kwargs)
        testcase = Testcase(**args)
        self.session.add(testcase)
        return testcase

    def add_submission(self, task=None, participation=None, **kwargs):
        """Add a submission."""
        if task is None:
            task = self.add_task(contest=self.add_contest())
        participation = participation \
            if participation is not None \
            else self.add_participation(contest=task.contest)
        assert task.contest == participation.contest
        args = {
            "task": task,
            "participation": participation,
            "timestamp": (task.contest.start + timedelta(0, unique_long_id())),
        }
        args.update(kwargs)
        submission = Submission(**args)
        self.session.add(submission)
        return submission

    def add_file(self, submission=None, **kwargs):
        """Create a file and add it to the session"""
        if submission is None:
            submission = self.add_sbubmission()
        args = {
            "submission": submission,
            "filename": unique_unicode_id(),
            "digest": unique_digest(),
        }
        args.update(kwargs)
        file = File(**args)
        self.session.add(file)
        return file

    def add_submission_result(self, submission=None, dataset=None, **kwargs):
        """Add a submission result."""
        task = None
        task = submission.task if submission is not None else task
        task = dataset.task if dataset is not None else task
        submission = submission \
            if submission is not None else self.add_submission(task=task)
        dataset = dataset \
            if dataset is not None else self.add_dataset(task=task)
        assert submission.task == dataset.task
        args = {
            "submission": submission,
            "dataset": dataset,
        }
        args.update(kwargs)
        submission_result = SubmissionResult(**args)
        self.session.add(submission_result)
        return submission_result

    def add_executable(self, submission_result=None, **kwargs):
        """Create an executable and add it to the session"""
        submission_result = submission_result \
            if submission_result is not None \
            else self.add_submission_result()
        args = {
            "submission_result": submission_result,
            "digest": unique_digest(),
            "filename": unique_unicode_id(),
        }
        args.update(kwargs)
        executable = Executable(**args)
        self.session.add(executable)
        return executable

    def add_evaluation(self, submission_result=None, testcase=None, **kwargs):
        """Add an evaluation."""
        dataset = None
        dataset = submission_result.dataset \
            if submission_result is not None else dataset
        dataset = testcase.dataset if testcase is not None else dataset
        submission_result = submission_result \
            if submission_result is not None \
            else self.add_submission_result(dataset=dataset)
        testcase = testcase if testcase is not None else self.add_testcase()
        assert submission_result.dataset == testcase.dataset
        args = {
            "submission_result": submission_result,
            "testcase": testcase,
        }
        args.update(kwargs)
        evaluation = Evaluation(**args)
        self.session.add(evaluation)
        return evaluation

    def add_user_test(self, task=None, participation=None, **kwargs):
        """Add a user test."""
        if task is None:
            task = self.add_task(contest=self.add_contest())
        participation = participation \
            if participation is not None \
            else self.add_participation(contest=task.contest)
        assert task.contest == participation.contest
        args = {
            "task": task,
            "participation": participation,
            "input": unique_digest(),
            "timestamp": (task.contest.start + timedelta(0, unique_long_id())),
        }
        args.update(kwargs)
        user_test = UserTest(**args)
        self.session.add(user_test)
        return user_test

    def add_user_test_result(self, user_test=None, dataset=None, **kwargs):
        """Add a user test result."""
        task = None
        task = user_test.task if user_test is not None else task
        task = dataset.task if dataset is not None else task
        user_test = user_test \
            if user_test is not None else self.add_user_test(task=task)
        dataset = dataset \
            if dataset is not None else self.add_dataset(task=task)
        assert user_test.task == dataset.task
        args = {
            "user_test": user_test,
            "dataset": dataset,
        }
        args.update(kwargs)
        user_test_result = UserTestResult(**args)
        self.session.add(user_test_result)
        return user_test_result

    # Other commonly used generation functions.

    def add_submission_with_results(self, task, participation,
                                    compilation_outcome=None):
        """Add a submission for the tasks, all of its results, and optionally
        the compilation outcome for all results.

        """
        submission = self.add_submission(task, participation)
        results = [self.add_submission_result(submission, dataset)
                   for dataset in task.datasets]
        if compilation_outcome is not None:
            for result in results:
                result.set_compilation_outcome(compilation_outcome)
        return submission, results

    def add_user_test_with_results(self, compilation_outcome=None):
        """Add a user_test for the first tasks, all of its results, and
        optionally the compilation outcome for all results.

        """
        user_test = self.add_user_test(self.tasks[0], self.participation)
        results = [self.add_user_test_result(user_test, dataset)
                   for dataset in self.tasks[0].datasets]
        if compilation_outcome is not None:
            for result in results:
                result.set_compilation_outcome(compilation_outcome)
        return user_test, results

    @staticmethod
    def get_team(**kwargs):
        """Create a team"""
        args = {
            "code": unique_unicode_id(),
            "name": unique_unicode_id(),
        }
        args.update(kwargs)
        team = Team(**args)
        return team

    def add_team(self, **kwargs):
        """Create a team and add it to the session"""
        team = self.get_team(**kwargs)
        self.session.add(team)
        return team
