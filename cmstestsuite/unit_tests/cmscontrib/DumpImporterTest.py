#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *
from future.builtins import *
from six import assertCountEqual, iteritems

import json
import io
import os
import unittest

from pyfakefs import fake_filesystem_unittest

# Needs to be first to allow for monkey patching the DB connection string.
from cmstestsuite.unit_tests.testdbgenerator import TestCaseWithDatabase

from cms import config
from cms.db import Contest, FSObject, Session, version

from cmscontrib.DumpImporter import DumpImporter


class TestDumpImporter(TestCaseWithDatabase,
                       fake_filesystem_unittest.TestCase):

    DUMP = {
        "contest_key": {
            "_class": "Contest",
            "name": "contestname",
            "description": "contest description 你好",
            "tasks": ["task_key"],
        },
        "task_key": {
            "_class": "Task",
            "name": "taskname",
            "title": "task title",
            "num": 0,
            "contest": "contest_key",
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
            "description": "dataset description",
            "task": "task_key",
        },
        "user_key": {
            "_class": "User",
            "username": "username",
            "first_name": "First Name",
            "last_name": "Last Name",
            "password": "pwd",
        },
        "part_key": {
            "_class": "Participation",
            "user": "user_key",
            "contest": "contest_key",
            "submissions": ["sub_key"],
        },
        "sub_key": {
            "_class": "Submission",
            "timestamp": 1234567890.123,
            "participation": "part_key",
            "task": "task_key",
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
            "digest": "040f06fd774092478d450774f5ba30c5da78acc8",
        },
        "_version": version,
        "_objects": ["contest_key", "user_key"],
    }
    FILES = {
        "040f06fd774092478d450774f5ba30c5da78acc8": ("desc", b"content"),
    }

    def setUp(self):
        super(TestDumpImporter, self).setUp()
        self.setUpPyfakefs()
        if not os.path.exists(config.temp_dir):
            os.makedirs(config.temp_dir)

        self.base = "/tmp/target"

        # Another contest, to make sure it's not wiped on import.
        self.other_contest = self.add_contest()
        self.session.commit()

        self.other_contest_name = self.other_contest.name
        self.other_contest_description = self.other_contest.description

    def tearDown(self):
        self.delete_data()
        super(TestDumpImporter, self).tearDown()

    def do_import(self, drop=False, load_files=True,
                  skip_generated=False, skip_submissions=False):
        """Create an importer and call do_import in a convenient way"""
        return DumpImporter(
            drop,
            self.base,
            load_files=load_files,
            load_model=True,
            skip_generated=skip_generated,
            skip_submissions=skip_submissions,
            skip_user_tests=False).do_import()

    def write_dump(self, dump):
        if not os.path.exists(self.base):
            os.makedirs(self.base)
        with io.open(os.path.join(self.base, "contest.json"), "wt") as f:
            json.dump(dump, f)

    def write_files(self, data):
        """Write files and descriptions on the filesystem.

        data ({str: (str, bytes)}): dictionary mapping digest to description
            and content.

        """
        f_path = os.path.join(self.base, "files")
        os.makedirs(f_path)
        d_path = os.path.join(self.base, "descriptions")
        os.makedirs(d_path)
        for digest, (desc, content) in iteritems(data):
            with io.open(
                    os.path.join(d_path, digest), "wt", encoding="utf-8") as f:
                f.write(desc)
            with io.open(os.path.join(f_path, digest), "wb") as f:
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
        assertCountEqual(self, [(t.name, t.title) for t in c.tasks],
                         task_names_and_titles)
        assertCountEqual(self, [(u.user.username, u.user.last_name)
                                for u in c.participations],
                         usernames_and_last_names)

    def assertContestNotInDb(self, name):
        """Assert that the contest with the given name is not in the DB."""
        db_contests = self.session.query(Contest)\
            .filter(Contest.name == name).all()
        self.assertEqual(len(db_contests), 0)

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
            "040f06fd774092478d450774f5ba30c5da78acc8", "desc", b"content")

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
            "040f06fd774092478d450774f5ba30c5da78acc8", "desc", b"content")

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

        self.assertFileNotInDb("040f06fd774092478d450774f5ba30c5da78acc8")

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
                "start": 1234567890.000,
                "stop": 1324567890.000,
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
                "contest": "contest_key",
                "managers": {},
                "testcases": {},
                "submissions": ["sub_key"],
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
                "submissions": ["sub_key"],
            },
            "sub_key": {
                "_class": "Submission",
                "timestamp": 1234567890.123,
                "language": "c",
                "user": "user_key",
                "task": "task_key",
                "compilation_text": "OK [1.234 - 20]",
                "executables": {"exe": "exe_key"},
                "evaluations": [],
            },
            "exe_key": {
                "_class": "Executable",
                "submission": "sub_key",
                "filename": "exe",
                "digest": "040f06fd774092478d450774f5ba30c5da78acc8",
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
