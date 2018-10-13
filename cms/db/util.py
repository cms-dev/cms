#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""Utilities relying on the database.

"""

import sys

from sqlalchemy import union
from sqlalchemy.exc import OperationalError

from cms import ConfigError
from . import SessionGen, Digest, Contest, Participation, Statement, \
    Attachment, Task, Manager, Dataset, Testcase, Submission, File, \
    SubmissionResult, Executable, UserTest, UserTestFile, UserTestManager, \
    UserTestResult, UserTestExecutable, PrintJob


def test_db_connection():
    """Perform an operation that raises if the DB is not reachable.

    raise (sqlalchemy.exc.OperationalError): if the DB cannot be
        accessed (usually for permission problems).

    """
    try:
        # We do not care of the specific query executed here, we just
        # use it to ensure that the DB is accessible.
        with SessionGen() as session:
            session.execute("select 0;")
    except OperationalError:
        raise ConfigError("Operational error while talking to the DB. "
                          "Is the connection string in cms.conf correct?")


def get_contest_list(session=None):
    """Return all the contest objects available on the database.

    session (Session|None): if specified, use such session for
        connecting to the database; otherwise, create a temporary one
        and discard it after the operation (this means that no further
        expansion of lazy properties of the returned Contest objects
        will be possible).

    return ([Contest]): the list of contests in the DB.

    """
    if session is None:
        with SessionGen() as session:
            return get_contest_list(session)

    return session.query(Contest).all()


def is_contest_id(contest_id):
    """Return if there is a contest with the given id in the database.

    contest_id (int): the id to query.
    return (boolean): True if there is such a contest.

    """
    with SessionGen() as session:
        return Contest.get_from_id(contest_id, session) is not None


def ask_for_contest(skip=None):
    """Print a greeter that ask the user for a contest, if there is
    not an indication of which contest to use in the command line.

    skip (int|None): how many commandline arguments are already taken
        by other usages (None for no arguments already consumed).

    return (int): a contest_id.

    """
    if isinstance(skip, int) and len(sys.argv) > skip + 1:
        contest_id = int(sys.argv[skip + 1])

    else:

        with SessionGen() as session:
            contests = get_contest_list(session)
            # The ids of the contests are cached, so the session can
            # be closed as soon as possible
            matches = {}
            n_contests = len(contests)
            if n_contests == 0:
                print("No contests in the database.")
                print("You may want to use some of the facilities in "
                      "cmscontrib to import a contest.")
                sys.exit(0)
            print("Contests available:")
            for i, row in enumerate(contests):
                print("%3d  -  ID: %d  -  Name: %s  -  Description: %s" %
                      (i + 1, row.id, row.name, row.description), end='')
                matches[i + 1] = row.id
                if i == n_contests - 1:
                    print(" (default)")
                else:
                    print()

        contest_number = input("Insert the row number next to the contest "
                               "you want to load (not the id): ")
        if contest_number == "":
            contest_number = n_contests
        try:
            contest_id = matches[int(contest_number)]
        except (ValueError, KeyError):
            print("Insert a correct number.")
            sys.exit(1)

    return contest_id


def get_submissions(session, contest_id=None, participation_id=None,
                    task_id=None, submission_id=None):
    """Search for submissions that match the given criteria

    The submissions will be returned as a list, and the last four
    parameters determine the filters used to decide which submissions
    to include. Some of them are incompatible, that is they cannot be
    non-None at the same time. When this happens it means that one of
    the parameters "implies" the other (for example, giving the
    participation already gives the contest it belongs to). Trying to
    give them both is useless and could only lead to inconsistencies
    and errors.

    session (Session): the database session to use.
    contest_id (int|None): id of the contest to filter with, or None.
    participation_id (int|None): id of the participation to filter
        with, or None.
    task_id (int|None): id of the task to filter with, or None.
    submission_id (int|None): id of the submission to filter with, or
        None.

    return (Query): a query for the list of submission that match the
        given criteria

    """
    if task_id is not None and contest_id is not None:
        raise ValueError("contest_id is superfluous if task_id is given")
    if participation_id is not None and contest_id is not None:
        raise ValueError(
            "contest_id is superfluous if participation_id is given")
    if submission_id is not None and contest_id is not None:
        raise ValueError("contest_id is superfluous if submission_id is given")
    if submission_id is not None and task_id is not None:
        raise ValueError("task_id is superfluous if submission_id is given")
    if submission_id is not None and participation_id is not None:
        raise ValueError(
            "participation_id is superfluous if submission_id is given")

    query = session.query(Submission)
    if submission_id is not None:
        query = query.filter(Submission.id == submission_id)
    if participation_id is not None:
        query = query.join(Participation) \
            .filter(Participation.id == participation_id)
    if task_id is not None:
        query = query.filter(Submission.task_id == task_id)
    if contest_id is not None:
        query = query.join(Participation) \
            .filter(Participation.contest_id == contest_id) \
            .join(Task).filter(Task.contest_id == contest_id)
    return query


def get_submission_results(session, contest_id=None, participation_id=None,
                           task_id=None, submission_id=None, dataset_id=None):
    """Search for submission results that match the given criteria

    The submission results will be returned as a list, and the last
    five parameters determine the filters used to decide which
    submission results to include. Some of them are incompatible, that
    is they cannot be non-None at the same time. When this happens it
    means that one of the parameters "implies" the other (for example,
    giving the participation already gives the contest it belongs
    to). Trying to give them both is useless and could only lead to
    inconsistencies and errors.

    session (Session): the database session to use.
    contest_id (int|None): id of the contest to filter with, or None.
    participation_id (int|None): id of the participation to filter with,
        or None.
    task_id (int|None): id of the task to filter with, or None.
    submission_id (int|None): id of the submission to filter with, or
        None.
    dataset_id (int|None): id of the dataset to filter with, or None.

    return (Query): a query for the list of submission results that
        match the given criteria

    """
    if task_id is not None and contest_id is not None:
        raise ValueError("contest_id is superfluous if task_id is given")
    if participation_id is not None and contest_id is not None:
        raise ValueError(
            "contest_id is superfluous if participation_id is given")
    if submission_id is not None and contest_id is not None:
        raise ValueError("contest_id is superfluous if submission_id is given")
    if submission_id is not None and task_id is not None:
        raise ValueError("task_id is superfluous if submission_id is given")
    if submission_id is not None and participation_id is not None:
        raise ValueError(
            "participation_id is superfluous if submission_id is given")
    if dataset_id is not None and task_id is not None:
        raise ValueError("task_id is superfluous if dataset_id is given")
    if dataset_id is not None and contest_id is not None:
        raise ValueError("contest_id is superfluous if dataset_id is given")

    query = session.query(SubmissionResult).join(Submission)
    if submission_id is not None:
        query = query.filter(SubmissionResult.submission_id == submission_id)
    if dataset_id is not None:
        query = query.filter(SubmissionResult.dataset_id == dataset_id)
    if participation_id is not None:
        query = query.join(Participation) \
            .filter(Participation.id == participation_id)
    if task_id is not None:
        query = query.filter(Submission.task_id == task_id)
    if contest_id is not None:
        query = query.join(Participation) \
            .filter(Participation.contest_id == contest_id)\
            .join(Task).filter(Task.contest_id == contest_id)
    return query


def get_datasets_to_judge(task):
    """Determine the datasets that ES and SS have to judge.

    Return a list of all Dataset objects that are either the
    active_dataset of their Task or have the autojudge flag set.
    These are the ones on which submissions are automatically judged by
    by ES and SS, whereas the results on any other dataset has to be
    explicitly requested by the contest admin (by invalidating it).

    task (Task): the task to query.

    return ([Dataset]): list of datasets to judge.

    """
    judge = []

    for dataset in task.datasets:
        if dataset.active or dataset.autojudge:
            judge.append(dataset)

    return judge


def enumerate_files(
        session, contest=None,
        skip_submissions=False, skip_user_tests=False, skip_print_jobs=False,
        skip_generated=False):
    """Enumerate all the files (by digest) referenced by the
    contest.

    return (set): a set of strings, the digests of the file
                  referenced in the contest.

    """
    contest_q = session.query(Contest)
    if contest is not None:
        contest_q = contest_q.filter(Contest.id == contest.id)

    queries = list()

    task_q = contest_q.join(Contest.tasks)
    queries.append(task_q.join(Task.statements).with_entities(Statement.digest))
    queries.append(task_q.join(Task.attachments)
                   .with_entities(Attachment.digest))

    dataset_q = task_q.join(Task.datasets)
    queries.append(dataset_q.join(Dataset.managers)
                   .with_entities(Manager.digest))
    queries.append(dataset_q.join(Dataset.testcases)
                   .with_entities(Testcase.input))
    queries.append(dataset_q.join(Dataset.testcases)
                   .with_entities(Testcase.output))

    if not skip_submissions:
        submission_q = task_q.join(Task.submissions)
        queries.append(submission_q.join(Submission.files)
                       .with_entities(File.digest))

        if not skip_generated:
            queries.append(submission_q.join(Submission.results)
                           .join(SubmissionResult.executables)
                           .with_entities(Executable.digest))

    if not skip_user_tests:
        user_test_q = task_q.join(Task.user_tests)
        queries.append(user_test_q.with_entities(UserTest.input))
        queries.append(user_test_q.join(UserTest.files)
                       .with_entities(UserTestFile.digest))
        queries.append(user_test_q.join(UserTest.managers)
                       .with_entities(UserTestManager.digest))

        if not skip_generated:
            user_test_result_q = user_test_q.join(UserTest.results)
            queries.append(user_test_result_q.join(UserTestResult.executables)
                           .with_entities(UserTestExecutable.digest))
            queries.append(user_test_result_q
                           .with_entities(UserTestResult.output))

    if not skip_print_jobs:
        queries.append(contest_q.join(Contest.participations)
                       .join(Participation.printjobs)
                       .with_entities(PrintJob.digest))

    # union(...).execute() would be executed outside of the session.
    digests = set(r[0] for r in session.execute(union(*queries)))
    digests.discard(Digest.TOMBSTONE)
    return digests
