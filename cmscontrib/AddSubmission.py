#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Utility to submit a solution for a user.

"""

import argparse
import logging
import sys

from cms import utf8_decoder, ServiceCoord
from cms.db import File, Participation, SessionGen, Submission, Task, User, \
    ask_for_contest
from cms.db.filecacher import FileCacher
from cms.grading.language import Language
from cms.grading.languagemanager import filename_to_language, get_language
from cms.io import RemoteServiceClient
from cmscommon.datetime import make_datetime


logger = logging.getLogger(__name__)


def maybe_send_notification(submission_id: int):
    """Non-blocking attempt to notify a running ES of the submission"""
    rs = RemoteServiceClient(ServiceCoord("EvaluationService", 0))
    rs.connect()
    rs.wait_for_connection(timeout=1)
    rs.new_submission(submission_id=submission_id)
    rs.disconnect()


def language_from_submitted_files(files: dict[str, str], contest_languages: list[Language]) -> Language | None:
    """Return the language inferred from the submitted files.

    files: dictionary mapping the expected filename to a path in
        the file system.

    return: the language inferred from the files.

    raise (ValueError): if different files point to different languages, or if
        it is impossible to extract the language from a file when it should be.

    """
    # TODO: deduplicate with the code in SubmitHandler.
    language = None
    for filename in files.keys():
        this_language = filename_to_language(files[filename], contest_languages)
        if this_language is None and ".%l" in filename:
            raise ValueError(
                "Cannot recognize language for file `%s'." % filename)

        if language is None:
            language = this_language
        elif this_language is not None and language != this_language:
            raise ValueError("Mixed-language submission detected.")
    return language


def add_submission(
    contest_id: int,
    username: str,
    task_name: str,
    timestamp: float,
    files: dict[str, str],
    given_language: str | None,
):
    file_cacher = FileCacher()
    with SessionGen() as session:

        participation: Participation | None = (
            session.query(Participation)
            .join(Participation.user)
            .filter(Participation.contest_id == contest_id)
            .filter(User.username == username)
            .first()
        )
        if participation is None:
            logging.critical("User `%s' does not exists or "
                             "does not participate in the contest.", username)
            return False
        task: Task | None = (
            session.query(Task)
            .filter(Task.contest_id == contest_id)
            .filter(Task.name == task_name)
            .first()
        )
        if task is None:
            logging.critical("Unable to find task `%s'.", task_name)
            return False

        elements = set(task.submission_format)

        for file_ in files:
            if file_ not in elements:
                logging.critical("File `%s' is not in the submission format "
                                 "for the task.", file_)
                return False

        if any(element not in files for element in elements):
            logger.warning("Not all files from the submission format were "
                           "provided.")

        # files is now a subset of elements.
        # We ensure we can infer a language if the task requires it.
        language = None
        need_lang = any(element.find(".%l") != -1 for element in elements)
        if need_lang:
            try:
                if given_language is not None:
                    language = get_language(given_language)
                else:
                    contest_languages = [
                        get_language(language)
                        for language in task.contest.languages
                    ]
                    language = language_from_submitted_files(files, contest_languages)
            except ValueError as e:
                logger.critical(e)
                return False
            if language is None:
                # This might happen in case not all files were provided.
                logger.critical("Unable to infer language from submission.")
                return False
        language_name = None if language is None else language.name

        # Store all files from the arguments, and obtain their digests..
        file_digests: dict[str, str] = {}
        try:
            for file_ in files:
                digest = file_cacher.put_file_from_path(
                    files[file_],
                    "Submission file %s sent by %s at %d."
                    % (file_, username, timestamp))
                file_digests[file_] = digest
        except Exception as e:
            logger.critical("Error while storing submission's file: %s.", e)
            return False

        # Create objects in the DB.

        submission = Submission(
            timestamp=make_datetime(timestamp),
            language=language_name,
            participation=participation,
            task=task,
            opaque_id=Submission.generate_opaque_id(session, participation.id)
        )
        for filename, digest in file_digests.items():
            session.add(File(filename, digest, submission=submission))
        session.add(submission)
        session.commit()
        maybe_send_notification(submission.id)

    return True


def main() -> int:
    """Parse arguments and launch process.

    return: exit code of the program.

    """
    parser = argparse.ArgumentParser(
        description="Adds a submission to a contest in CMS.")
    parser.add_argument("-c", "--contest-id", action="store", type=int,
                        help="id of contest where to add the submission")
    parser.add_argument("-f", "--file", action="append", type=utf8_decoder,
                        help="in the form <name>:<file>, where name is the "
                        "name as required by CMS, and file is the name of "
                        "the file in the filesystem - may be specified "
                        "multiple times", required=True)
    parser.add_argument("username", action="store", type=utf8_decoder,
                        help="user doing the submission")
    parser.add_argument("task_name", action="store", type=utf8_decoder,
                        help="name of task the submission is for")
    parser.add_argument("-t", "--timestamp", action="store", type=int,
                        help="timestamp of the submission in seconds from "
                        "epoch, e.g. `date +%%s` (now if not set)")
    parser.add_argument("-l", "--language",
                        help="programming language (e.g., 'C++17 / g++'), "
                        "default is to guess from file name extension. "
                        "It is also possible to specify languages not enabled "
                        "in the contest.")

    args = parser.parse_args()

    if args.contest_id is None:
        args.contest_id = ask_for_contest()

    if args.timestamp is None:
        import time
        args.timestamp = time.time()

    split_files: list[tuple[str, str]] = [
        file_.split(":", 1) for file_ in args.file]
    if any(len(file_) != 2 for file_ in split_files):
        parser.error("Invalid value for the file argument: format is "
                     "<name>:<file>.")
        return 1
    files: dict[str, str] = {}
    for name, filename in split_files:
        if name in files:
            parser.error("Duplicate assignment for file `%s'." % name)
            return 1
        files[name] = filename

    success = add_submission(contest_id=args.contest_id,
                             username=args.username,
                             task_name=args.task_name,
                             timestamp=args.timestamp,
                             files=files,
                             given_language=args.language)
    return 0 if success is True else 1


if __name__ == "__main__":
    sys.exit(main())
