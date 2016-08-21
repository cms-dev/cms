#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Utilities to generate test objects."""

from mock import Mock

import random
import string

from cms import SCORE_MODE_MAX
from cmscommon.datetime import make_datetime


def get_string(length=16):
    return "".join(random.choice(string.letters) for _ in xrange(length))


def get_int(upper=2 ** 31, lower=1):
    return random.randint(lower, upper)


def get_contest():
    contest = Mock()
    contest.id = get_int()
    contest.name = get_string()
    start = get_int(2 ** 11)
    duration = get_int(2 ** 8)
    contest.start = make_datetime(start)
    contest.stop = make_datetime(start + duration)
    contest.score_precision = 2
    contest.description = get_string()
    return contest


def get_testcase():
    testcase = Mock()
    testcase.id = get_int()
    return testcase


def get_dataset():
    dataset = Mock()
    dataset.id = get_int()
    dataset.testcases = dict(
        (get_string(), get_testcase()) for _ in xrange(10))
    dataset.score_type = "Sum"
    dataset.score_type_parameters = "100"
    return dataset


def get_task(dataset=None):
    dataset = dataset if dataset is not None else get_dataset()

    task = Mock()
    task.active_dataset = dataset

    task.id = get_int()
    task.name = get_string()
    task.title = get_string()
    task.score_precision = 2
    task.score_mode = SCORE_MODE_MAX
    task.num = 0

    return task


def get_user():
    user = Mock()
    user.username = get_string()
    user.first_name = get_string()
    user.last_name = get_string()
    return user


def get_team():
    team = Mock()
    team.code = get_string()
    team.name = get_string()
    return team


def get_participation(hidden=False, user=None):
    if user is None:
        user = get_user()
    participation = Mock()
    participation.id = get_int()
    participation.hidden = hidden
    participation.user = user
    participation.team = get_team()
    return participation


def get_sr(scored=True):
    sr = Mock()
    sr.scored.return_value = scored
    sr.ranking_score_details = "0"
    sr.score = get_int(100) if scored else None
    sr.token = None
    return sr


def get_submission(task=None, participation=None,
                   sr=None, scored=True, official=True):
    task = task if task is not None else get_task()
    participation = participation if participation is not None \
        else get_participation()
    sr = sr if sr is not None else get_sr(scored=scored)

    submission = Mock()
    submission.timestamp = make_datetime(get_int(2 ** 11 + 2 ** 8, 2 ** 11))
    submission.tokened.return_value = False

    submission.get_result.return_value = sr
    submission.participation = participation
    submission.task = task
    submission.official = official

    submission.id = get_int()
    return submission
