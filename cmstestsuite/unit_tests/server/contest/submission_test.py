#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
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

"""Tests for submission functions.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *
from future.builtins import *
import six
from six import iteritems

import io
import os
import stat
import tarfile
import unittest
import zipfile
from collections import namedtuple
from datetime import timedelta

from mock import call, patch, MagicMock

# Needs to be first to allow for monkey patching the DB connection string.
from cmstestsuite.unit_tests.databasemixin import DatabaseMixin

from cms import config
from cms.db import Submission, UserTest
from cms.server.contest.submission import get_submission_count, \
    check_max_number, get_latest_submission, check_min_interval, \
    ReceivedFile, InvalidArchive, extract_files_from_archive, \
    extract_files_from_tornado, InvalidFilesOrLanguage, \
    match_files_and_languages, fetch_file_digests_from_previous_submission, \
    StorageFailed, store_local_copy
from cmscommon.datetime import make_datetime
from cmstestsuite.unit_tests.filesystemmixin import FileSystemMixin
from cmstestsuite.unit_tests.testidgenerator import unique_digest, \
    unique_unicode_id


class TestGetSubmissionCount(DatabaseMixin, unittest.TestCase):

    def setUp(self):
        super(TestGetSubmissionCount, self).setUp()
        self.contest = self.add_contest()
        self.task1 = self.add_task(contest=self.contest)
        self.task2 = self.add_task(contest=self.contest)
        self.participation = self.add_participation(contest=self.contest)

    def call(self, participation=None, **kwargs):
        if participation is None:
            participation = self.participation
        return get_submission_count(self.session, participation, **kwargs)

    def test_bad_arguments(self):
        # Needs at least one of contest or task.
        with self.assertRaises(ValueError):
            self.call()
        # If both, the task's contest cannot be None.
        other_task = self.add_task()
        with self.assertRaises(ValueError):
            self.call(contest=self.contest, task=other_task)
        # And cannot be another contest.
        other_contest = self.add_contest()
        other_task.contest = other_contest
        with self.assertRaises(ValueError):
            self.call(contest=self.contest, task=other_task)

    def test_count_task(self):
        # No submissions.
        self.assertEqual(self.call(task=self.task1), 0)

        # One submission.
        s = self.add_submission(task=self.task1,
                                participation=self.participation)
        self.assertEqual(self.call(task=self.task1), 1)

        # More than one submission.
        self.add_submission(task=self.task1, participation=self.participation)
        self.assertEqual(self.call(task=self.task1), 2)

        # Doesn't mix submissions for different tasks.
        self.assertEqual(self.call(task=self.task2), 0)

        # Doesn't mix submissions for different users.
        other_participation = self.add_participation(contest=self.contest)
        self.assertEqual(self.call(participation=other_participation,
                                   task=self.task1), 0)

        # Doesn't mix submissions with user tests.
        self.assertEqual(self.call(task=self.task1, cls=UserTest), 0)

        # Isn't influenced by submission results.
        d1 = self.add_dataset(task=self.task1)
        d2 = self.add_dataset(task=self.task1)
        self.add_submission_result(submission=s, dataset=d1)
        self.add_submission_result(submission=s, dataset=d2)
        self.assertEqual(self.call(task=self.task1), 2)

    def test_count_contest(self):
        # No submissions.
        self.assertEqual(self.call(contest=self.contest), 0)

        # One submission.
        self.add_submission(task=self.task1, participation=self.participation)
        self.assertEqual(self.call(contest=self.contest), 1)

        # Another one, on a different task.
        self.add_submission(task=self.task2, participation=self.participation)
        self.assertEqual(self.call(contest=self.contest), 2)

        # Back to the first task.
        self.add_submission(task=self.task1, participation=self.participation)
        self.assertEqual(self.call(contest=self.contest), 3)

        # Doesn't mix submissions for different contests.
        other_contest = self.add_contest()
        self.assertEqual(self.call(contest=other_contest), 0)

        # Doesn't mix submissions for different users.
        other_participation = self.add_participation(contest=self.contest)
        self.assertEqual(self.call(participation=other_participation,
                                   contest=self.contest), 0)

        # Doesn't mix submissions with user tests.
        self.assertEqual(self.call(contest=self.contest, cls=UserTest), 0)

    def test_user_tests(self):
        # No user tests.
        self.assertEqual(self.call(contest=self.contest, cls=UserTest), 0)
        self.assertEqual(self.call(task=self.task1, cls=UserTest), 0)
        self.assertEqual(self.call(task=self.task2, cls=UserTest), 0)

        # One user test.
        self.add_user_test(task=self.task1, participation=self.participation)
        self.assertEqual(self.call(contest=self.contest, cls=UserTest), 1)
        self.assertEqual(self.call(task=self.task1, cls=UserTest), 1)
        self.assertEqual(self.call(task=self.task2, cls=UserTest), 0)

        # Another user test, on a different task.
        self.add_user_test(task=self.task2, participation=self.participation)
        self.assertEqual(self.call(contest=self.contest, cls=UserTest), 2)
        self.assertEqual(self.call(task=self.task1, cls=UserTest), 1)
        self.assertEqual(self.call(task=self.task2, cls=UserTest), 1)

        # Doesn't mix user tests with submissions.
        self.assertEqual(self.call(contest=self.contest), 0)
        self.assertEqual(self.call(task=self.task1), 0)
        self.assertEqual(self.call(task=self.task2), 0)


class TestCheckMaxNumber(DatabaseMixin, unittest.TestCase):

    def setUp(self):
        super(TestCheckMaxNumber, self).setUp()

        patcher = patch("cms.server.contest.submission.get_submission_count")
        self.get_submission_count = patcher.start()
        self.addCleanup(patcher.stop)
        self.calls = list()

        self.contest = self.add_contest()
        self.task = self.add_task(contest=self.contest)
        self.participation = self.add_participation(unrestricted=False,
                                                    contest=self.contest)

    def call(self, max_number, **kwargs):
        res = check_max_number(
            self.session, max_number, self.participation, **kwargs)
        kwargs.setdefault("contest", None)
        kwargs.setdefault("task", None)
        kwargs.setdefault("cls", Submission)
        self.calls.append(call(self.session, self.participation, **kwargs))
        return res

    def test_no_limit(self):
        self.get_submission_count.return_value = 5
        # Test different arguments to ensure they don't cause issues.
        self.assertTrue(self.call(None))
        self.assertTrue(self.call(None, contest=self.contest))
        self.assertTrue(self.call(None, task=self.task))
        self.assertTrue(self.call(None, contest=self.contest, task=self.task))
        # Having calls signals an inefficiency.
        self.get_submission_count.assert_not_called()

    def test_limit(self):
        self.get_submission_count.return_value = 5
        # Test different arguments to ensure they are passed to the call.
        self.assertFalse(self.call(0, contest=self.contest))
        self.assertFalse(self.call(3, task=self.task))
        self.assertFalse(self.call(5, contest=self.contest, task=self.task))
        self.assertTrue(self.call(6, contest=self.contest, cls=UserTest))
        self.assertTrue(self.call(9, task=self.task, cls=UserTest))
        # Arguments should have been passed unchanged.
        self.get_submission_count.assert_has_calls(self.calls)

    def test_limit_unrestricted(self):
        # Unrestricted users have no limit enforced.
        self.participation.unrestricted = True
        self.get_submission_count.return_value = 5
        # Test different arguments to ensure they don't cause issues.
        self.assertTrue(self.call(0, contest=self.contest))
        self.assertTrue(self.call(3, task=self.task))
        self.assertTrue(self.call(5, contest=self.contest, task=self.task))
        self.assertTrue(self.call(6, contest=self.contest, cls=UserTest))
        self.assertTrue(self.call(9, task=self.task, cls=UserTest))
        # Having calls signals an inefficiency.
        self.get_submission_count.assert_not_called()


class TestGetLatestSubmission(DatabaseMixin, unittest.TestCase):

    def setUp(self):
        super(TestGetLatestSubmission, self).setUp()
        self.contest = self.add_contest()
        self.task1 = self.add_task(contest=self.contest)
        self.task2 = self.add_task(contest=self.contest)
        self.participation = self.add_participation(contest=self.contest)
        self.timestamp = make_datetime()

    def at(self, seconds):
        return self.timestamp + timedelta(seconds=seconds)

    def call(self, participation=None, **kwargs):
        if participation is None:
            participation = self.participation
        return get_latest_submission(self.session, participation, **kwargs)

    def test_bad_arguments(self):
        # Needs at least one of contest or task.
        with self.assertRaises(ValueError):
            self.call()
        # If both, the task's contest cannot be None.
        other_task = self.add_task()
        with self.assertRaises(ValueError):
            self.call(contest=self.contest, task=other_task)
        # And cannot be another contest.
        other_contest = self.add_contest()
        other_task.contest = other_contest
        with self.assertRaises(ValueError):
            self.call(contest=self.contest, task=other_task)

    def test_retrieve_task(self):
        # No submissions.
        self.assertIsNone(self.call(task=self.task1))

        # One submission.
        s1 = self.add_submission(timestamp=self.at(0), task=self.task1,
                                 participation=self.participation)
        self.assertIs(self.call(task=self.task1), s1)

        # More than one submission.
        s2 = self.add_submission(timestamp=self.at(2), task=self.task1,
                                 participation=self.participation)
        self.assertIs(self.call(task=self.task1), s2)

        # They are sorted by timestamp, not by insertion order (i.e., by id).
        self.add_submission(timestamp=self.at(1), task=self.task1,
                            participation=self.participation)
        self.assertIs(self.call(task=self.task1), s2)

        # Doesn't mix submissions for different tasks.
        self.assertIsNone(self.call(task=self.task2))

        # Doesn't mix submissions for different users.
        other_participation = self.add_participation(contest=self.contest)
        self.assertIsNone(self.call(participation=other_participation,
                                    task=self.task1))

        # Doesn't mix submissions with user tests.
        self.assertIsNone(self.call(task=self.task1, cls=UserTest))

    def test_retrieve_contest(self):
        # No submissions.
        self.assertIsNone(self.call(contest=self.contest))

        # One submission.
        s1 = self.add_submission(timestamp=self.at(2), task=self.task1,
                                 participation=self.participation)
        self.assertIs(self.call(contest=self.contest), s1)

        # Another one, on a different task.
        s2 = self.add_submission(timestamp=self.at(3), task=self.task2,
                                 participation=self.participation)
        self.assertIs(self.call(contest=self.contest), s2)

        # Back to the first task, but at an earlier time.
        self.add_submission(timestamp=self.at(1), task=self.task1,
                            participation=self.participation)
        self.assertIs(self.call(contest=self.contest), s2)

        # Doesn't mix submissions for different contests.
        other_contest = self.add_contest()
        self.assertIsNone(self.call(contest=other_contest))

        # Doesn't mix submissions for different users.
        other_participation = self.add_participation(contest=self.contest)
        self.assertIsNone(self.call(participation=other_participation,
                                    contest=self.contest))

        # Doesn't mix submissions with user tests.
        self.assertIsNone(self.call(contest=self.contest, cls=UserTest))

    def test_user_tests(self):
        # No user tests.
        self.assertIsNone(self.call(contest=self.contest, cls=UserTest))
        self.assertIsNone(self.call(task=self.task1, cls=UserTest))
        self.assertIsNone(self.call(task=self.task2, cls=UserTest))

        # One user test.
        s1 = self.add_user_test(timestamp=self.at(1), task=self.task1,
                                participation=self.participation)
        self.assertIs(self.call(contest=self.contest, cls=UserTest), s1)
        self.assertIs(self.call(task=self.task1, cls=UserTest), s1)
        self.assertIsNone(self.call(task=self.task2, cls=UserTest))

        # Another user test, on a different task.
        s2 = self.add_user_test(timestamp=self.at(2), task=self.task2,
                                participation=self.participation)
        self.assertIs(self.call(contest=self.contest, cls=UserTest), s2)
        self.assertIs(self.call(task=self.task1, cls=UserTest), s1)
        self.assertIs(self.call(task=self.task2, cls=UserTest), s2)

        # Doesn't mix user tests with submissions.
        self.assertIsNone(self.call(contest=self.contest))
        self.assertIsNone(self.call(task=self.task1))
        self.assertIsNone(self.call(task=self.task2))


class TestCheckMinInterval(DatabaseMixin, unittest.TestCase):

    def setUp(self):
        super(TestCheckMinInterval, self).setUp()

        patcher = patch("cms.server.contest.submission.get_latest_submission")
        self.get_latest_submission = patcher.start()
        self.addCleanup(patcher.stop)
        self.calls = list()

        self.contest = self.add_contest()
        self.task = self.add_task(contest=self.contest)
        self.participation = self.add_participation(unrestricted=False,
                                                    contest=self.contest)

        self.timestamp = make_datetime()

    def at(self, seconds):
        return self.timestamp + timedelta(seconds=seconds)

    def call(self, min_interval, timestamp, **kwargs):
        res = check_min_interval(
            self.session,
            None if min_interval is None else timedelta(seconds=min_interval),
            self.at(timestamp), self.participation, **kwargs)
        kwargs.setdefault("contest", None)
        kwargs.setdefault("task", None)
        kwargs.setdefault("cls", Submission)
        self.calls.append(call(self.session, self.participation, **kwargs))
        return res

    def test_no_limit(self):
        s = self.add_submission(timestamp=self.at(5), task=self.task,
                                participation=self.participation)
        self.get_latest_submission.return_value = s
        # Test different arguments to ensure they don't cause issues.
        self.assertTrue(self.call(None, 0))
        self.assertTrue(self.call(None, 1, contest=self.contest))
        self.assertTrue(self.call(None, 2, task=self.task))
        self.assertTrue(self.call(
            None, 3, contest=self.contest, task=self.task))
        # Having calls signals an inefficiency.
        self.get_latest_submission.assert_not_called()

    def test_limit(self):
        s = self.add_submission(timestamp=self.at(5), task=self.task,
                                participation=self.participation)
        self.get_latest_submission.return_value = s
        # Test different arguments to ensure they are passed to the call.
        self.assertFalse(self.call(1, 4, contest=self.contest))
        self.assertFalse(self.call(3, 6, task=self.task, cls=UserTest))
        self.assertTrue(self.call(4, 11, contest=self.contest, task=self.task))
        # Arguments should have been passed unchanged.
        self.get_latest_submission.assert_has_calls(self.calls)

    def test_limit_no_submissions(self):
        self.get_latest_submission.return_value = None
        # Test different arguments to ensure they are passed to the call.
        self.assertTrue(self.call(1, 4, contest=self.contest, cls=UserTest))
        self.assertTrue(self.call(3, 6, task=self.task))
        self.assertTrue(self.call(4, 11, contest=self.contest, task=self.task))
        # Arguments should have been passed unchanged.
        self.get_latest_submission.assert_has_calls(self.calls)

    def test_limit_unrestricted(self):
        # Unrestricted users have no limit enforced.
        self.participation.unrestricted = True
        s = self.add_submission(timestamp=self.at(5), task=self.task,
                                participation=self.participation)
        self.get_latest_submission.return_value = s
        # Test different arguments to ensure they don't cause issues.
        self.assertTrue(self.call(1, 4, contest=self.contest))
        self.assertTrue(self.call(3, 6, task=self.task))
        self.assertTrue(self.call(
            4, 11, contest=self.contest, task=self.task, cls=UserTest))
        # Having calls signals an inefficiency.
        self.get_latest_submission.assert_not_called()


class TestExtractFilesFromArchive(unittest.TestCase):

    def test_zip(self):
        files = [ReceivedFile(None, "foo.c", b"some content"),
                 ReceivedFile(None, "foo", b"some other content"),
                 ReceivedFile(None, "foo.%l", b"more content")]
        archive_data = io.BytesIO()
        with zipfile.ZipFile(archive_data, "w",
                             compression=zipfile.ZIP_DEFLATED) as f:
            for _, filename, content in files:
                f.writestr(filename, content)
        six.assertCountEqual(
            self, extract_files_from_archive(archive_data.getvalue()), files)

    def test_tar_gz(self):
        files = [ReceivedFile(None, "foo.c", b"some content"),
                 ReceivedFile(None, "foo", b"some other content"),
                 ReceivedFile(None, "foo.%l", b"more content")]
        archive_data = io.BytesIO()
        with tarfile.open(fileobj=archive_data, mode="w:gz") as f:
            for _, filename, content in files:
                fileobj = io.BytesIO(content)
                tarinfo = tarfile.TarInfo(filename)
                tarinfo.size = len(content)
                f.addfile(tarinfo, fileobj)
        six.assertCountEqual(
            self, extract_files_from_archive(archive_data.getvalue()), files)

    def test_failure(self):
        with self.assertRaises(InvalidArchive):
            extract_files_from_archive(b"this is not a valid archive")

    def test_directories(self):
        # Make sure we ignore the directory structure and only use the
        # trailing component of the path (i.e., the basename) in the
        # return value, even if it leads to duplicated filenames.
        archive_data = io.BytesIO()
        with zipfile.ZipFile(archive_data, "w",
                             compression=zipfile.ZIP_DEFLATED) as f:
            f.writestr("toplevel", b"some content")
            f.writestr("nested/once", b"some other content")
            f.writestr("two/levels/deep", b"more content")
            f.writestr("many/levels/deep", b"moar content")
        six.assertCountEqual(
            self, extract_files_from_archive(archive_data.getvalue()),
            [ReceivedFile(None, "toplevel", b"some content"),
             ReceivedFile(None, "once", b"some other content"),
             ReceivedFile(None, "deep", b"more content"),
             ReceivedFile(None, "deep", b"moar content")])

    # The remaining tests trigger some corner cases of the Archive class
    # and demonstrate what we have observed happens in those situations.
    # They are here to show that we're fine (even if not always outright
    # happy) with the behaviors in those scenarios.

    def test_filename_with_null(self):
        # This is an expected and most likely unproblematic behavior.
        archive_data = io.BytesIO()
        with zipfile.ZipFile(archive_data, "w") as f:
            f.writestr("foo\0bar", b"some content")
        six.assertCountEqual(
            self, extract_files_from_archive(archive_data.getvalue()),
            [ReceivedFile(None, "foo", b"some content")])

    # The behavior documented in this test actually only happens when
    # patool uses 7z (which happens if it is found installed). Otherwise
    # it falls back on Python's zipfile module which outright fails.
    # Due to this difference we tolerate failures in this test.
    @unittest.expectedFailure
    def test_empty_filename(self):
        # This is a quite unexpected behavior: luckily in practice it
        # should have no effect as the elements of the submission format
        # aren't allowed to be empty and thus the submission would be
        # rejected later on anyways. It also shouldn't leak any private
        # information.
        archive_data = io.BytesIO()
        with zipfile.ZipFile(archive_data, "w") as f:
            # Need ZipInfo because of "bug" in writestr.
            f.writestr(zipfile.ZipInfo(""), b"some content")
        res = extract_files_from_archive(archive_data.getvalue())
        self.assertEqual(len(res), 1)
        f = res[0]
        self.assertIsNone(f.codename)
        # The extracted file is named like the temporary file where the
        # archive's contents were copied to, plus a trailing tilde.
        six.assertRegex(self, f.filename, "tmp[a-z0-9_]+~")
        self.assertEqual(f.content, b"some content")

    def test_multiple_slashes_are_compressed(self):
        # This is a (probably expected and) desirable behavior.
        archive_data = io.BytesIO()
        with zipfile.ZipFile(archive_data, "w") as f:
            f.writestr("foo//bar", b"some content")
        six.assertCountEqual(
            self, extract_files_from_archive(archive_data.getvalue()),
            [ReceivedFile(None, "bar", b"some content")])

    def test_paths_that_might_escape(self):
        # This should check that the extracted files cannot "escape"
        # from the temporary directory where they're being extracted to.
        filenames = ["../foo/bar", "/foo/bar"]
        for filename in filenames:
            archive_data = io.BytesIO()
            with zipfile.ZipFile(archive_data, "w") as f:
                f.writestr(filename, b"some content")
            six.assertCountEqual(
                self, extract_files_from_archive(archive_data.getvalue()),
                [ReceivedFile(None, "bar", b"some content")])

    def test_conflicting_filenames(self):
        # This is an unnecessary limitation due to the fact that patool
        # does extract files to the actual filesystem. We could avoid it
        # by using zipfile, tarfile, etc. directly but it would be too
        # burdensome to support the same amount of archive types as
        # patool does.
        archive_data = io.BytesIO()
        with zipfile.ZipFile(archive_data, "w") as f:
            f.writestr("foo", b"some content")
            f.writestr("foo/bar", b"more content")
        with self.assertRaises(InvalidArchive):
            extract_files_from_archive(archive_data.getvalue())


MockHTTPFile = namedtuple("MockHTTPFile", ["filename", "body"])


class TestExtractFilesFromTornado(unittest.TestCase):

    def setUp(self):
        super(TestExtractFilesFromTornado, self).setUp()

        patcher = \
            patch("cms.server.contest.submission.extract_files_from_archive")
        self.extract_files_from_archive = patcher.start()
        self.addCleanup(patcher.stop)

    def test_empty(self):
        self.assertEqual(extract_files_from_tornado(dict()), list())

    def test_success(self):
        tornado_files = {
            "foo.%l": [MockHTTPFile("foo.py", b"some python stuff")],
            "bar.%l": [MockHTTPFile("bar.c", b"one file in C"),
                       MockHTTPFile("bar.cxx", b"the same file in C++")],
            # Make sure that empty lists have no effect.
            "baz": []}
        six.assertCountEqual(self, extract_files_from_tornado(tornado_files), [
            ReceivedFile("foo.%l", "foo.py", b"some python stuff"),
            ReceivedFile("bar.%l", "bar.c", b"one file in C"),
            ReceivedFile("bar.%l", "bar.cxx", b"the same file in C++")])

    def test_not_archive_if_other_codenames(self):
        tornado_files = {
            "submission": [MockHTTPFile("sub.zip", b"this is an archive")],
            "foo.%l": [MockHTTPFile("foo.c", b"this is something else")]}
        six.assertCountEqual(self, extract_files_from_tornado(tornado_files), [
            ReceivedFile("submission", "sub.zip", b"this is an archive"),
            ReceivedFile("foo.%l", "foo.c", b"this is something else")])

    def test_not_archive_if_other_files(self):
        tornado_files = {
            "submission": [MockHTTPFile("sub.zip", b"this is an archive"),
                           MockHTTPFile("sub2.zip", b"this is another one")]}
        six.assertCountEqual(self, extract_files_from_tornado(tornado_files), [
            ReceivedFile("submission", "sub.zip", b"this is an archive"),
            ReceivedFile("submission", "sub2.zip", b"this is another one")])

    def test_good_archive(self):
        tornado_files = {
            "submission": [MockHTTPFile("archive.zip", b"this is an archive")]}
        self.assertIs(extract_files_from_tornado(tornado_files),
                      self.extract_files_from_archive.return_value)
        self.extract_files_from_archive.assert_called_once_with(
            b"this is an archive")

    def test_bad_archive(self):
        tornado_files = {
            "submission": [MockHTTPFile("archive.zip",
                                        b"this is not a valid archive")]}
        self.extract_files_from_archive.side_effect = InvalidArchive
        with self.assertRaises(InvalidArchive):
            extract_files_from_tornado(tornado_files)
        self.extract_files_from_archive.assert_called_once_with(
            b"this is not a valid archive")


def make_language(name, source_extensions):
    language = MagicMock()
    language.configure_mock(name=name,
                            source_extensions=source_extensions,
                            source_extension=source_extensions[0])
    return language


C_LANG = make_language("C", [".c"])
# Has many extensions.
CPP_LANG = make_language("C++", [".cpp", ".cxx", ".cc"])
# Has an extension that doesn't begin with a period.
PASCAL_LANG = make_language("Pascal", ["lib.pas"])
# Have the same extensions.
PY2_LANG = make_language("Py2", [".py"])
PY3_LANG = make_language("Py3", [".py"])
# Have extensions that create a weird corner case.
LONG_OVERLAP_LANG = make_language("LongOverlap", [".suf.fix"])
SHORT_OVERLAP_LANG = make_language("ShortOverlap", [".fix"])
# The two in one.
SELF_OVERLAP_LANG = make_language("SelfOverlap", [".suf.fix", ".fix"])

FOO_CONTENT = b"this is the content of a file"
BAR_CONTENT = b"this is the content of another file"
BAZ_CONTENT = b"this is the content of a third file"
SPAM_CONTENT = b"this is the content of a fourth file"
HAM_CONTENT = b"this is the content of a fifth file"
EGGS_CONTENT = b"this is the content of a sixth file"


class TestMatchFilesAndLanguages(unittest.TestCase):

    def setUp(self):
        super(TestMatchFilesAndLanguages, self).setUp()

        self.languages = set()

        patcher = patch("cms.server.contest.submission.LANGUAGES",
                        self.languages)
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch("cms.server.contest.submission.get_language",
                        self.mock_get_language)
        patcher.start()
        self.addCleanup(patcher.stop)

    def mock_get_language(self, language_name):
        for language in self.languages:
            if language.name == language_name:
                return language
        raise KeyError()

    # Test success scenarios.

    def test_success_language_required(self):
        self.languages.update({C_LANG, CPP_LANG})

        # Both languageful and languageless files with and without
        # codename and filename are matched correctly against a
        # language-specific submission format.
        # Also check that when the codename matches the "extensionless"
        # filename is irrelevant (the extension matters, however).
        files, language = match_files_and_languages(
            [ReceivedFile("foo.%l", "my_name.cpp", FOO_CONTENT),
             ReceivedFile("bar.%l", None, BAR_CONTENT),
             ReceivedFile(None, "baz.cc", BAZ_CONTENT),
             ReceivedFile("spam.txt", "my_other_name", SPAM_CONTENT),
             ReceivedFile("eggs.zip", None, HAM_CONTENT),
             ReceivedFile(None, "ham", EGGS_CONTENT)],
            None,
            {"foo.%l", "bar.%l", "baz.%l",
             "spam.txt", "eggs.zip", "ham",
             "superfluous"},
            None)
        self.assertEqual(files, {"foo.%l": FOO_CONTENT,
                                 "bar.%l": BAR_CONTENT,
                                 "baz.%l": BAZ_CONTENT,
                                 "spam.txt": SPAM_CONTENT,
                                 "eggs.zip": HAM_CONTENT,
                                 "ham": EGGS_CONTENT})
        self.assertIs(language, CPP_LANG)

    def test_success_language_agnostic(self):
        self.languages.update({C_LANG, CPP_LANG})

        # Languageless files with and without codename and filename are
        # matched correctly against a language-agnostic submission
        # format.
        files, language = match_files_and_languages(
            [ReceivedFile("foo.txt", "my_name", FOO_CONTENT),
             ReceivedFile("bar.zip", None, BAR_CONTENT),
             ReceivedFile(None, "baz", BAZ_CONTENT)],
            None,
            {"foo.txt", "bar.zip", "baz",
             "superfluous"},
            None)
        self.assertEqual(files, {"foo.txt": FOO_CONTENT,
                                 "bar.zip": BAR_CONTENT,
                                 "baz": BAZ_CONTENT})
        self.assertIsNone(language)

    # Test support for language-agnostic formats.

    def test_language_agnostic_always_possible(self):
        self.languages.update({C_LANG, CPP_LANG})

        # In language-agnostic settings, passing a (non-None) language
        # is an error.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                [ReceivedFile("foo.txt", None, FOO_CONTENT)],
                "C", {"foo.txt", "bar.zip"}, None)

        # Even if a set of allowed languages is given, None (when
        # applicable) is always allowed.
        files, language = match_files_and_languages(
            [ReceivedFile("foo.txt", None, FOO_CONTENT)],
            None, {"foo.txt", "bar.zip"}, ["C++"])
        self.assertEqual(files, {"foo.txt": FOO_CONTENT})
        self.assertIsNone(language)

    # Tests for issues matching files.

    def test_bad_file(self):
        self.languages.update({C_LANG})

        # Different codename.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                [ReceivedFile("foo.%l", None, FOO_CONTENT)],
                "C", {"bar.%l"}, None)

        # Incompatible filename.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                [ReceivedFile(None, "foo.c", FOO_CONTENT)],
                "C", {"bar.%l"}, None)

        # The same in a language-agnostic setting.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                [ReceivedFile("foo.txt", None, FOO_CONTENT)],
                None, {"bar.txt"}, None)

        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                [ReceivedFile(None, "foo.txt", FOO_CONTENT)],
                None, {"bar.txt"}, None)

    def test_bad_extension(self):
        self.languages.update({C_LANG})

        # Even when the codename (and, here, but not necessarily, the
        # extensionless filename) match, the filename's extension needs
        # to be compatible with the language.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                [ReceivedFile("foo.%l", "foo.cpp", FOO_CONTENT)],
                "C", {"foo.%l"}, None)

    def test_extension_without_leading_period(self):
        self.languages.update({PASCAL_LANG})

        # Check that the *whole* trailing `.%l` string is replaced with
        # the extension, not just the `%l` part, and also check that the
        # function doesn't split the extension on the filename.
        files, language = match_files_and_languages(
            [ReceivedFile(None, "foolib.pas", FOO_CONTENT)],
            None, {"foo.%l"}, None)
        self.assertEqual(files, {"foo.%l": FOO_CONTENT})
        self.assertIs(language, PASCAL_LANG)

        # The same check, in the negative form.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                [ReceivedFile(None, "foo.lib.pas", FOO_CONTENT)],
                None, {"foo.%l"}, None)

        # This must also hold when the filename isn't matched against
        # the submission format (because the codename is used for that)
        # but just its extension is checked.
        files, language = match_files_and_languages(
            [ReceivedFile("foo.%l", "foolib.pas", FOO_CONTENT)],
            None, {"foo.%l"}, None)
        self.assertEqual(files, {"foo.%l": FOO_CONTENT})
        self.assertIs(language, PASCAL_LANG)

    def test_duplicate_files(self):
        self.languages.update({C_LANG})

        # If two files match the same codename (even if through
        # different means) then the match is invalid.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                [ReceivedFile("foo.%l", "bar.c", FOO_CONTENT),
                 ReceivedFile(None, "foo.c", BAR_CONTENT)],
                None, {"foo.%l"}, None)

    def test_ambiguous_file(self):
        self.languages.update({C_LANG, CPP_LANG})

        # For an admittedly weird submission format, a single file could
        # successfully match multiple elements.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                [ReceivedFile(None, "foo.c", FOO_CONTENT)],
                "C", {"foo.%l", "foo.c"}, None)

        # This brings in some weird side-effects: for example, in the
        # following, our attempt at matching the files as C fails (since
        # foo.c is ambiguous) whereas matching them as C++ doesn't (as
        # foo.c isn't compatible with foo.%l anymore); thus we guess
        # that the correct language must be C++. If there were other
        # languages allowed it would become ambiguous and fail (as then
        # all languages would be compatible, except C). Remember that
        # these sort of problems arise only when codenames aren't given.
        files, language = match_files_and_languages(
            [ReceivedFile(None, "foo.c", FOO_CONTENT)],
            None, {"foo.%l", "foo.c"}, None)
        self.assertEqual(files, {"foo.c": FOO_CONTENT})
        self.assertIs(language, CPP_LANG)

        # And although in theory it could be disambiguated in some cases
        # if one were smart enough, we aren't.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                [ReceivedFile("foo.%l", "bar.c", FOO_CONTENT),
                 ReceivedFile(None, "foo.c", FOO_CONTENT)],
                "C", {"foo.%l", "foo.c"}, None)

    def test_ambiguous_file_2(self):
        self.languages.update(
            {SELF_OVERLAP_LANG, LONG_OVERLAP_LANG, SHORT_OVERLAP_LANG})

        # For an even weirder language and submission format, a single
        # file could successfully match two language-specific elements
        # of the submission format.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                [ReceivedFile(None, "foo.suf.fix", FOO_CONTENT)],
                "SelfOverlap", {"foo.%l", "foo.suf.%l"}, None)

        # Wow, much overlap, very ambiguous.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                [ReceivedFile(None, "foo.suf.fix", FOO_CONTENT)],
                None, {"foo.%l", "foo.suf.%l"}, None)

        # I'm doing this just for the fun.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                [ReceivedFile(None, "foo.suf.fix", FOO_CONTENT)],
                None, {"foo.%l"}, None)

    # Tests for language issues and ways to solve them.

    def test_forbidden_language(self):
        self.languages.update({C_LANG, CPP_LANG})

        # The (autoguessed) language that would match is forbidden.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                [ReceivedFile("foo.%l", "foo.c", FOO_CONTENT)],
                None, {"foo.%l"}, ["C++", "Py2"])

        # The same if the language is given.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                [ReceivedFile("foo.%l", "foo.c", FOO_CONTENT)],
                "C", {"foo.%l"}, ["C++", "Py2"])

    def test_missing_extensions(self):
        self.languages.update({C_LANG, CPP_LANG})
        given_files = [ReceivedFile("foo.%l", None, FOO_CONTENT)]
        submission_format = {"foo.%l"}

        # The situation is ambiguous: it matches for every language, as
        # there is no extension to clarify and no language is given.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                given_files, None, submission_format, None)

        # Restricting the candidates fixes it.
        files, language = match_files_and_languages(
            given_files, "C", submission_format, None)
        self.assertEqual(files, {"foo.%l": FOO_CONTENT})
        self.assertIs(language, C_LANG)

        # So does limiting the allowed languages.
        files, language = match_files_and_languages(
            given_files, None, submission_format, ["C++"])
        self.assertEqual(files, {"foo.%l": FOO_CONTENT})
        self.assertIs(language, CPP_LANG)

    def test_ambiguous_extensions(self):
        self.languages.update({PY2_LANG, PY3_LANG})
        given_files = [ReceivedFile("foo.%l", "foo.py", FOO_CONTENT)]
        submission_format = {"foo.%l"}

        # The situation is ambiguous: both languages match the
        # extension.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                given_files, None, submission_format, None)

        # Restricting the candidates fixes it.
        files, language = match_files_and_languages(
            given_files, "Py2", submission_format, None)
        self.assertEqual(files, {"foo.%l": FOO_CONTENT})
        self.assertIs(language, PY2_LANG)

        # So does limiting the allowed languages.
        files, language = match_files_and_languages(
            given_files, None, submission_format, ["Py3"])
        self.assertEqual(files, {"foo.%l": FOO_CONTENT})
        self.assertIs(language, PY3_LANG)

    def test_overlapping_extensions(self):
        self.languages.update({LONG_OVERLAP_LANG, SHORT_OVERLAP_LANG})
        given_files = [ReceivedFile(None, "foo.suf.fix", FOO_CONTENT)]
        submission_format = {"foo.%l", "foo.suf.%l"}

        # The situation is ambiguous: both languages match, although
        # each does so to a different element of the submission format.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                given_files, None, submission_format, None)

        # Restricting the candidates fixes it.
        files, language = match_files_and_languages(
            given_files, "LongOverlap", submission_format, None)
        self.assertEqual(files, {"foo.%l": FOO_CONTENT})
        self.assertIs(language, LONG_OVERLAP_LANG)

        # So does limiting the allowed languages.
        files, language = match_files_and_languages(
            given_files, None, submission_format, ["ShortOverlap"])
        self.assertEqual(files, {"foo.suf.%l": FOO_CONTENT})
        self.assertIs(language, SHORT_OVERLAP_LANG)

    # Test some corner cases.

    def test_neither_codename_nor_filename(self):
        self.languages.update({C_LANG})

        # Without neither codename nor filename, there's nothing to base
        # a match on.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                [ReceivedFile(None, None, FOO_CONTENT)],
                "C", {"foo.%l"}, None)

        # The same holds in a language-agnostic setting.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                [ReceivedFile(None, None, FOO_CONTENT)],
                None, {"foo.txt"}, None)

    def test_nonexisting_given_languages(self):
        self.languages.update({C_LANG, CPP_LANG})

        # Passing a language that doesn't exist means the contestant
        # doesn't know what they are doing: we're not following through.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                [ReceivedFile("foo.%l", "foo.c", FOO_CONTENT)],
                "BadLang", {"foo.%l"}, None)

    def test_nonexisting_allowed_languages(self):
        self.languages.update({C_LANG, CPP_LANG})

        # Non-existing languages among the allowed languages are seen as
        # a configuration error: admins should intervene but contestants
        # shouldn't suffer, and thus these items are simply ignored.
        # Both when used to constitute the candidates (as no candidates
        # were given)...
        files, language = match_files_and_languages(
            [ReceivedFile("foo.%l", "foo.c", FOO_CONTENT)],
            None, {"foo.%l"}, ["C", "BadLang"])
        self.assertEqual(files, {"foo.%l": FOO_CONTENT})
        self.assertIs(language, C_LANG)

        # And when they act as filter for the given candidates.
        files, language = match_files_and_languages(
            [ReceivedFile("foo.%l", "foo.c", FOO_CONTENT)],
            "C", {"foo.%l"}, ["C", "BadLang"])
        self.assertEqual(files, {"foo.%l": FOO_CONTENT})
        self.assertIs(language, C_LANG)

    def test_given_files_empty(self):
        self.languages.update({C_LANG, CPP_LANG})

        # No files vacuously match every submission format for every
        # language, hence this is ambiguous.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                list(), None, {"foo.%l"}, None)

        # For just a single fixed language it could be considered valid,
        # however in the best case it would be rejected later because
        # some (all) files are missing and in the worst case the files
        # from the previous submission would be fetched: no reasonable
        # user could have meant this on purpose, we reject.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                list(), "C", {"foo.%l"}, None)

        # The same holds for a language-agnostic submission format:
        # moreover, in that case there wouldn't be any ambiguity from
        # the start as only one "language" is allowed (i.e., None).
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                list(), None, {"foo.txt"}, None)

    def test_submission_format_empty(self):
        self.languages.update({C_LANG, CPP_LANG})

        # If no files are wanted, any file will cause an invalid match.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                [ReceivedFile("foo.%l", "foo.c", FOO_CONTENT)],
                "C", set(), None)

        # Even in language-agnostic settings.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                [ReceivedFile("foo.txt", "foo.txt", FOO_CONTENT)],
                None, set(), None)

        # If there are no files this could be made to work. However we
        # decided that this means that the whole thing is very messed up
        # and thus abort instead.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                list(), None, set(), None)

    def test_allowed_languages_empty(self):
        self.languages.update({C_LANG})

        # An empty list of allowed languages means no language allowed:
        # any attempt at matching must necessarily fail.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                [ReceivedFile("foo.%l", "foo.c", FOO_CONTENT)],
                "C", {"foo.%l"}, list())

        # If all allowed languages are invalid, it's as if there weren't
        # any.
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                [ReceivedFile("foo.%l", "foo.c", FOO_CONTENT)],
                "C", {"foo.%l"}, ["BadLang"])

        # The same holds if no candidates are given (this difference is
        # relevant because now the allowed ones are used as candidates,
        # instead of acting only as a filter).
        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                [ReceivedFile("foo.%l", "foo.c", FOO_CONTENT)],
                None, {"foo.%l"}, list())

        with self.assertRaises(InvalidFilesOrLanguage):
            match_files_and_languages(
                [ReceivedFile("foo.%l", "foo.c", FOO_CONTENT)],
                None, {"foo.%l"}, ["BadLang"])

        # However the "None" language, if applicable (i.e., if the
        # submission format is language-agnostic), is always allowed.
        files, language = match_files_and_languages(
            [ReceivedFile("foo.txt", "foo.txt", FOO_CONTENT)],
            None, {"foo.txt"}, list())
        self.assertEqual(files, {"foo.txt": FOO_CONTENT})
        self.assertIsNone(language)

        files, language = match_files_and_languages(
            [ReceivedFile("foo.txt", "foo.txt", FOO_CONTENT)],
            None, {"foo.txt"}, ["BadLang"])
        self.assertEqual(files, {"foo.txt": FOO_CONTENT})
        self.assertIsNone(language)


class TestFetchFileDigestsFromPreviousSubmission(DatabaseMixin,
                                                 unittest.TestCase):

    def setUp(self):
        super(TestFetchFileDigestsFromPreviousSubmission, self).setUp()

        self.contest = self.add_contest()
        self.participation = self.add_participation(contest=self.contest)
        self.task = self.add_task(contest=self.contest)

        self.languages = {C_LANG, CPP_LANG, PY2_LANG, PY3_LANG}

        patcher = patch("cms.server.contest.submission.LANGUAGES",
                        self.languages)
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch("cms.server.contest.submission.get_language",
                        self.mock_get_language)
        patcher.start()
        self.addCleanup(patcher.stop)

    def mock_get_language(self, language_name):
        for language in self.languages:
            if language.name == language_name:
                return language
        raise KeyError()

    def insert_submission(self, language, file_digests):
        s = self.add_submission(
            language=language, participation=self.participation, task=self.task)
        for codename, digest in iteritems(file_digests):
            self.add_file(filename=codename, digest=digest, submission=s)

    def insert_user_test(
            self, language, input_digest, file_digests, manager_digests):
        t = self.add_user_test(
            language=language, input=input_digest,
            participation=self.participation, task=self.task)
        for codename, digest in iteritems(file_digests):
            self.add_user_test_file(filename=codename, digest=digest,
                                    user_test=t)
        for filename, digest in iteritems(manager_digests):
            self.add_user_test_manager(filename=filename, digest=digest,
                                       user_test=t)

    def call(self, language, codenames, cls=Submission):
        return fetch_file_digests_from_previous_submission(
            self.session, self.participation, self.task, language, codenames,
            cls)

    def test_success_submission(self):
        foo_digest = unique_digest()
        baz_digest = unique_digest()
        self.insert_submission("C",
                               {"foo.%l": foo_digest, "baz.txt": baz_digest})
        self.assertEqual(self.call(C_LANG, {"foo.%l", "bar.txt"}),
                         {"foo.%l": foo_digest})

    def test_no_submission(self):
        self.assertEqual(self.call(C_LANG, {"foo.%l", "bar.txt"}),
                         dict())

    def test_previous_submission_wrong_language(self):
        foo_digest = unique_digest()
        baz_digest = unique_digest()
        self.insert_submission("C",
                               {"foo.%l": foo_digest, "baz.txt": baz_digest})
        self.assertEqual(self.call(PY2_LANG, {"foo.%l", "bar.txt"}),
                         dict())

    def test_language_agnostic(self):
        foo_digest = unique_digest()
        baz_digest = unique_digest()
        self.insert_submission(None,
                               {"foo.txt": foo_digest, "baz": baz_digest})
        self.assertEqual(self.call(None, {"foo.txt", "bar.zip"}),
                         {"foo.txt": foo_digest})

    def test_success_user_test(self):
        input_digest = unique_digest()
        foo_digest = unique_digest()
        baz_digest = unique_digest()
        spam_digest = unique_digest()
        eggs_digest = unique_digest()
        self.insert_user_test("C", input_digest,
                              {"foo.%l": foo_digest, "baz.txt": baz_digest},
                              {"spam.c": spam_digest, "eggs.h": eggs_digest})
        self.assertEqual(self.call(C_LANG, {"input",
                                            "foo.%l", "bar.txt",
                                            "spam.%l", "ham"},
                                   cls=UserTest),
                         {"input": input_digest,
                          "foo.%l": foo_digest,
                          "spam.%l": spam_digest})

    def test_no_user_test(self):
        self.assertEqual(self.call(C_LANG, {"foo.%l", "bar.txt"},
                                   cls=UserTest),
                         dict())

    def test_previous_user_test_wrong_language(self):
        foo_digest = unique_digest()
        baz_digest = unique_digest()
        input_digest = unique_digest()
        spam_digest = unique_digest()
        eggs_digest = unique_digest()
        self.insert_user_test("C", input_digest,
                              {"foo.%l": foo_digest, "baz.txt": baz_digest},
                              {"spam.c": spam_digest, "eggs.h": eggs_digest})
        self.assertEqual(self.call(PY2_LANG, {"input",
                                              "foo.%l", "bar.txt",
                                              "spam.%l", "ham"},
                                   cls=UserTest),
                         dict())

    def test_managers_can_use_only_primary_extension(self):
        input_digest = unique_digest()
        foo_digest = unique_digest()
        bar_digest = unique_digest()
        self.insert_user_test("C++", input_digest, dict(),
                              {"foo.cpp": foo_digest, "bar.cc": bar_digest})
        self.assertEqual(self.call(CPP_LANG, {"foo.%l", "bar.%l"},
                                   cls=UserTest),
                         {"foo.%l": foo_digest})


class TestStoreLocalCopy(DatabaseMixin, FileSystemMixin, unittest.TestCase):

    def setUp(self):
        super(TestStoreLocalCopy, self).setUp()

        self.contest = self.add_contest()
        self.participation = self.add_participation(contest=self.contest)
        self.task = self.add_task(contest=self.contest)
        # Flush needed so that the objects are given IDs by the DB.
        self.session.flush()

        self.timestamp = make_datetime()

    @staticmethod
    def generate_content():
        return unique_unicode_id().encode('utf-8')

    def assertSomeFileContains(self, content, in_):
        # The function uses pickle, which has the nice property of
        # serializing bytes objects verbatim and byte-aligned, meaning
        # we can find them unchanged when we look at the encoded data.
        for directory, _, filenames in os.walk(in_):
            for filename in filenames:
                with io.open(os.path.join(directory, filename), "rb") as f:
                    if content in f.read():
                        return
        self.fail("store_local_copy didn't create any file")

    def test_success(self):
        # We use a content that is unique enough to ensure that if we
        # find it in a file it won't be a false positive.
        content = self.generate_content()
        directory = os.path.join(self.base_dir, "foo")
        store_local_copy(directory, self.participation, self.task,
                         self.timestamp, {"foo.%l": content})
        self.assertSomeFileContains(content, in_=directory)

    def test_success_many_times(self):
        # Test that multiple files are allowed in a single call and that
        # successive calls don't overwrite preceding ones.
        content_a = self.generate_content()
        content_b = self.generate_content()
        content_c = self.generate_content()
        store_local_copy(self.base_dir, self.participation, self.task,
                         self.timestamp,
                         {"foo.%l": content_a, "bar.txt": content_b})
        # Giving the same user and timestamp would actually overwrite.
        store_local_copy(self.base_dir, self.participation, self.task,
                         self.timestamp + timedelta(seconds=1),
                         {"foo.%l": content_c})
        self.assertSomeFileContains(content_a, in_=self.base_dir)
        self.assertSomeFileContains(content_b, in_=self.base_dir)
        self.assertSomeFileContains(content_c, in_=self.base_dir)

    def test_success_with_data_dir(self):
        content = self.generate_content()
        with patch.object(config, "data_dir", self.base_dir):
            store_local_copy("%s/bar", self.participation, self.task,
                             self.timestamp, {"foo.%l": content})
        self.assertSomeFileContains(content,
                                    in_=os.path.join(self.base_dir, "bar"))

    def test_failure(self):
        # Make read-only.
        os.chmod(self.base_dir, stat.S_IRUSR)
        with self.assertRaises(StorageFailed):
            store_local_copy(self.base_dir, self.participation, self.task,
                             self.timestamp, {"foo.%l": b"some content"})


if __name__ == "__main__":
    unittest.main()
