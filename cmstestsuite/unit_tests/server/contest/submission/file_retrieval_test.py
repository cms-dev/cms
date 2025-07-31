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

import base64
import io
import sys
import tarfile
import unittest
import zipfile
from collections import namedtuple
from unittest.mock import patch
import zlib

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

    @unittest.skipIf(sys.version_info < (3, 12), "this archive crashes zipfile before py3.12")
    def test_empty_filename(self):
        archive_data = io.BytesIO()
        with zipfile.ZipFile(archive_data, "w") as f:
            # Need ZipInfo because of "bug" in writestr.
            f.writestr(zipfile.ZipInfo(""), b"some content")
        res = extract_files_from_archive(archive_data.getvalue())
        self.assertEqual(len(res), 1)
        f = res[0]
        self.assertIsNone(f.codename)
        self.assertEqual(f.filename, "")
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

    def test_zip_bomb_size_tarbz(self):
        # this test should finish almost instantly, instead of trying to
        # decompress the entire archive.

        # This data is a tar.bz2 file that contains one file, with 64GB of null
        # bytes.
        data = zlib.decompress(base64.b64decode("""
eJztyu9rzHEAAODPjHabezHaSSm+Yy1WlHKxpI5km1d34/vi9uaKKeUNI8kL2khRy3UK+XG1ue4uKaF
TvNBerNTe2isvpDVLFNNaebMS/4Q3z+vnOTR0unf3wXz3sXw1f6625kqyMDpTzDStzGUy2bAQfcqGKJ
GIQql1R9/4wLcT4XL5SbTlaaIycWe2pTK8Zzpc+vm98PXRQO54fLgex6nc3h/PHkfbTlYbcS5e3/5y8
OaHdFv/pq2T6za8qBzp6Xo+9+vLvpmR97W29JkD2dr4cmNt5u61d1dfLS1/XNjfe33jjULLxbe333R2
FUv9fUsdqdKpdPFzeedi6vd8SIYQxkJzYvXscM+qoWK99TznnHPOOeecc84555xzzjnnnHPOOeecc84
555xzzjnnnHPOOeecc84555xzzjnnnHPOOeecc84555xzzjnnnHPOOeecc84555xzzjnnnHPOOeecc8
4555xzzjnnnHPOOeecc84555xzzjnnnHPOOeecc845/w/+sD79erF5pfzX2/+N5NSD6v3JpsZgtHnX/
K2zE53bL9w7+gctbrLz"""))

        with self.assertRaises(InvalidArchive) as exc:
            extract_files_from_archive(data, 1_000_000, None)

        self.assertTrue(exc.exception.too_big)


    def test_zip_bomb_count_tarbz(self):
        # this test should finish almost instantly, instead of trying to
        # decompress the entire archive.

        # This data is a tar.bz2 file that contains 120 million empty files,
        # all named "x". (the decompressed tar file would be 6GB.)
        block = base64.b64decode("""
MUFZJlNZFfIt8gXzb9uAyIBAAHcAAADgAB5ACAAwAVgAUyYmQZGFMmJkGRgUqmo2poaD1GgVKm4FSpg
CRQ7gqVPYKlTwCpUyBUqdgKlTIKlTIJFDYBUqbAqVOAVKmAJFDAKlTYCiSuQVKmAUSVgFSpyCpU8gqV
OAVKmAVKnIKlTqCpU3BIofQVKnwFSpoFSpoFSpoFSp+BUqZBUqfw==""")
        data = b"BZh9" + 1000*block + bytes.fromhex("1772453850905d4ab55d")

        with self.assertRaises(InvalidArchive) as exc:
            extract_files_from_archive(data, None, 1000)

        self.assertTrue(exc.exception.too_many_files)

    def test_zip_bomb_size_zip(self):
        # Similar to test_zip_bomb_size_tarbz. This test uses zip's
        # (little-used?) bzip2 mode, because bzip2 is the most efficient at
        # compressing large amounts of null bytes. It should be fine for the
        # test though, we care more about zipfile's API here than the
        # underlying compression algorithm.

        # This data is a zip file with one file containing 16GB of null bytes.
        data = zlib.decompress(base64.b64decode("""
eJzt2r9qwlAUx/Fzm1hUpEixm4MKCi6pbi1d/IdLEIJOyeKojxA3FScHkVBwdejSZ3Ap4t7JUQQHVx9
Bk6LgUDfH7+9wzzmXzyscy9R0Q0Ri8vG8cpLbWvp4jpKEuEriEkT338H4W6XidN+LZTvXsp8iu61qT0
ryIxJOSaHfqFfm2e9of4bjOI7jOI7jOI7jOI7jOI7jOI7jOI7jOI7jOI7jOI7jOI7j9/Pxb+9FOutrX
3vT/Gcz9Lbw8svRcLMvupapHgzt9o38JV+DoP97MW+ZocdgKr+q/sy8Br8TACk9vA=="""))

        with self.assertRaises(InvalidArchive) as exc:
            extract_files_from_archive(data, 1_000_000, None)

        self.assertTrue(exc.exception.too_big)

    def test_zip_bomb_count_zip(self):
        # This test is not as extreme as the other zip-bomb ones, because zip
        # does not have metadata compression. Once we have a zip in memory (as
        # returned by tornado), constructing the file list is quite cheap, so
        # zipfile doesn't even have an API to not construct the entire file
        # list.
        archive_data = io.BytesIO()
        with zipfile.ZipFile(archive_data, "w") as f:
            for i in range(1000):
                f.writestr(f"{i}", b"x")

        with self.assertRaises(InvalidArchive) as exc:
            extract_files_from_archive(archive_data.getvalue(), 500, 50)

        # size limit 500 vs total file size 1000 (1 byte per file) means we
        # will hit both limits, but the file count limit should be hit first.
        self.assertTrue(exc.exception.too_many_files)


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
            b"this is an archive", None, None)

    def test_bad_archive(self):
        tornado_files = {
            "submission": [MockHTTPFile("archive.zip",
                                        b"this is not a valid archive")]}
        self.extract_files_from_archive.side_effect = InvalidArchive
        with self.assertRaises(InvalidArchive):
            extract_files_from_tornado(tornado_files)
        self.extract_files_from_archive.assert_called_once_with(
            b"this is not a valid archive", None, None)


if __name__ == "__main__":
    unittest.main()
