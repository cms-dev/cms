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

"""Tests for the DumpImporter script"""

import json
import os
import unittest

# Needs to be first to allow for monkey patching the DB connection string.
from cmstestsuite.unit_tests.databasemixin import DatabaseMixin

from cms.db import Contest, User, FSObject, Session, version
from cmscommon.digest import bytes_digest
from cmscontrib.DumpImporter import DumpImporter
from cmstestsuite.unit_tests.filesystemmixin import FileSystemMixin


class TestDumpImporter(DatabaseMixin, FileSystemMixin, unittest.TestCase):

    GENERATED_FILE_CONTENT = b"content"
    NON_GENERATED_FILE_CONTENT = b"source"

    GENERATED_FILE_DIGEST = bytes_digest(GENERATED_FILE_CONTENT)
    NON_GENERATED_FILE_DIGEST = bytes_digest(NON_GENERATED_FILE_CONTENT)

    FILES = {
        GENERATED_FILE_DIGEST: ("desc", GENERATED_FILE_CONTENT),
        NON_GENERATED_FILE_DIGEST: ("subsource", NON_GENERATED_FILE_CONTENT),
    }

    DUMP = {
        "contest_key": {
            "_class": "Contest",
            "name": "contestname",
            "description": "contest description 你好",
            "tasks": ["task_key"],
            "participations": ["part_key"],
        },
        "task_key": {
            "_class": "Task",
            "name": "taskname",
            "title": "task title",
            "num": 0,
            "contest": "contest_key",
            "submission_format": ["source"],
            "attachments": {},
            "datasets": ["dataset_key"],
            "active_dataset": "dataset_key",
            "submissions": ["sub_key"],
        },
        "dataset_key": {
            "_class": "Dataset",
            "task_type": "Batch",
            "task_type_parameters": "[]",
            "score_type": "Sum",
            "score_type_parameters": "[]",
            "time_limit": 1.0,
            "memory_limit": 512 * 1024 * 1024,
            "description": "dataset description",
            "task": "task_key",
            "managers": {},
        },
        "user_key": {
            "_class": "User",
            "username": "username",
            "first_name": "First Name",
            "last_name": "Last Name",
            "password": "pwd",
            "participations": ["part_key"],
        },
        "part_key": {
            "_class": "Participation",
            "user": "user_key",
            "contest": "contest_key",
            "submissions": ["sub_key"],
        },
        "sub_key": {
            "_class": "Submission",
            "timestamp": 1_234_567_890.123,
            "participation": "part_key",
            "task": "task_key",
            "files": {"source": "file_key"},
            "results": ["sr_key"],
        },
        "file_key": {
            "_class": "File",
            "submission": "sub_key",
            "filename": "source",
            "digest": NON_GENERATED_FILE_DIGEST,
        },
        "sr_key": {
            "_class": "SubmissionResult",
            "submission": "sub_key",
            "dataset": "dataset_key",
            "executables": {"exe": "exe_key"},
        },
        "exe_key": {
            "_class": "Executable",
            "submission_result": "sr_key",
            "filename": "exe",
            "dataset": "dataset_key",
            "digest": GENERATED_FILE_DIGEST,
        },
        "_version": version,
        "_objects": ["contest_key", "user_key"],
    }

    def setUp(self):
        super().setUp()

        # Another contest, to make sure it's not wiped on import.
        self.other_contest = self.add_contest()
        self.session.commit()

        self.other_contest_name = self.other_contest.name
        self.other_contest_description = self.other_contest.description

    def tearDown(self):
        self.delete_data()
        super().tearDown()

    def do_import(self, drop=False, load_files=True,
                  skip_generated=False, skip_submissions=False,
                  skip_users=False):
        """Create an importer and call do_import in a convenient way"""
        return DumpImporter(
            drop,
            self.base_dir,
            load_files=load_files,
            load_model=True,
            skip_generated=skip_generated,
            skip_submissions=skip_submissions,
            skip_user_tests=False,
            skip_users=skip_users,
            skip_print_jobs=False).do_import()

    def write_dump(self, dump):
        destination = self.get_path("contest.json")
        with open(destination, "wt", encoding="utf-8") as f:
            json.dump(dump, f, indent=4, sort_keys=True)

    def write_files(self, data):
        """Write files and descriptions on the filesystem.

        data ({str: (str, bytes)}): dictionary mapping digest to description
            and content.

        """
        f_path = self.makedirs("files")
        d_path = self.makedirs("descriptions")
        for digest, (desc, content) in data.items():
            with open(
                    os.path.join(d_path, digest), "wt", encoding="utf-8") as f:
                f.write(desc)
            with open(os.path.join(f_path, digest), "wb") as f:
                f.write(content)

    def assertContestInDb(self, name, description, task_names_and_titles,
                          usernames_and_last_names):
        """Assert that the contest with the given data is in the DB

        The query is done by contest name, and to avoid caching, we query from
        a brand new session.

        """
        db_contests = self.session.query(Contest)\
            .filter(Contest.name == name).all()
        self.assertEqual(len(db_contests), 1)
        c = db_contests[0]
        self.assertEqual(c.name, name)
        self.assertEqual(c.description, description)
        self.assertCountEqual([(t.name, t.title) for t in c.tasks],
                              task_names_and_titles)
        self.assertCountEqual([(u.user.username, u.user.last_name)
                                for u in c.participations],
                              usernames_and_last_names)

    def assertContestNotInDb(self, name):
        """Assert that the contest with the given name is not in the DB."""
        db_contests = self.session.query(Contest)\
            .filter(Contest.name == name).all()
        self.assertEqual(len(db_contests), 0)

    def assertUserNotInDb(self, username):
        """Assert that the user with the given username is not in the DB."""
        db_users = self.session.query(User)\
            .filter(User.username == username).all()
        self.assertEqual(len(db_users), 0)

    def assertFileInDb(self, digest, description, content):
        """Assert that the file with the given data is in the DB."""
        fsos = self.session.query(FSObject)\
            .filter(FSObject.digest == digest).all()
        self.assertEqual(len(fsos), 1)
        fso = fsos[0]
        self.assertEqual(fso.digest, digest)
        self.assertEqual(fso.description, description)
        self.assertEqual(fso.get_lobject().read(), content)

    def assertFileNotInDb(self, digest):
        """Assert that the file with the given digest is not in the DB."""
        fsos = self.session.query(FSObject)\
            .filter(FSObject.digest == digest).all()
        self.assertEqual(len(fsos), 0)

    def test_import(self):
        """Test importing everything, while keeping the existing contest."""
        self.write_dump(TestDumpImporter.DUMP)
        self.write_files(TestDumpImporter.FILES)
        self.assertTrue(self.do_import())

        self.assertContestInDb("contestname", "contest description 你好",
                               [("taskname", "task title")],
                               [("username", "Last Name")])
        self.assertContestInDb(
            self.other_contest_name, self.other_contest_description, [], [])

        self.assertFileInDb(
            TestDumpImporter.GENERATED_FILE_DIGEST, "desc", b"content")
        self.assertFileInDb(
            TestDumpImporter.NON_GENERATED_FILE_DIGEST, "subsource", b"source")

    def test_import_with_drop(self):
        """Test importing everything, but dropping existing data."""
        self.write_dump(TestDumpImporter.DUMP)
        self.write_files(TestDumpImporter.FILES)

        # Need to close the session and reopen it, otherwise the drop hangs.
        self.session.close()
        self.assertTrue(self.do_import(drop=True))
        self.session = Session()

        self.assertContestInDb("contestname", "contest description 你好",
                               [("taskname", "task title")],
                               [("username", "Last Name")])
        self.assertContestNotInDb(self.other_contest_name)

        self.assertFileInDb(
            TestDumpImporter.GENERATED_FILE_DIGEST, "desc", b"content")
        self.assertFileInDb(
            TestDumpImporter.NON_GENERATED_FILE_DIGEST, "subsource", b"source")

    def test_import_skip_generated(self):
        """Test importing everything but the generated data."""
        self.write_dump(TestDumpImporter.DUMP)
        self.write_files(TestDumpImporter.FILES)
        self.assertTrue(self.do_import(skip_generated=True))

        self.assertContestInDb("contestname", "contest description 你好",
                               [("taskname", "task title")],
                               [("username", "Last Name")])
        self.assertContestInDb(
            self.other_contest_name, self.other_contest_description, [], [])

        self.assertFileNotInDb(TestDumpImporter.GENERATED_FILE_DIGEST)
        self.assertFileInDb(
            TestDumpImporter.NON_GENERATED_FILE_DIGEST, "subsource", b"source")

    def test_import_skip_files(self):
        """Test importing the json but not the files."""
        self.write_dump(TestDumpImporter.DUMP)
        self.write_files(TestDumpImporter.FILES)
        self.assertTrue(self.do_import(load_files=False))

        self.assertContestInDb("contestname", "contest description 你好",
                               [("taskname", "task title")],
                               [("username", "Last Name")])
        self.assertContestInDb(
            self.other_contest_name, self.other_contest_description, [], [])

        self.assertFileNotInDb(TestDumpImporter.GENERATED_FILE_DIGEST)
        self.assertFileNotInDb(TestDumpImporter.NON_GENERATED_FILE_DIGEST)

    def test_import_skip_users(self):
        """Test importing everything but not the users."""
        self.write_dump(TestDumpImporter.DUMP)
        self.write_files(TestDumpImporter.FILES)

        self.assertTrue(self.do_import(skip_users=True))

        self.assertContestInDb("contestname", "contest description 你好",
                               [("taskname", "task title")],
                               [])
        self.assertContestInDb(
            self.other_contest_name, self.other_contest_description, [], [])

        self.assertUserNotInDb("username")
        self.assertFileNotInDb(TestDumpImporter.GENERATED_FILE_DIGEST)
        self.assertFileNotInDb(TestDumpImporter.NON_GENERATED_FILE_DIGEST)


    def test_import_old(self):
        """Test importing an old dump.

        This does not pretend to be exhaustive, just makes sure the happy
        path of the updaters run successfully.

        """
        self.write_dump({
            "contest_key": {
                "_class": "Contest",
                "name": "contestname",
                "description": "contest description",
                "start": 1_234_567_890.000,
                "stop": 1_324_567_890.000,
                "token_initial": 2,
                "token_gen_number": 1,
                "token_gen_time": 10,
                "token_total": 100,
                "token_max": 100,
                "tasks": ["task_key"],
            },
            "task_key": {
                "_class": "Task",
                "name": "taskname",
                "title": "task title",
                "num": 0,
                "primary_statements": "[\"en\", \"ja\"]",
                "token_initial": None,
                "token_gen_number": 0,
                "token_gen_time": 0,
                "token_total": None,
                "token_max": None,
                "task_type": "Batch",
                "task_type_parameters": "[]",
                "score_type": "Sum",
                "score_type_parameters": "[]",
                "time_limit": 0.0,
                "memory_limit": None,
                "contest": "contest_key",
                "attachments": {},
                "managers": {},
                "testcases": {},
                "submissions": ["sub1_key", "sub2_key"],
                "user_tests": [],
            },
            "user_key": {
                "_class": "User",
                "username": "username",
                "first_name": "First Name",
                "last_name": "Last Name",
                "password": "pwd",
                "email": "",
                "ip": "0.0.0.0",
                "preferred_languages": "[\"en\", \"it_IT\"]",
                "contest": "contest_key",
                "submissions": ["sub1_key", "sub2_key"],
            },
            "sub1_key": {
                "_class": "Submission",
                "timestamp": 1_234_567_890.123,
                "language": "c",
                "user": "user_key",
                "task": "task_key",
                "compilation_text": "OK [1.234 - 20]",
                "files": {},
                "executables": {"exe": "exe_key"},
                "evaluations": [],
            },
            "sub2_key": {
                "_class": "Submission",
                "timestamp": 1_234_567_900.123,
                "language": "c",
                "user": "user_key",
                "task": "task_key",
                "compilation_text": "Killed with signal 11 [0.123 - 10]\n",
                "files": {},
                "executables": {},
                "evaluations": [],
            },
            "exe_key": {
                "_class": "Executable",
                "submission": "sub1_key",
                "filename": "exe",
                "digest": TestDumpImporter.GENERATED_FILE_DIGEST,
            },
            "_version": 1,
            "_objects": ["contest_key", "user_key"],
        })
        self.write_files(TestDumpImporter.FILES)
        self.assertTrue(self.do_import(skip_generated=True))

        self.assertContestInDb("contestname", "contest description",
                               [("taskname", "task title")],
                               [("username", "Last Name")])
        self.assertContestInDb(
            self.other_contest_name, self.other_contest_description, [], [])

        self.assertFileNotInDb("040f06fd774092478d450774f5ba30c5da78acc8")


if __name__ == "__main__":
    unittest.main()
