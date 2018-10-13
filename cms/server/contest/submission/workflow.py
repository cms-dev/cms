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

"""Procedures used by CWS to accept submissions and user tests."""

import logging

from cms import config
from cms.db import Submission, File, UserTestManager, UserTestFile, UserTest
from cmscommon.datetime import make_timestamp
from .check import check_max_number, check_min_interval
from .file_matching import InvalidFilesOrLanguage, match_files_and_language
from .file_retrieval import InvalidArchive, extract_files_from_tornado
from .utils import fetch_file_digests_from_previous_submission, StorageFailed, \
    store_local_copy


logger = logging.getLogger(__name__)


# Dummy function to mark translatable strings.
def N_(msgid):
    return msgid


class UnacceptableSubmission(Exception):
    def __init__(self, subject, text):
        super().__init__("%s: %s" % (subject, text))
        self.subject = subject
        self.text = text


def accept_submission(sql_session, file_cacher, participation, task, timestamp,
                      tornado_files, language_name, official):
    """Process a contestant's request to submit a submission.

    Parse and validate the data that a contestant sent for a submission
    and, if all checks and operations succeed, add the result to the
    database and return it.

    sql_session (Session): the DB session to use to fetch and add data.
    file_cacher (FileCacher): the file cacher to use to store the files.
    participation (Participation): the contestant who is submitting.
    task (Task): the task on which they are submitting.
    timestamp (datetime): the moment in time they submitted at.
    tornado_files ({str: [tornado.httputil.HTTPFile]}): the files they
        sent in.
    language_name (str|None): the language they declared their files are
        in (None means unknown and thus auto-detect).
    official (bool): whether the submission was sent in during a regular
        contest phase (and should be counted towards the score/rank) or
        during the analysis mode.

    return (Submission): the resulting submission, if all went well.

    raise (UnacceptableSubmission): if the contestant wasn't allowed to
        hand in a submission, if the provided data was invalid, if there
        were critical failures in the process.

    """
    contest = participation.contest
    assert task.contest is contest

    # Check whether the contestant is allowed to submit.

    if not check_max_number(sql_session, contest.max_submission_number,
                            participation, contest=contest):
        raise UnacceptableSubmission(
            N_("Too many submissions!"),
            N_("You have reached the maximum limit of "
               "at most %d submissions among all tasks.") %
            contest.max_submission_number)

    if not check_max_number(sql_session, task.max_submission_number,
                            participation, task=task):
        raise UnacceptableSubmission(
            N_("Too many submissions!"),
            N_("You have reached the maximum limit of "
               "at most %d submissions on this task.") %
            task.max_submission_number)

    if not check_min_interval(sql_session, contest.min_submission_interval,
                              timestamp, participation, contest=contest):
        raise UnacceptableSubmission(
            N_("Submissions too frequent!"),
            N_("Among all tasks, you can submit again "
               "after %d seconds from last submission.") %
            contest.min_submission_interval.total_seconds())

    if not check_min_interval(sql_session, task.min_submission_interval,
                              timestamp, participation, task=task):
        raise UnacceptableSubmission(
            N_("Submissions too frequent!"),
            N_("For this task, you can submit again "
               "after %d seconds from last submission.") %
            task.min_submission_interval.total_seconds())

    # Process the data we received and ensure it's valid.

    required_codenames = set(task.submission_format)

    try:
        received_files = extract_files_from_tornado(tornado_files)
    except InvalidArchive:
        raise UnacceptableSubmission(
            N_("Invalid archive format!"),
            N_("The submitted archive could not be opened."))

    try:
        files, language = match_files_and_language(
            received_files, language_name, required_codenames,
            contest.languages)
    except InvalidFilesOrLanguage:
        raise UnacceptableSubmission(
            N_("Invalid submission format!"),
            N_("Please select the correct files."))

    digests = dict()
    missing_codenames = required_codenames.difference(files.keys())
    if missing_codenames:
        if task.active_dataset.task_type_object.ALLOW_PARTIAL_SUBMISSION:
            digests = fetch_file_digests_from_previous_submission(
                sql_session, participation, task, language,
                missing_codenames)
        else:
            raise UnacceptableSubmission(
                N_("Invalid submission format!"),
                N_("Please select the correct files."))

    if any(len(content) > config.max_submission_length
           for content in files.values()):
        raise UnacceptableSubmission(
            N_("Submission too big!"),
            N_("Each source file must be at most %d bytes long.") %
            config.max_submission_length)

    # All checks done, submission accepted.

    if config.submit_local_copy:
        try:
            store_local_copy(config.submit_local_copy_path, participation,
                             task, timestamp, files)
        except StorageFailed:
            logger.error("Submission local copy failed.", exc_info=True)

    # We now have to send all the files to the destination...
    try:
        for codename, content in files.items():
            digest = file_cacher.put_file_content(
                content,
                "Submission file %s sent by %s at %d." % (
                    codename, participation.user.username,
                    make_timestamp(timestamp)))
            digests[codename] = digest

    # In case of error, the server aborts the submission
    except Exception as error:
        logger.error("Storage failed! %s", error)
        raise UnacceptableSubmission(
            N_("Submission storage failed!"),
            N_("Please try again."))

    # All the files are stored, ready to submit!
    logger.info("All files stored for submission sent by %s",
                participation.user.username)

    submission = Submission(
        timestamp=timestamp,
        language=language.name if language is not None else None,
        task=task,
        participation=participation,
        official=official)
    sql_session.add(submission)

    for codename, digest in digests.items():
        sql_session.add(File(
            filename=codename, digest=digest, submission=submission))

    return submission


class TestingNotAllowed(Exception):
    pass


class UnacceptableUserTest(Exception):
    def __init__(self, subject, text):
        super().__init__("%s: %s" % (subject, text))
        self.subject = subject
        self.text = text


def accept_user_test(sql_session, file_cacher, participation, task, timestamp,
                     tornado_files, language_name):
    """Process a contestant's request to submit a user test.

    sql_session (Session): the DB session to use to fetch and add data.
    file_cacher (FileCacher): the file cacher to use to store the files.
    participation (Participation): the contestant who is submitting.
    task (Task): the task on which they are submitting.
    timestamp (datetime): the moment in time they submitted at.
    tornado_files ({str: [tornado.httputil.HTTPFile]}): the files they
        sent in.
    language_name (str|None): the language they declared their files are
        in (None means unknown and thus auto-detect).

    return (UserTest): the resulting user test, if all went well.

    raise (TestingNotAllowed): if the task doesn't allow for any tests.
    raise (UnacceptableUserTest): if the contestant wasn't allowed to
        hand in a user test, if the provided data was invalid, if there
        were critical failures in the process.

    """
    contest = participation.contest
    assert task.contest is contest

    # Check whether the task is testable.

    task_type = task.active_dataset.task_type_object
    if not task_type.testable:
        raise TestingNotAllowed()

    # Check whether the contestant is allowed to send a test.

    if not check_max_number(sql_session, contest.max_user_test_number,
                            participation, contest=contest, cls=UserTest):
        raise UnacceptableUserTest(
            N_("Too many tests!"),
            N_("You have reached the maximum limit of "
               "at most %d tests among all tasks.") %
            contest.max_user_test_number)

    if not check_max_number(sql_session, task.max_user_test_number,
                            participation, task=task, cls=UserTest):
        raise UnacceptableUserTest(
            N_("Too many tests!"),
            N_("You have reached the maximum limit of "
               "at most %d tests on this task.") %
            task.max_user_test_number)

    if not check_min_interval(sql_session, contest.min_user_test_interval,
                              timestamp, participation, contest=contest,
                              cls=UserTest):
        raise UnacceptableUserTest(
            N_("Tests too frequent!"),
            N_("Among all tasks, you can test again "
               "after %d seconds from last test.") %
            contest.min_user_test_interval.total_seconds())

    if not check_min_interval(sql_session, task.min_user_test_interval,
                              timestamp, participation, task=task,
                              cls=UserTest):
        raise UnacceptableUserTest(
            N_("Tests too frequent!"),
            N_("For this task, you can test again "
               "after %d seconds from last test.") %
            task.min_user_test_interval.total_seconds())

    # Process the data we received and ensure it's valid.

    required_codenames = set(task.submission_format)
    required_codenames.update(task_type.get_user_managers())
    required_codenames.add("input")

    try:
        received_files = extract_files_from_tornado(tornado_files)
    except InvalidArchive:
        raise UnacceptableUserTest(
            N_("Invalid archive format!"),
            N_("The submitted archive could not be opened."))

    try:
        files, language = match_files_and_language(
            received_files, language_name, required_codenames,
            contest.languages)
    except InvalidFilesOrLanguage:
        raise UnacceptableUserTest(
            N_("Invalid test format!"),
            N_("Please select the correct files."))

    digests = dict()
    missing_codenames = required_codenames.difference(files.keys())
    if missing_codenames:
        if task.active_dataset.task_type_object.ALLOW_PARTIAL_SUBMISSION:
            digests = fetch_file_digests_from_previous_submission(
                sql_session, participation, task, language,
                missing_codenames, cls=UserTest)
        else:
            raise UnacceptableUserTest(
                N_("Invalid test format!"),
                N_("Please select the correct files."))

    if "input" not in files and "input" not in digests:
        raise UnacceptableUserTest(
            N_("Invalid test format!"),
            N_("Please select the correct files."))

    if any(len(content) > config.max_submission_length
           for codename, content in files.items()
           if codename != "input"):
        raise UnacceptableUserTest(
            N_("Test too big!"),
            N_("Each source file must be at most %d bytes long.") %
            config.max_submission_length)
    if "input" in files and len(files["input"]) > config.max_input_length:
        raise UnacceptableUserTest(
            N_("Input too big!"),
            N_("The input file must be at most %d bytes long.") %
            config.max_input_length)

    # All checks done, submission accepted.

    if config.tests_local_copy:
        try:
            store_local_copy(config.tests_local_copy_path, participation, task,
                             timestamp, files)
        except StorageFailed:
            logger.error("Test local copy failed.", exc_info=True)

    # We now have to send all the files to the destination...
    try:
        for codename, content in files.items():
            digest = file_cacher.put_file_content(
                content,
                "Test file %s sent by %s at %d." % (
                    codename, participation.user.username,
                    make_timestamp(timestamp)))
            digests[codename] = digest

    # In case of error, the server aborts the submission
    except Exception as error:
        logger.error("Storage failed! %s", error)
        raise UnacceptableUserTest(
            N_("Test storage failed!"),
            N_("Please try again."))

    # All the files are stored, ready to submit!
    logger.info("All files stored for test sent by %s",
                participation.user.username)

    user_test = UserTest(
        timestamp=timestamp,
        language=language.name if language is not None else None,
        input=digests["input"],
        participation=participation,
        task=task)
    sql_session.add(user_test)

    for codename, digest in digests.items():
        if codename == "input":
            continue
        if codename in task.submission_format:
            sql_session.add(UserTestFile(
                filename=codename, digest=digest, user_test=user_test))
        else:  # codename in task_type.get_user_managers()
            if language is not None:
                extension = language.source_extension
                filename = codename.replace(".%l", extension)
            else:
                filename = codename
            sql_session.add(UserTestManager(
                filename=filename, digest=digest, user_test=user_test))

    return user_test
