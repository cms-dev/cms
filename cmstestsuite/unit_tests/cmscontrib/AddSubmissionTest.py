#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Tests for the AddSubmission script"""

import unittest

# Needs to be first to allow for monkey patching the DB connection string.
from cmstestsuite.unit_tests.databasemixin import DatabaseMixin

from cms.db import File, Submission
from cmscommon.datetime import make_datetime
from cmscommon.digest import bytes_digest
from cmscontrib.AddSubmission import add_submission
from cmstestsuite.unit_tests.filesystemmixin import FileSystemMixin


_TS = 1_234_567_890


_CONTENT_1 = b"this is a source file"
_CONTENT_2 = b"this is another source"
_CONTENT_3 = b"this is one more"
_DIGEST_1 = bytes_digest(_CONTENT_1)
_DIGEST_2 = bytes_digest(_CONTENT_2)
_DIGEST_3 = bytes_digest(_CONTENT_3)
_FILENAME_1 = "file.c"
_FILENAME_2 = "file"
_FILENAME_3 = "file.py"
_LANGUAGE_1 = "C11 / gcc"


class TestAddSubmissionMixin(DatabaseMixin, FileSystemMixin):
    """Mixin for testing AddSubmission with different tasks."""

    def setUp(self):
        super().setUp()

        self.write_file(_FILENAME_1, _CONTENT_1)
        self.write_file(_FILENAME_2, _CONTENT_2)
        self.write_file(_FILENAME_3, _CONTENT_3)

        self.contest = self.add_contest()
        self.other_contest = self.add_contest()
        self.user = self.add_user()
        self.participation = self.add_participation(
            user=self.user, contest=self.contest)
        self.other_participation = self.add_participation(
            user=self.user, contest=self.other_contest)

        self.session.commit()

    def tearDown(self):
        self.delete_data()
        super().tearDown()

    def assertSubmissionInDb(self, timestamp, task, language, files):
        """Assert that the submission with the given data is in the DB."""
        db_submissions = self.session.query(Submission)\
            .filter(Submission.timestamp == make_datetime(timestamp))\
            .filter(Submission.task_id == task.id).all()
        self.assertEqual(len(db_submissions), 1)
        s = db_submissions[0]
        self.assertEqual(s.participation_id, self.participation.id)
        self.assertEqual(s.language, language)

        # Check the submission's files are exactly those expected.
        db_files = self.session.query(File)\
            .filter(File.submission_id == s.id).all()
        db_files_dict = dict((f.filename, f.digest) for f in db_files)
        self.assertEqual(files, db_files_dict)

    def assertSubmissionNotInDb(self, timestamp):
        """Assert that the submission with the given data is not in the DB."""
        db_submissions = self.session.query(Submission)\
            .filter(Submission.timestamp == make_datetime(timestamp)).all()
        self.assertEqual(len(db_submissions), 0)


class TestAddSubmissionSingleSourceWithLanguage(
        TestAddSubmissionMixin, unittest.TestCase):
    """Tests for AddSubmission when the task has a single source file."""

    def setUp(self):
        super().setUp()

        self.task = self.add_task(submission_format=["source.%l"],
                                  contest=self.contest)

        self.session.commit()

    def test_success(self):
        self.assertTrue(add_submission(
            self.contest.id, self.user.username, self.task.name, _TS,
            {"source.%l": self.get_path(_FILENAME_1)}))
        self.assertSubmissionInDb(_TS, self.task, _LANGUAGE_1,
                                  {"source.%l": _DIGEST_1})

    def test_fail_no_task(self):
        # We pass a non-existing task name.
        self.assertFalse(add_submission(
            self.contest.id, self.user.username, self.task.name + "_wrong",
            _TS, {}))
        self.assertSubmissionNotInDb(_TS)

    def test_fail_no_user(self):
        # We pass a non-existing username.
        self.assertFalse(add_submission(
            self.contest.id, self.user.username + "_wrong", self.task.name,
            _TS, {}))
        self.assertSubmissionNotInDb(_TS)

    def test_fail_no_contest(self):
        # We pass a non-existing contest id.
        self.assertFalse(add_submission(
            self.contest.id + 100, self.user.username, self.task.name, _TS,
            {}))
        self.assertSubmissionNotInDb(_TS)

    def test_fail_task_not_in_contest(self):
        # We pass a contest that does not contain the task.
        self.assertFalse(add_submission(
            self.other_contest.id, self.user.username, self.task.name, _TS,
            {}))
        self.assertSubmissionNotInDb(_TS)

    def test_fail_no_language_inferrable_missing_source(self):
        # Task requires a language, but we don't provide any file that
        # indicate it.
        self.assertFalse(add_submission(
            self.contest.id, self.user.username, self.task.name, _TS, {}))
        self.assertSubmissionNotInDb(_TS)

    def test_fail_no_language_inferrable_missing_extension(self):
        # Task requires a language, but the file we provide does not have
        # an extension defining the language.
        self.assertFalse(add_submission(
            self.contest.id, self.user.username, self.task.name, _TS,
            {"source.%l": self.get_path(_FILENAME_2)}))
        self.assertSubmissionNotInDb(_TS)

    def test_fail_file_not_found(self):
        # We provide a path, but the file does not exist.
        self.assertFalse(add_submission(
            self.contest.id, self.user.username, self.task.name, _TS,
            {"source.%l": self.get_path("source_not_existing.c")}))
        self.assertSubmissionNotInDb(_TS)

    def test_fail_file_not_in_submission_format(self):
        # We provide a file, but for the wrong filename.
        self.assertFalse(add_submission(
            self.contest.id, self.user.username, self.task.name, _TS,
            {"wrong_source.%l": self.get_path(_FILENAME_1)}))
        self.assertSubmissionNotInDb(_TS)


class TestAddSubmissionTwoSourcesWithLanguage(
        TestAddSubmissionMixin, unittest.TestCase):
    """Tests for AddSubmission when the task has two source files."""

    def setUp(self):
        super().setUp()

        self.task = self.add_task(
            submission_format=["source1.%l", "source2.%l"],
            contest=self.contest)

        self.session.commit()

    def test_success_many(self):
        self.assertTrue(add_submission(
            self.contest.id, self.user.username, self.task.name, _TS, {
                "source1.%l": self.get_path(_FILENAME_1),
                "source2.%l": self.get_path(_FILENAME_1),
             }))
        self.assertSubmissionInDb(_TS, self.task, _LANGUAGE_1, {
            "source1.%l": _DIGEST_1,
            "source2.%l": _DIGEST_1,
        })

    def test_success_missing_file(self):
        # We allow submissions with missing files, as long as we can identify
        # the language.
        self.assertTrue(add_submission(
            self.contest.id, self.user.username, self.task.name, _TS,
            {"source1.%l": self.get_path(_FILENAME_1)}))
        self.assertSubmissionInDb(_TS, self.task, _LANGUAGE_1,
                                  {"source1.%l": _DIGEST_1})

    def test_fail_language_only_in_one(self):
        self.assertFalse(add_submission(
            self.contest.id, self.user.username, self.task.name, _TS, {
                "source1.%l": self.get_path(_FILENAME_1),
                "source2.%l": self.get_path(_FILENAME_2),
             }))
        self.assertSubmissionNotInDb(_TS)

    def test_fail_inconsistent_language(self):
        # Language for the two files is different.
        self.assertFalse(add_submission(
            self.contest.id, self.user.username, self.task.name, _TS, {
                "source1.%l": self.get_path(_FILENAME_1),
                "source2.%l": self.get_path(_FILENAME_3),
            }))
        self.assertSubmissionNotInDb(_TS)


class TestAddSubmissionTwoSourcesOneLanguage(
        TestAddSubmissionMixin, unittest.TestCase):
    """Tests for AddSubmission with one source with language and one not."""

    def setUp(self):
        super().setUp()

        self.task = self.add_task(
            submission_format=["source1.%l", "source2"],
            contest=self.contest)

        self.session.commit()

    def test_success_many(self):
        self.assertTrue(add_submission(
            self.contest.id, self.user.username, self.task.name, _TS, {
                "source1.%l": self.get_path(_FILENAME_1),
                "source2": self.get_path(_FILENAME_2),
             }))
        self.assertSubmissionInDb(_TS, self.task, _LANGUAGE_1, {
            "source1.%l": _DIGEST_1,
            "source2": _DIGEST_2,
        })

    def test_success_missing_source_without_language(self):
        # We allow submissions with missing files, as long as we can identify
        # the language.
        self.assertTrue(add_submission(
            self.contest.id, self.user.username, self.task.name, _TS,
            {"source1.%l": self.get_path(_FILENAME_1)}))
        self.assertSubmissionInDb(_TS, self.task, _LANGUAGE_1,
                                  {"source1.%l": _DIGEST_1})

    def test_fail_missing_source_with_language(self):
        # We allow submissions with missing files, as long as we can identify
        # the language.
        self.assertFalse(add_submission(
            self.contest.id, self.user.username, self.task.name, _TS,
            {"source2": self.get_path(_FILENAME_2)}))
        self.assertSubmissionNotInDb(_TS)


class TestAddSubmissionOutputOnly(
        TestAddSubmissionMixin, unittest.TestCase):
    """Tests for AddSubmission when there the submission has no language."""

    def setUp(self):
        super().setUp()

        self.task = self.add_task(submission_format=["source"],
                                  contest=self.contest)

        self.session.commit()

    def test_success_no_language(self):
        self.assertTrue(add_submission(
            self.contest.id, self.user.username, self.task.name, _TS,
            {"source": self.get_path(_FILENAME_2)}))
        self.assertSubmissionInDb(_TS, self.task, None, {"source": _DIGEST_2})

    def test_success_no_source(self):
        # Here we don't provide any file, but language is not required.
        self.assertTrue(add_submission(
            self.contest.id, self.user.username, self.task.name, _TS, {}))
        self.assertSubmissionInDb(_TS, self.task, None, {})


if __name__ == "__main__":
    unittest.main()
