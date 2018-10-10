#!/usr/bin/env python3

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

import os
import stat
import unittest
from datetime import timedelta
from unittest.mock import MagicMock, patch

# Needs to be first to allow for monkey patching the DB connection string.
from cmstestsuite.unit_tests.databasemixin import DatabaseMixin

from cms import config
from cms.db import Submission, UserTest
from cms.server.contest.submission import \
    fetch_file_digests_from_previous_submission, StorageFailed, store_local_copy
from cmscommon.datetime import make_datetime
from cmstestsuite.unit_tests.filesystemmixin import FileSystemMixin
from cmstestsuite.unit_tests.testidgenerator import unique_digest, \
    unique_unicode_id


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


class TestFetchFileDigestsFromPreviousSubmission(DatabaseMixin,
                                                 unittest.TestCase):

    def setUp(self):
        super().setUp()

        self.contest = self.add_contest()
        self.participation = self.add_participation(contest=self.contest)
        self.task = self.add_task(contest=self.contest)

    def insert_submission(self, language, file_digests):
        s = self.add_submission(
            language=language, participation=self.participation, task=self.task)
        for codename, digest in file_digests.items():
            self.add_file(filename=codename, digest=digest, submission=s)

    def insert_user_test(
            self, language, input_digest, file_digests, manager_digests):
        t = self.add_user_test(
            language=language, input=input_digest,
            participation=self.participation, task=self.task)
        for codename, digest in file_digests.items():
            self.add_user_test_file(filename=codename, digest=digest,
                                    user_test=t)
        for filename, digest in manager_digests.items():
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
        self.insert_submission("Py2",
                               {"foo.%l": foo_digest, "baz.txt": baz_digest})
        self.assertEqual(self.call(C_LANG, {"foo.%l", "bar.txt"}),
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
        self.insert_user_test("Py2", input_digest,
                              {"foo.%l": foo_digest, "baz.txt": baz_digest},
                              {"spam.c": spam_digest, "eggs.h": eggs_digest})
        self.assertEqual(self.call(C_LANG, {"input",
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

    def test_managers_extension_replacement(self):
        input_digest = unique_digest()
        foo_digest = unique_digest()
        bad_digest = unique_digest()
        # The *full* `.%l` of the codename has to be replaced with the
        # language's primary extension, including the `.`, even when the
        # extension doesn't begin with `.`. This also means that
        # splitting the filename to get the extension out of is most
        # likely a bad approach.
        self.insert_user_test("Pascal", input_digest, dict(),
                              {"foolib.pas": foo_digest,
                               "foo.lib.pas": bad_digest,
                               "foo.pas": bad_digest})
        self.assertEqual(self.call(PASCAL_LANG, {"foo.%l"}, cls=UserTest),
                         {"foo.%l": foo_digest})


class TestStoreLocalCopy(DatabaseMixin, FileSystemMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()

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
                with open(os.path.join(directory, filename), "rb") as f:
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
