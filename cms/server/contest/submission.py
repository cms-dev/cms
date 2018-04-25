#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

"""Submission-related helpers for CWS.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa
from six import iterkeys, iteritems

import io
import logging
import os.path
import pickle
from collections import namedtuple

from patoolib.util import PatoolError
from sqlalchemy import func, desc

from cms import config
from cms.db import Submission, Task, UserTest
from cms.grading.languagemanager import LANGUAGES, get_language
from cmscommon.archive import Archive


logger = logging.getLogger(__name__)


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


# Represents a file received through HTTP from an HTML form.
# codename (str|None): the name of the form field (in our case it's the
#   filename-with-%l).
# filename (str|None): the name the file had on the user's system.
# content (bytes): the data of the file.
ReceivedFile = namedtuple("ReceivedFile", ["codename", "filename", "content"])


class InvalidArchive(Exception):
    """Raised when the archive submitted by the user cannot be opened."""

    pass


def extract_files_from_archive(data):
    """Return the files contained in the given archive.

    Given the binary data of an archive in any of the formats supported
    by patool, extract its contents and return them in our format. The
    archive's contents must be a valid directory structure (i.e., its
    contents cannot have conflicting/duplicated paths) but the structure
    will be ignored and the files will be returned with their basename.

    data (bytes): the raw contents of the archive.

    return ([ReceivedFile]): the files contained in the archive, with
        their filename filled in but their codename set to None.

    raise (InvalidArchive): if the data doesn't seem to encode an
        archive, its contents are invalid, or other issues.

    """
    archive = Archive.from_raw_data(data)

    if archive is None:
        raise InvalidArchive()

    result = list()

    try:
        archive.unpack()
        for name in archive.namelist():
            with archive.read(name) as f:
                result.append(
                    ReceivedFile(None, os.path.basename(name), f.read()))

    # When dropping py2, replace EnvironmentError by OSError.
    except (PatoolError, EnvironmentError):
        raise InvalidArchive()

    finally:
        archive.cleanup()

    return result


def extract_files_from_tornado(tornado_files):
    """Transform some files as received by Tornado into our format.

    Given the files as provided by Tornado on the HTTPServerRequest's
    files attribute, produce a result in our own format. Also, if the
    files look like they consist of just a compressed archive, extract
    it and return its contents instead.

    tornado_files ({str: [tornado.httputil.HTTPFile]}): a bunch of
        files, in Tornado's format.

    return ([ReceivedFile]): the same bunch of files, in our format
        (except if it was an archive: then it's the archive's contents).

    raise (InvalidArchive): if there are issues extracting the archive.

    """
    if len(tornado_files) == 1 and "submission" in tornado_files \
            and len(tornado_files["submission"]) == 1:
        return extract_files_from_archive(tornado_files["submission"][0].body)

    result = list()
    for codename, files in iteritems(tornado_files):
        for f in files:
            result.append(ReceivedFile(codename, f.filename, f.body))
    return result


class InvalidFiles(Exception):
    """Raised when the submitted files can't be matched to the format."""

    pass


def _match_filename(filename, language, element):
    """Ensure the filename is entirely compatible with the element.

    Return whether the filename matches the element, including having an
    appropriate value for the language-specific extension (if present)
    for the given language.

    filename (str): the filename.
    language (Language|None): the language.
    element (str): the element of the submission format.

    return (bool): whether there's a match.

    """
    if not element.endswith(".%l"):
        return filename == element
    if language is None:
        raise ValueError("language not given but submission format requires it")
    base = os.path.splitext(element)[0]
    return any(filename == base + ext for ext in language.source_extensions)


def _match_extension(filename, language, element):
    """Ensure filename is compatible with element w.r.t. the extension.

    Return whether the filename (if given) matches the language-specific
    extension of the element (if present) for the given language.

    filename (str|None): the filename.
    language (Language|None): the language.
    element (str): the element of the submission format.

    return (bool): whether there's a match.

    """
    if filename is None or not element.endswith(".%l"):
        return True
    if language is None:
        raise ValueError("language not given but submission format requires it")
    return any(filename.endswith(ext) for ext in language.source_extensions)


def _match_file(codename, filename, language, submission_format):
    """Figure out what element of the submission format a file is for.

    Return our best guess for which element of the submission format
    the submitted file was meant for. A match occurs when:
    - the codename isn't given and the filename matches an element of
      the submission format when we replace the latter's trailing ".%l"
      (if any) with one of the source extensions of the language;
    - the codename matches exactly and if it ends in ".%l" the filename
      (if given) ends in any of the extensions of the language.

    codename (str|None): the filename-with-%l, if provided.
    filename (str|None): the name the contestant gave to the file, if
        provided.
    language (Language|None): the language to match against.
    submission_format ({str}): the task's submission format.

    return (str): the element of the submission format matched by the
        file.

    raise (InvalidFiles): if there's the slightest uncertainty or
        ambiguity.

    """
    if codename is None and filename is None:
        raise InvalidFiles("need at least one of codename and filename")

    # If no codename is given we guess it, by attempting a match of the
    # filename against all codenames. We claim victory if there is only
    # one hit.
    if codename is None:
        candidate_elements = {element for element in submission_format
                              if _match_filename(filename, language, element)}
        if len(candidate_elements) == 1:
            return candidate_elements.pop()

    # If, on the other hand, the codename is given then it needs to
    # exactly match an element of the format and, as a safety measure,
    # the filename needs to match too at least with respect to the
    # extension.
    elif codename in submission_format \
            and _match_extension(filename, language, codename):
        return codename

    raise InvalidFiles(
        "file %r/%r doesn't unambiguously match the submission format"
        % (codename, filename))


def _match_files(given_files, language, submission_format):
    """Fit the given files into the given submission format.

    Figure out, for all of the given files, which element of the
    submission format they are for.

    given_files ([ReceivedFile]): the files, as received from the user.
    language (Language|None): the language to match against.
    submission_format ({str}): the set of filenames-with-%l that the
        contestants are required to submit.

    return ({str: bytes}): the mapping from filenames-with-%l to
        contents.

    raise (InvalidFiles): if there's the slightest uncertainty or
        ambiguity.

    """
    files = dict()

    for codename, filename, content in given_files:
        codename = _match_file(codename, filename, language, submission_format)
        if codename in files:
            raise InvalidFiles(
                "two files match the same element %r of the submission format"
                % codename)
        files[codename] = content

    return files


class InvalidFilesOrLanguage(Exception):
    """Raised when the submitted files or given languages don't make sense."""

    pass


def match_files_and_languages(given_files, given_language_name,
                              submission_format, allowed_language_names):
    """Figure out what the given files are and which language they're in.

    Take a set of files and a set of languages that these files are
    claimed to be in and try to make sense of it. That is, the provided
    information may come from sloppy, untrusted or adversarial sources
    and this function's duty is to parse and validate it to ensure it
    conforms to the expected format for a submission. Such a format is
    given as a set of desired codenames (i.e., filenames with language
    specific extensions replaced by %l) and a set of allowed languages
    (if such a limitation is in place). The function tries to be lenient
    as long as it believes the contestant's intentions are clear.

    The function first figures out which set of candidate languages the
    submission could be in, then tries to match the data against all of
    them. If exactly one matches then that match is returned. The
    languages that are considered are the ones provided by the user (if
    they exist and are allowed) or, if not provided, all languages
    (restricted to the allowed ones). If the submission format contains
    no element ending in ".%l" then the None language is always used
    (the rest of the arguments still needs to make sense though).
    Matching a language is done using the match_files function.

    given_files ([ReceivedFile]): the submitted files.
    given_language_name (str|None): the language, usually provided by
        the contestant, which the submitted files are in (None means
        this information isn't available and we should guess it).
    submission_format ({str}): the codenames that the submitted files
        should be matched to.
    allowed_language_names ([str]|None): the languages that the result
        is allowed to have (None means no limitation).

    return ({str: bytes}, Language|None): the mapping from codenames to
        content, and the language of the submission (with None meaning
        that no language is needed as the format was language-agnostic).

    raise (InvalidFilesOrLanguages): if issues arise when finding a
        match.

    """
    if len(given_files) == 0:
        raise InvalidFilesOrLanguage("no files given")

    # If the submission format is language-agnostic the only "language"
    # that makes sense is None, and if the caller thought differently we
    # let them know.
    if not any(element.endswith(".%l") for element in submission_format):
        if given_language_name is not None:
            raise InvalidFilesOrLanguage(
                "a language %r is given when not needed" % given_language_name)
        candidate_languages = {None}

    # If a language is required and the caller told us which one to use
    # we follow their indication, provided it exists and is allowed.
    elif given_language_name is not None:
        try:
            language = get_language(given_language_name)
        except KeyError:
            raise InvalidFilesOrLanguage(
                "the given language %r isn't a language" % given_language_name)

        if allowed_language_names is not None \
                and language.name not in allowed_language_names:
            raise InvalidFilesOrLanguage(
                "the given language %r isn't allowed" % given_language_name)

        candidate_languages = {language}

    # If a language is needed but the caller didn't provide any we try
    # to auto-detect it by guessing among all allowed languages.
    else:
        if allowed_language_names is None:
            candidate_languages = set(LANGUAGES)
        else:
            candidate_languages = set()
            for language_name in allowed_language_names:
                try:
                    language = get_language(language_name)
                except KeyError:
                    pass
                else:
                    candidate_languages.add(language)

    matched_files_by_language = dict()
    invalidity_reasons = list()
    for language in candidate_languages:
        try:
            matched_files_by_language[language] = \
                _match_files(given_files, language, submission_format)
        except InvalidFiles as err:
            invalidity_reasons.append("%r: %s" % (
                language.name if language is not None else None, err))

    if len(matched_files_by_language) == 0:
        raise InvalidFilesOrLanguage(
            "there isn't any language that matches all the files:\n%s"
            % (";\n".join(invalidity_reasons)))
    elif len(matched_files_by_language) > 1:
        raise InvalidFilesOrLanguage(
            "there is more than one language that matches all the files: %r"
            % set(iterkeys(matched_files_by_language)))

    language, files = matched_files_by_language.popitem()

    return files, language


def fetch_file_digests_from_previous_submission(
        sql_session, participation, task, language, codenames, cls=Submission):
    """Retrieve digests of files with given codenames from latest submission.

    Get the most recent submission of the given contestant on the given
    task and, if it is of the given language, return the digests of its
    files that correspond to the given codenames. In case of UserTests
    lookup also among the user-provided managers.

    sql_session (Session): the SQLAlchemy session to use.
    participation (Participation): the participation whose submissions
        should be considered.
    task (Task): the task whose submissions should be considered.
    language (Language|None): the language the submission has to be in
        for the lookup to be allowed.
    codenames ({str}): the filenames-with-%l that need to be retrieved.
    cls (type): if the UserTest class is given, lookup user tests rather
        than submissions.

    return ({str: str}): for every codename, the digest of the file of
        that codename in the previous submission; if the previous
        submission didn't have that file it won't be included in the
        result; if there is no previous submission or if it isn't in the
        desired language, return an empty result.

    """
    # FIXME Instead of taking the latest submission *if* it is of the
    # right language, take the latest *among* those of that language.
    latest_submission = get_latest_submission(
        sql_session, participation, task=task, cls=cls)

    language_name = language.name if language is not None else None
    if latest_submission is None or language_name != latest_submission.language:
        return dict()

    digests = dict()
    for codename in codenames:
        # The expected behavior of this code is undefined when a task's
        # submission format, its task type's user_managers and {"input"}
        # are not pairwise disjoint sets. That is not supposed to happen
        # and it would probably already create issues upon submission.
        if codename in latest_submission.files:
            digests[codename] = latest_submission.files[codename].digest
        elif cls is UserTest:
            if codename == "input":
                digests["input"] = latest_submission.input
            else:
                if codename.endswith(".%l"):
                    if language is None:
                        raise ValueError("language not given when submission "
                                         "format requires it")
                    filename = (os.path.splitext(codename)[0]
                                + language.source_extension)
                else:
                    filename = codename
                if filename in latest_submission.managers:
                    digests[codename] = \
                        latest_submission.managers[filename].digest

    return digests


class StorageFailed(Exception):
    pass


def store_local_copy(path, participation, task, timestamp, files):
    """Write the files plus some metadata to a local backup

    Add a new file to the local backup storage (rooted in the given
    directory), containing the data of the given files and some details
    about the user, the task and the contest of the submission. The
    files are organized in directories (one for each contestant, named
    as their usernames) and their names are the dates and times of the
    submissions. The files' contents are pickle-encoded tuples whose
    first three elements are the contest ID, the user ID and the task ID
    and whose fourth element is a dict describing the files.

    path (str): the directory in which to build the archive; it will be
        created if it doesn't exist; if it contains `%s` it will be
        replaced with the data_dir specified in the config.
    participation (Participation): the participation that submitted.
    task (Task): the task on which they submitted.
    timestamp (datetime): when the submission happened.
    files ({str: bytes}): the files that were sent in: the keys are the
        codenames (filenames-with-%l), the values are the contents.

    raise (StorageFailed): in case of problems.

    """
    try:
        path = os.path.join(path.replace("%s", config.data_dir),
                            participation.user.username)
        if not os.path.exists(path):
            os.makedirs(path)
        with io.open(os.path.join(path, "%s" % timestamp), "wb") as f:
            pickle.dump((participation.contest.id, participation.user.id,
                         task.id, files), f)
    except EnvironmentError as e:
        raise StorageFailed("Failed to store local copy of submission: %s", e)
