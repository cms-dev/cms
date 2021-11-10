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

"""Tests for the DumpExporter script"""

import json
import os
import unittest

# Needs to be first to allow for monkey patching the DB connection string.
from cmstestsuite.unit_tests.databasemixin import DatabaseMixin

from cms.db import Contest, Executable, Participation, Statement, Submission, \
    SubmissionResult, Task, User, version
from cmscommon.digest import bytes_digest
from cmscontrib.DumpExporter import DumpExporter
from cmstestsuite.unit_tests.filesystemmixin import FileSystemMixin


class TestDumpExporter(DatabaseMixin, FileSystemMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()

        self.target = self.get_path("target")
        self.dump = None

        # Add a file to be used as a statement.
        self.st_content = b"statement"
        self.st_digest = bytes_digest(self.st_content)
        self.add_fsobject(self.st_digest, self.st_content)

        # Add a file to be used as a submission source.
        self.file_content = b"source"
        self.file_digest = bytes_digest(self.file_content)
        self.add_fsobject(self.file_digest, self.file_content)

        # Add a file to be used as an executable.
        self.exe_content = b"executable"
        self.exe_digest = bytes_digest(self.exe_content)
        self.add_fsobject(self.exe_digest, self.exe_content)

        self.contest = self.add_contest(description="你好")
        self.participation = self.add_participation(contest=self.contest)
        self.user = self.participation.user
        self.task = self.add_task(contest=self.contest)
        self.statement = self.add_statement(
            task=self.task, digest=self.st_digest)
        self.dataset = self.add_dataset(task=self.task)
        self.task.active_dataset = self.task.datasets[0]
        self.submission = self.add_submission(self.task, self.participation)
        self.file = self.add_file(
            submission=self.submission, digest=self.file_digest)

        # Add the executable to the submission
        self.submission_result = self.add_submission_result(
            submission=self.submission, dataset=self.dataset)
        self.add_executable(self.submission_result, digest=self.exe_digest)

        # Another contest
        self.other_contest = self.add_contest()
        # User and task not attached to any contest.
        self.unattached_user = self.add_user()
        self.unattached_task = self.add_task()

        self.session.commit()

    def tearDown(self):
        self.delete_data()
        super().tearDown()

    def do_export(self, contest_ids, dump_files=True, skip_generated=False,
                  skip_submissions=False, skip_users=False):
        """Create an exporter and call do_export in a convenient way"""
        r = DumpExporter(
            contest_ids,
            self.target,
            dump_files=dump_files,
            dump_model=True,
            skip_generated=skip_generated,
            skip_submissions=skip_submissions,
            skip_user_tests=False,
            skip_users=skip_users,
            skip_print_jobs=False).do_export()
        dump_path = os.path.join(self.target, "contest.json")
        try:
            with open(dump_path, "rt", encoding="utf-8") as f:
                self.dump = json.load(f)
        except Exception:
            self.dump = None

        return r

    def assertInDump(self, cls, **kwargs):
        """Assert that an object is in the dump.

        cls (Class): the object should be of this class.
        kwargs (dict): the object should have at least these key/value pairs.

        return (string): the key of the object in the dump.

        raise (AssertionError): if the object is not in the dump.

        """
        for key, obj in self.dump.items():
            if isinstance(obj, dict) and obj["_class"] == cls.__name__ and \
                    all(obj[k] == v for k, v in kwargs.items()):
                return key
        raise AssertionError("Cannot find object of class %s with fields %s" %
                             (cls.__name__, kwargs))

    def assertNotInDump(self, cls, **kwargs):
        """Assert that an object is not in the dump.

        cls (Class): the object should be of this class.
        kwargs (dict): the object should have at least these key/value pairs.

        raise (AssertionError): if the object is in the dump.

        """
        for obj in self.dump.values():
            if isinstance(obj, dict) and obj["_class"] == cls.__name__ and \
                    all(obj[k] == v for k, v in kwargs.items()):
                raise AssertionError("Object of class %s with fields %s "
                                     "should not appear in the dump" %
                                     (cls.__name__, kwargs))

    def assertFileInDump(self, digest, content):
        path = os.path.join(self.target, "files", digest)
        self.assertTrue(os.path.exists(path))
        with open(path, "rb") as f:
            self.assertEqual(content, f.read())

    def assertFileNotInDump(self, digest):
        path = os.path.join(self.target, "files", digest)
        self.assertFalse(os.path.exists(path))

    def test_dont_overwrite(self):
        with open(self.target, "wt", encoding="utf-8") as f:
            f.write("hello!")
        self.assertFalse(self.do_export(None))
        with open(self.target, "rt") as f:
            self.assertEqual(f.read(), "hello!")

    def test_export_all(self):
        """Test exporting everything.

        In addition to the checks for objects being present, this test also
        checks that cross references are correct, and that we have the correct
        data in _objects and _version.

        """
        self.assertTrue(self.do_export(None))

        contest_key = self.assertInDump(Contest, name=self.contest.name)
        user_key = self.assertInDump(User, username=self.user.username)
        participation_key = self.assertInDump(
            Participation, user=user_key, contest=contest_key)
        task_key = self.assertInDump(
            Task, name=self.task.name, contest=contest_key)
        self.assertInDump(Statement, digest=self.st_digest, task=task_key)
        self.assertInDump(
            Submission, task=task_key, participation=participation_key)

        other_contest_key = self.assertInDump(
            Contest, name=self.other_contest.name)
        unattached_user_key = self.assertInDump(
            User, username=self.unattached_user.username)
        unattached_task_key = self.assertInDump(
            Task, name=self.unattached_task.name)

        self.assertFileInDump(self.st_digest, self.st_content)
        self.assertFileInDump(self.exe_digest, self.exe_content)
        self.assertFileInDump(self.file_digest, self.file_content)

        # Root objects are the contests, the users, and unattached tasks.
        self.assertCountEqual(self.dump["_objects"],
                              [contest_key, other_contest_key, user_key,
                               unattached_task_key, unattached_user_key])
        self.assertEqual(self.dump["_version"], version)

    def test_export_single_contest(self):
        """Test exporting a single contest."""
        self.assertTrue(self.do_export([self.contest.id]))

        self.assertInDump(Contest, name=self.contest.name)
        self.assertInDump(Submission)
        self.assertInDump(Statement, digest=self.st_digest)

        self.assertNotInDump(Contest, name=self.other_contest.name)
        self.assertNotInDump(User, username=self.unattached_user.username)
        self.assertNotInDump(Task, name=self.unattached_task.name)

        self.assertFileInDump(self.st_digest, self.st_content)
        self.assertFileInDump(self.exe_digest, self.exe_content)
        self.assertFileInDump(self.file_digest, self.file_content)

    def test_export_single_contest_no_files(self):
        """Test exporting a contest does not export files of other contests."""
        self.assertTrue(self.do_export([self.other_contest.id]))

        self.assertInDump(Contest, name=self.other_contest.name)
        self.assertNotInDump(Submission)
        self.assertNotInDump(Statement, digest=self.st_digest)

        self.assertNotInDump(Contest, name=self.contest.name)
        self.assertNotInDump(User, username=self.unattached_user.username)
        self.assertNotInDump(Task, name=self.unattached_task.name)

        self.assertFileNotInDump(self.st_digest)
        self.assertFileNotInDump(self.exe_digest)
        self.assertFileNotInDump(self.file_digest)

    def test_skip_files(self):
        """Test skipping files, generated or original."""
        self.assertTrue(self.do_export(None, dump_files=False))

        self.assertInDump(Statement, digest=self.st_digest)
        self.assertInDump(Executable, digest=self.exe_digest)
        self.assertFileNotInDump(self.st_digest)
        self.assertFileNotInDump(self.exe_digest)
        self.assertFileNotInDump(self.file_digest)

    def test_skip_submissions(self):
        """Test skipping submissions.

        Should not export submissions and depending objects, but still export
        the others, including files.

        """
        self.assertTrue(self.do_export(None, skip_submissions=True))

        self.assertInDump(Statement, digest=self.st_digest)
        self.assertFileInDump(self.st_digest, self.st_content)

        self.assertNotInDump(Submission)
        self.assertNotInDump(SubmissionResult)
        self.assertFileNotInDump(self.exe_digest)
        self.assertFileNotInDump(self.file_digest)

    def test_skip_generated(self):
        """Test skipping generated file.

        Should not export results and executables, but still export the other
        files.

        """
        self.assertTrue(self.do_export(None, skip_generated=True))

        self.assertInDump(Statement, digest=self.st_digest)
        self.assertFileInDump(self.st_digest, self.st_content)
        self.assertInDump(Submission)
        self.assertFileInDump(self.file_digest, self.file_content)

        self.assertNotInDump(SubmissionResult)
        self.assertFileNotInDump(self.exe_digest)

    def test_skip_users(self):
        """Test skipping users.

        Should not export users and depending objects.
        Should still export contest, tasks and their depending objects.

        """
        self.assertTrue(self.do_export(None, skip_users=True))

        self.assertInDump(Statement, digest=self.st_digest)
        self.assertFileInDump(self.st_digest, self.st_content)

        self.assertNotInDump(User)
        self.assertNotInDump(Participation)
        self.assertNotInDump(Submission)
        self.assertNotInDump(SubmissionResult)
        self.assertFileNotInDump(self.file_digest)
        self.assertFileNotInDump(self.exe_digest)


if __name__ == "__main__":
    unittest.main()
