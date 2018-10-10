#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

import io
import tarfile
import unittest
import zipfile
from collections import namedtuple
from unittest.mock import patch

from cms.server.contest.submission import ReceivedFile, InvalidArchive, \
    extract_files_from_archive, extract_files_from_tornado


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
        self.assertCountEqual(
            extract_files_from_archive(archive_data.getvalue()), files)

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
        self.assertCountEqual(
            extract_files_from_archive(archive_data.getvalue()), files)

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
        self.assertCountEqual(
            extract_files_from_archive(archive_data.getvalue()),
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
        self.assertCountEqual(
            extract_files_from_archive(archive_data.getvalue()),
            [ReceivedFile(None, "foo", b"some content")])

    # The behavior documented in this test actually only happens when
    # patool uses 7z (which happens if it is found installed). Otherwise
    # it falls back on Python's zipfile module which outright fails.
    # Due to this difference we do not run this test.
    @unittest.skip("Depends on what is installed in the system.")
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
        self.assertRegex(f.filename, "tmp[a-z0-9_]+~")
        self.assertEqual(f.content, b"some content")

    def test_multiple_slashes_are_compressed(self):
        # This is a (probably expected and) desirable behavior.
        archive_data = io.BytesIO()
        with zipfile.ZipFile(archive_data, "w") as f:
            f.writestr("foo//bar", b"some content")
        self.assertCountEqual(
            extract_files_from_archive(archive_data.getvalue()),
            [ReceivedFile(None, "bar", b"some content")])

    def test_paths_that_might_escape(self):
        # This should check that the extracted files cannot "escape"
        # from the temporary directory where they're being extracted to.
        filenames = ["../foo/bar", "/foo/bar"]
        for filename in filenames:
            archive_data = io.BytesIO()
            with zipfile.ZipFile(archive_data, "w") as f:
                f.writestr(filename, b"some content")
            self.assertCountEqual(
                extract_files_from_archive(archive_data.getvalue()),
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
        super().setUp()

        patcher = patch(
            "cms.server.contest.submission.file_retrieval"
            ".extract_files_from_archive")
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
        self.assertCountEqual(extract_files_from_tornado(tornado_files), [
            ReceivedFile("foo.%l", "foo.py", b"some python stuff"),
            ReceivedFile("bar.%l", "bar.c", b"one file in C"),
            ReceivedFile("bar.%l", "bar.cxx", b"the same file in C++")])

    def test_not_archive_if_other_codenames(self):
        tornado_files = {
            "submission": [MockHTTPFile("sub.zip", b"this is an archive")],
            "foo.%l": [MockHTTPFile("foo.c", b"this is something else")]}
        self.assertCountEqual(extract_files_from_tornado(tornado_files), [
            ReceivedFile("submission", "sub.zip", b"this is an archive"),
            ReceivedFile("foo.%l", "foo.c", b"this is something else")])

    def test_not_archive_if_other_files(self):
        tornado_files = {
            "submission": [MockHTTPFile("sub.zip", b"this is an archive"),
                           MockHTTPFile("sub2.zip", b"this is another one")]}
        self.assertCountEqual(extract_files_from_tornado(tornado_files), [
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


if __name__ == "__main__":
    unittest.main()
