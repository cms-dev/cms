#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2015-2016 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
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

"""Functions to check whether submissions are allowed.

Provide functions to verify whether a given contestant is allowed to
send a submission or a user test on a given task and contest, based on
the current situation. Also include some support functions, which are
exported as they may be of general interest.

"""
from datetime import datetime, timedelta
from sqlalchemy import desc, func
from sqlalchemy.orm import Query

from cms.db import Task, Submission
from cms.db.contest import Contest
from cms.db.session import Session
from cms.db.user import Participation
from cms.db.usertest import UserTest


def _filter_submission_query(
    q: Query,
    participation: Participation,
    contest: Contest | None,
    task: Task | None,
    cls: type[Submission | UserTest],
) -> Query:
    """Filter a query for submissions by participation, contest, task.

    Apply to the given query some filters that narrow down the set of
    results to the submissions that were sent in by the given
    contestant on the given contest or task.

    q: a SQLAlchemy query, assumed to select from either
        submissions or user tests (as specified by cls).
    participation: the contestant to filter for.
    contest: the contest to filter for.
    task: the task to filter for.
    cls: either Submission or UserTest, specifies which class
        the query selects from.

    return: the original query with the filters applied.

    """
    if task is not None:
        if contest is not None and contest is not task.contest:
            raise ValueError("contest and task don't match")
        q = q.filter(cls.task == task)
    elif contest is not None:
        q = q.join(cls.task) \
            .filter(Task.contest == contest)
    else:
        raise ValueError("need at least one of contest and task")
    q = q.filter(cls.participation == participation)
    return q


def get_submission_count(
    sql_session: Session,
    participation: Participation,
    contest: Contest | None = None,
    task: Task | None = None,
    cls: type[Submission | UserTest] = Submission,
) -> int:
    """Return the number of submissions the contestant sent in.

    Count the submissions (or user tests) for the given participation
    on the given task or contest (that is, on all the contest's tasks).

    sql_session: the SQLAlchemy session to use.
    participation: the participation to fetch data for.
    contest: if given count on all the contest's tasks.
    task: if given count only on this task (trumps contest).
    cls: if the UserTest class is given, count user tests rather
        than submissions.

    return: the count.

    """
    q = sql_session.query(func.count(cls.id))
    q = _filter_submission_query(q, participation, contest, task, cls)
    return q.scalar()


def check_max_number(
    sql_session: Session,
    max_number: int | None,
    participation: Participation,
    contest: Contest | None = None,
    task: Task | None = None,
    cls: type[Submission | UserTest] = Submission,
) -> bool:
    """Check whether user already sent in given number of submissions.

    Verify whether the given participation did already hit the given
    constraint on the maximum number of submissions (i.e., whether they
    submitted at least as many submissions as the limit) and return the
    *opposite*, that is, return whether they are allowed to send more.

    sql_session: the SQLAlchemy session to use.
    max_number: the constraint; None means no constraint has
        to be enforced and thus True is always returned.
    participation: the participation to fetch data for.
    contest: if given count on all the contest's tasks.
    task: if given count only on this task (trumps contest).
    cls: if the UserTest class is given, count user tests rather
        than submissions.

    return: whether the contestant can submit more.

    """
    if max_number is None or participation.unrestricted:
        return True
    count = get_submission_count(
        sql_session, participation, contest=contest, task=task, cls=cls)
    return count < max_number


def get_latest_submission(
    sql_session: Session,
    participation: Participation,
    contest: Contest | None = None,
    task: Task | None = None,
    cls: type[Submission | UserTest] = Submission,
) -> Submission | UserTest | None:
    """Return the most recent submission the contestant sent in.

    Retrieve the submission (or user test) with the latest timestamp
    among the ones for the given participation on the given task or
    contest (that is, on all the contest's tasks).

    sql_session: the SQLAlchemy session to use.
    participation: the participation to fetch data for.
    contest: if given look at all the contest's tasks.
    task: if given look only at this task (trumps contest).
    cls: if the UserTest class is given, fetch user tests rather
        than submissions.

    return: the latest submission/user test,
        if any.

    """
    q = sql_session.query(cls)
    q = _filter_submission_query(q, participation, contest, task, cls)
    q = q.order_by(desc(cls.timestamp))
    return q.first()


def check_min_interval(
    sql_session: Session,
    min_interval: timedelta | None,
    timestamp: datetime,
    participation: Participation,
    contest: Contest | None = None,
    task: Task | None = None,
    cls: type[Submission | UserTest] = Submission,
) -> bool:
    """Check whether user sent in latest submission long enough ago.

    Verify whether at least the given amount of time has passed since
    the given participation last sent in a submission (or user test).

    sql_session: the SQLAlchemy session to use.
    min_interval: the constraint; None means no
        constraint has to be enforced and thus True is always returned.
    timestamp: the current timestamp.
    participation: the participation to fetch data for.
    contest: if given look at all the contest's tasks.
    task: if given look only at this task (trumps contest).
    cls: if the UserTest class is given, fetch user tests rather
        than submissions.

    return: whether the contestant's "cool down" period has
        expired and they can submit again.

    """
    if min_interval is None or participation.unrestricted:
        return True
    submission = get_latest_submission(
        sql_session, participation, contest=contest, task=task, cls=cls)
    return (submission is None
            or timestamp - submission.timestamp >= min_interval)


def is_last_minutes(timestamp: datetime, participation: Participation):
    """
    timestamp: the current timestamp.
    participation: the participation to be checked.

    return: whether the participation is in its last minutes of contest.
    """

    if participation.unrestricted \
            or participation.contest.min_submission_interval_grace_period is None:
        return False

    if participation.contest.per_user_time is None:
        end_time = participation.contest.stop
    else:
        end_time = participation.starting_time + participation.contest.per_user_time

    end_time += participation.delay_time + participation.extra_time
    time_left = end_time - timestamp
    return time_left <= \
        participation.contest.min_submission_interval_grace_period
