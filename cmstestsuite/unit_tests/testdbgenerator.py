#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Utilities to create objects in a testing DB.

Apart from a base class for tests using a testing DB, this module
offers a series of add_<object> functions to create the minimal object
possible in the database.

When the object depends on a "parent" object, the caller can specify
it, or leave it for the function to create. When there is a common
ancestor through multiple paths, the functions check that it is the
same regardless of the path used to reach it.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import unittest

from datetime import timedelta

from sqlalchemy import create_engine

import cms

# Monkeypatch the db string.
cms.config.database += "fortesting"

import cms.db

from cmstestsuite.unit_tests.testidgenerator import unique_long_id, \
    unique_unicode_id

from cms.db import Contest, Dataset, Evaluation, Participation, \
    Submission, SubmissionResult, Task, Testcase, User, UserTest, \
    UserTestResult, \
    drop_db, init_db


class TestCaseWithDatabase(unittest.TestCase):
    """TestCase subclass starting with a clean testing database."""

    @classmethod
    def setUpClass(cls):
        cms.db.engine = create_engine(cms.config.database)
        drop_db()
        init_db()
        cls.connection = cms.db.engine.connect()
        cms.db.metadata.create_all(cls.connection)

    @classmethod
    def tearDownClass(cls):
        drop_db()
        cls.connection.close()
        cms.db.engine.dispose()


def add_contest(session, **kwargs):
    """Add a contest."""
    args = {
        "name": unique_unicode_id(),
        "description": unique_unicode_id(),
    }
    args.update(kwargs)
    contest = Contest(**args)
    session.add(contest)
    return contest


def add_user(session, **kwargs):
    """Add a user."""
    args = {
        "username": unique_unicode_id(),
        "password": "",
        "first_name": unique_unicode_id(),
        "last_name": unique_unicode_id(),
    }
    args.update(kwargs)
    user = User(**args)
    session.add(user)
    return user


def add_participation(session, user=None, contest=None, **kwargs):
    """Add a participation."""
    user = user if user is not None else add_user(session)
    contest = contest if contest is not None else add_contest(session)
    args = {
        "user": user,
        "contest": contest,
    }
    args.update(kwargs)
    participation = Participation(**args)
    session.add(participation)
    return participation


def add_task(session, contest=None, **kwargs):
    """Add a task."""
    contest = contest if contest is not None else add_contest(session)
    args = {
        "contest": contest,
        "name": unique_unicode_id(),
        "title": unique_unicode_id(),
    }
    args.update(kwargs)
    task = Task(**args)
    session.add(task)
    return task


def add_dataset(session, task=None, **kwargs):
    """Add a dataset."""
    task = task if task is not None else add_task(session)
    args = {
        "task": task,
        "description": unique_unicode_id(),
        "task_type": "",
        "task_type_parameters": "",
        "score_type": "",
        "score_type_parameters": "",
    }
    args.update(kwargs)
    dataset = Dataset(**args)
    session.add(dataset)
    return dataset


def add_testcase(session, dataset=None, **kwargs):
    """Add a testcase."""
    dataset = dataset if dataset is not None else add_dataset(session)
    args = {
        "dataset": dataset,
        "codename": unique_unicode_id(),
        "input": unique_unicode_id(),
        "output": unique_unicode_id(),
    }
    args.update(kwargs)
    testcase = Testcase(**args)
    session.add(testcase)
    return testcase


def add_submission(session, task=None, participation=None, **kwargs):
    """Add a submission."""
    task = task if task is not None else add_task(session)
    participation = participation \
        if participation is not None \
        else add_participation(session, contest=task.contest)
    assert task.contest == participation.contest
    args = {
        "task": task,
        "participation": participation,
        "timestamp": (task.contest.start + timedelta(0, unique_long_id())),
    }
    args.update(kwargs)
    submission = Submission(**args)
    session.add(submission)
    return submission


def add_submission_result(session, submission=None, dataset=None, **kwargs):
    """Add a submission result."""
    task = None
    task = submission.task if submission is not None else task
    task = dataset.task if dataset is not None else task
    submission = submission \
        if submission is not None else add_submission(session, task=task)
    dataset = dataset \
        if dataset is not None else add_dataset(session, task=task)
    assert submission.task == dataset.task
    args = {
        "submission": submission,
        "dataset": dataset,
    }
    args.update(kwargs)
    submission_result = SubmissionResult(**args)
    session.add(submission_result)
    return submission_result


def add_evaluation(session, submission_result=None, testcase=None, **kwargs):
    """Add an evaluation."""
    dataset = None
    dataset = submission_result.dataset \
        if submission_result is not None else dataset
    dataset = testcase.dataset if testcase is not None else dataset
    submission_result = submission_result \
        if submission_result is not None else add_submission_result(session)
    testcase = testcase if testcase is not None else add_testcase(session)
    assert submission_result.dataset == testcase.dataset
    args = {
        "submission_result": submission_result,
        "testcase": testcase,
    }
    args.update(kwargs)
    evaluation = Evaluation(**args)
    session.add(evaluation)
    return evaluation


def add_user_test(session, task=None, participation=None, **kwargs):
    """Add a user test."""
    task = task if task is not None else add_task(session)
    participation = participation \
        if participation is not None \
        else add_participation(session, contest=task.contest)
    assert task.contest == participation.contest
    args = {
        "task": task,
        "participation": participation,
        "input": unique_unicode_id(),
        "timestamp": (task.contest.start + timedelta(0, unique_long_id())),
    }
    args.update(kwargs)
    user_test = UserTest(**args)
    session.add(user_test)
    return user_test


def add_user_test_result(session, user_test=None, dataset=None, **kwargs):
    """Add a user test result."""
    task = None
    task = user_test.task if user_test is not None else task
    task = dataset.task if dataset is not None else task
    user_test = user_test \
        if user_test is not None else add_user_test(session, task=task)
    dataset = dataset \
        if dataset is not None else add_dataset(session, task=task)
    assert user_test.task == dataset.task
    args = {
        "user_test": user_test,
        "dataset": dataset,
    }
    args.update(kwargs)
    user_test_result = UserTestResult(**args)
    session.add(user_test_result)
    return user_test_result
