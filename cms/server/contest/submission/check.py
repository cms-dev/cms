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

from cms.db import Task, Submission
from cms.db.user import Participation


def _filter_submission_query(q, participation, contest, task, cls):
    """Filter a query for submissions by participation, contest, task.

    Apply to the given query some filters that narrow down the set of
    results to the submissions that were sent in by the given
    contestant on the given contest or task.

    q (Query): a SQLAlchemy query, assumed to select from either
        submissions or user tests (as specified by cls).
    participation (Participation): the contestant to filter for.
    contest (Contest|None): the contest to filter for.
    task (Task|None): the task to filter for.
    cls (type): either Submission or UserTest, specifies which class
        the query selects from.

    return (Query): the original query with the filters applied.

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
        sql_session, participation, contest=None, task=None, cls=Submission):
    """Return the number of submissions the contestant sent in.

    Count the submissions (or user tests) for the given participation
    on the given task or contest (that is, on all the contest's tasks).

    sql_session (Session): the SQLAlchemy session to use.
    participation (Participation): the participation to fetch data for.
    contest (Contest|None): if given count on all the contest's tasks.
    task (Task|None): if given count only on this task (trumps contest).
    cls (type): if the UserTest class is given, count user tests rather
        than submissions.

    return (int): the count.

    """
    q = sql_session.query(func.count(cls.id))
    q = _filter_submission_query(q, participation, contest, task, cls)
    return q.scalar()


def check_max_number(
        sql_session, max_number, participation, contest=None, task=None,
        cls=Submission):
    """Check whether user already sent in given number of submissions.

    Verify whether the given participation did already hit the given
    constraint on the maximum number of submissions (i.e., whether they
    submitted at least as many submissions as the limit) and return the
    *opposite*, that is, return whether they are allowed to send more.

    sql_session (Session): the SQLAlchemy session to use.
    max_number (int|None): the constraint; None means no constraint has
        to be enforced and thus True is always returned.
    participation (Participation): the participation to fetch data for.
    contest (Contest|None): if given count on all the contest's tasks.
    task (Task|None): if given count only on this task (trumps contest).
    cls (type): if the UserTest class is given, count user tests rather
        than submissions.

    return (bool): whether the contestant can submit more.

    """
    if max_number is None or participation.unrestricted:
        return True
    count = get_submission_count(
        sql_session, participation, contest=contest, task=task, cls=cls)
    return count < max_number


def get_latest_submission(
        sql_session, participation, contest=None, task=None, cls=Submission):
    """Return the most recent submission the contestant sent in.

    Retrieve the submission (or user test) with the latest timestamp
    among the ones for the given participation on the given task or
    contest (that is, on all the contest's tasks).

    sql_session (Session): the SQLAlchemy session to use.
    participation (Participation): the participation to fetch data for.
    contest (Contest|None): if given look at all the contest's tasks.
    task (Task|None): if given look only at this task (trumps contest).
    cls (type): if the UserTest class is given, fetch user tests rather
        than submissions.

    return (Submission|UserTest|None): the latest submission/user test,
        if any.

    """
    q = sql_session.query(cls)
    q = _filter_submission_query(q, participation, contest, task, cls)
    q = q.order_by(desc(cls.timestamp))
    return q.first()


def check_min_interval(
        sql_session, min_interval, timestamp, participation, contest=None,
        task=None, cls=Submission):
    """Check whether user sent in latest submission long enough ago.

    Verify whether at least the given amount of time has passed since
    the given participation last sent in a submission (or user test).

    sql_session (Session): the SQLAlchemy session to use.
    min_interval (timedelta|None): the constraint; None means no
        constraint has to be enforced and thus True is always returned.
    timestamp (datetime): the current timestamp.
    participation (Participation): the participation to fetch data for.
    contest (Contest|None): if given look at all the contest's tasks.
    task (Task|None): if given look only at this task (trumps contest).
    cls (type): if the UserTest class is given, fetch user tests rather
        than submissions.

    return (bool): whether the contestant's "cool down" period has
        expired and they can submit again.

    """
    if min_interval is None or participation.unrestricted:
        return True
    submission = get_latest_submission(
        sql_session, participation, contest=contest, task=task, cls=cls)
    return (submission is None
            or timestamp - submission.timestamp >= min_interval)


def is_last_minutes(timestamp: datetime, participation: Participation, delta=timedelta(minutes=15)):
    """
    timestamp (datetime): the current timestamp.
    participation (Participation): the participation to be checked.
    delta (timedelta): length of the last time section to be checked.

    return (bool): whether it is the last `delta` of the participation.
    """

    if participation.contest.per_user_time is None:
        end_time = participation.contest.stop
    else:
        end_time = participation.starting_time + participation.contest.per_user_time

    end_time += participation.delay_time + participation.extra_time
    time_left = end_time - timestamp
    return time_left <= delta
