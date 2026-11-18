#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2026 Pasit Sangprachathanarak <ouipingpasit@gmail.com>
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

"""Seed the test database with the objects the browser tests rely on.

The data is created through the helpers of DatabaseObjectGeneratorMixin,
so the browser tests do not depend on the import path of cmscontrib.

"""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from cms.db import Announcement, File, Message, Question, Session, \
    Statement, SubmissionResult, Testcase, UserTest, UserTestFile, \
    UserTestResult, drop_db, engine, init_db
from cms.db.filecacher import DBBackend
from cmscommon.crypto import build_password
from cmstestsuite.unit_tests.databasemixin import DatabaseObjectGeneratorMixin


# Names of the languages enabled in the seeded contest.
LANGUAGES = ["C++20 / g++", "Python 3 / CPython"]

CONTEST_DESCRIPTION = "Browser Test Contest"
TASK_NAME = "sum"
TASK_TITLE = "Sum of two numbers"
# A second task whose submissions consist of two files, which makes CWS
# show a menu to download them instead of a single link.
PAIR_TASK_NAME = "pair"
PAIR_FILES = ["pair_a.py", "pair_b.py"]
ANNOUNCEMENT_SUBJECT = "Welcome to the contest"
MESSAGE_SUBJECT = "A private message"
ANSWERED_QUESTION_SUBJECT = "Is the input sorted?"
ANSWER_TEXT = "Yes, it is sorted."

# Users that never change state: tests using them may run in any order.
READER = "alice"
# Users reserved for flows that change state.
SUBMITTER = "bob"
TOKEN_USER = "carol"
ASKER = "dave"
# A user without any submission, to check the empty state.
NOBODY = "erin"

PASSWORDS = {
    name: name + "-password"
    for name in (READER, SUBMITTER, TOKEN_USER, ASKER, NOBODY)
}


@dataclass
class SeededData:
    contest_id: int
    contest_name: str
    task_name: str
    # Number of finished submissions of READER on the task.
    reader_submissions: int
    # Number of finished, not yet tokened submissions of TOKEN_USER.
    token_user_submissions: int


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _store_file(content: bytes) -> str:
    """Put content in the file store, and return its digest."""
    digest = hashlib.sha1(content).hexdigest()
    backend = DBBackend()
    fobj = backend.create_file(digest)
    if fobj is None:
        # The same content was already stored.
        return digest
    fobj.write(content)
    backend.commit_file(fobj, digest)
    return digest


def seed_database() -> SeededData:
    """Recreate the database and fill it with the test fixtures.

    Refuses to run on a database whose name does not end in "fortesting".

    """
    assert engine.url.database.endswith("fortesting"), (
        "The database name is not in the form '<name>fortesting' and "
        "this could mean that you're running tests on the wrong database. "
        "Aborting")
    drop_db()
    init_db()

    gen = DatabaseObjectGeneratorMixin
    session = Session()

    contest = gen.get_contest(
        name="browsertest",
        description=CONTEST_DESCRIPTION,
        languages=LANGUAGES,
        allow_questions=True,
        allow_registration=True,
        allow_user_tests=True,
        token_mode="infinite",
    )
    session.add(contest)

    task = gen.get_task(
        name=TASK_NAME,
        title=TASK_TITLE,
        contest=contest,
        num=0,
        submission_format=["sum.%l"],
        token_mode="infinite",
    )
    dataset = gen.get_dataset(
        task=task,
        description="Browser test dataset",
        autojudge=False,
        time_limit=1.0,
        memory_limit=256 * 1024 * 1024,
        task_type="Batch",
        task_type_parameters=["alone", ["", ""], "diff"],
        score_type="Sum",
        score_type_parameters=50,
    )
    task.active_dataset = dataset
    session.add(task)
    session.add(dataset)

    pdf = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n"
    session.add(Statement(task=task, digest=_store_file(pdf), language="en"))

    # A single public testcase gives the task a maximum score, which makes
    # CWS show the score column.
    session.add(Testcase(
        dataset=dataset, codename="1", public=True,
        input=_store_file(b"1 2\n"), output=_store_file(b"3\n")))

    pair_task = gen.get_task(
        name=PAIR_TASK_NAME,
        title="Two files",
        contest=contest,
        num=1,
        submission_format=["pair_a.%l", "pair_b.%l"],
        token_mode="infinite",
    )
    pair_dataset = gen.get_dataset(
        task=pair_task,
        description="Browser test dataset",
        autojudge=False,
        time_limit=1.0,
        memory_limit=256 * 1024 * 1024,
        task_type="Batch",
        task_type_parameters=["alone", ["", ""], "diff"],
        score_type="Sum",
        score_type_parameters=50,
    )
    pair_task.active_dataset = pair_dataset
    session.add(pair_task)
    session.add(pair_dataset)
    session.add(Statement(
        task=pair_task, digest=_store_file(pdf), language="en"))
    session.add(Testcase(
        dataset=pair_dataset, codename="1", public=True,
        input=_store_file(b"1 2\n"), output=_store_file(b"3\n")))

    users = {}
    participations = {}
    for name, password in PASSWORDS.items():
        user = gen.get_user(
            username=name,
            first_name=name.capitalize(),
            last_name="Tester",
            password=build_password(password),
        )
        users[name] = user
        participations[name] = gen.get_participation(
            user=user, contest=contest)
        session.add(participations[name])

    session.add(Announcement(
        contest=contest,
        subject=ANNOUNCEMENT_SUBJECT,
        text="Good luck to everyone.",
        timestamp=_now() - timedelta(hours=1)))
    session.add(Message(
        participation=participations[READER],
        subject=MESSAGE_SUBJECT,
        text="Please remember to read the rules.",
        timestamp=_now() - timedelta(hours=1)))
    session.add(Question(
        participation=participations[READER],
        subject=ANSWERED_QUESTION_SUBJECT,
        text="Can I assume the input is sorted?",
        question_timestamp=_now() - timedelta(hours=2),
        reply_timestamp=_now() - timedelta(hours=1),
        reply_subject="Re: " + ANSWERED_QUESTION_SUBJECT,
        reply_text=ANSWER_TEXT,
        ignored=False))

    source = _store_file(b"print(sum(map(int, input().split())))\n")

    def add_finished_submission(name: str, index: int):
        submission = gen.get_submission(
            task=task,
            participation=participations[name],
            language="Python 3 / CPython",
            timestamp=_now() - timedelta(minutes=30 - index),
            opaque_id=1000 * (1 + list(PASSWORDS).index(name)) + index,
        )
        session.add(submission)
        session.add(File(
            submission=submission, filename="sum.%l", digest=source))
        details = [{
            "idx": 1,
            "outcome": "Correct",
            "text": ["Output is correct"],
            "time": 0.01,
            "memory": 1024 * 1024,
        }]
        session.add(SubmissionResult(
            submission=submission,
            dataset=dataset,
            compilation_outcome="ok",
            compilation_text=["OK"],
            compilation_tries=1,
            evaluation_outcome="ok",
            evaluation_tries=1,
            score=50.0,
            score_details=details,
            public_score=50.0,
            public_score_details=details,
            ranking_score_details=["50"],
        ))
        return submission

    reader_submissions = 2
    for i in range(reader_submissions):
        add_finished_submission(READER, i)
    token_user_submissions = 2
    for i in range(token_user_submissions):
        add_finished_submission(TOKEN_USER, i)

    # A finished submission made of two files, to get the download menu.
    pair_submission = gen.get_submission(
        task=pair_task,
        participation=participations[READER],
        language="Python 3 / CPython",
        timestamp=_now() - timedelta(minutes=20),
        opaque_id=9000,
    )
    session.add(pair_submission)
    for name in ("pair_a.%l", "pair_b.%l"):
        session.add(File(
            submission=pair_submission, filename=name, digest=source))
    pair_details = [{
        "idx": 1,
        "outcome": "Correct",
        "text": ["Output is correct"],
        "time": 0.01,
        "memory": 1024 * 1024,
    }]
    session.add(SubmissionResult(
        submission=pair_submission,
        dataset=pair_dataset,
        compilation_outcome="ok",
        compilation_text=["OK"],
        compilation_tries=1,
        evaluation_outcome="ok",
        evaluation_tries=1,
        score=50.0,
        score_details=pair_details,
        public_score=50.0,
        public_score_details=pair_details,
        ranking_score_details=["50"],
    ))

    # Finished user tests: one with a single file, one with two files.
    test_input = _store_file(b"1 2\n")
    test_output = _store_file(b"3\n")
    for task_, dataset_, names in (
            (task, dataset, ["sum.%l"]),
            (pair_task, pair_dataset, ["pair_a.%l", "pair_b.%l"])):
        user_test = UserTest(
            participation=participations[READER],
            task=task_,
            timestamp=_now() - timedelta(minutes=10),
            language="Python 3 / CPython",
            input=test_input,
        )
        session.add(user_test)
        for name in names:
            session.add(UserTestFile(
                user_test=user_test, filename=name, digest=source))
        session.add(UserTestResult(
            user_test=user_test,
            dataset=dataset_,
            output=test_output,
            compilation_outcome="ok",
            compilation_text=["OK"],
            compilation_tries=1,
            evaluation_outcome="ok",
            evaluation_text=["Execution completed successfully"],
            evaluation_tries=1,
            execution_time=0.01,
            execution_memory=1024 * 1024,
        ))

    session.commit()
    result = SeededData(
        contest_id=contest.id,
        contest_name=contest.name,
        task_name=TASK_NAME,
        reader_submissions=reader_submissions,
        token_user_submissions=token_user_submissions,
    )
    session.close()
    return result
