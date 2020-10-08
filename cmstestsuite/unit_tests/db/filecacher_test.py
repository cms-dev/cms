#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""Testing suite for FileCacher

"""

import os
import random
import shutil
import unittest
from io import BytesIO

# Needs to be first to allow for monkey patching the DB connection string.
from cmstestsuite.unit_tests.databasemixin import DatabaseMixin

from cms.db.filecacher import FileCacher
from cmscommon.digest import Digester, bytes_digest


class RandomFile:
    """Simulate a random file with dim bytes, calculating its
    SHA1 hash.

    """
    def __init__(self, dim):
        self.dim = dim
        self.digester = Digester()

    def read(self, byte_num):
        """Read byte_num bytes from the source and return them,
        updating the hashing.

        byte_num (int): number of bytes to read.

        return (string): byte_num bytes of content.

        """
        if byte_num > self.dim:
            byte_num = self.dim
        if byte_num == 0:
            return b''
        buf = os.urandom(byte_num)
        self.dim -= len(buf)
        self.digester.update(buf)
        return buf

    def close(self):
        """Do nothing.

        """
        pass

    @property
    def digest(self):
        """Digest of the data read from the source file.

        return (string): digest.

        """
        return self.digester.digest()


class HashingFile:
    """Hashes the content written to this files.

    """
    def __init__(self):
        self.digester = Digester()

    def write(self, buf):
        """Update the hashing with the content of buf.

        buf (string): new content for the file.

        return (int): length of buf.

        """
        self.digester.update(buf)
        return len(buf)

    @property
    def digest(self):
        """Digest of the data written in the file.

        return (string): digest.

        """
        return self.digester.digest()

    def close(self):
        """Do nothing, because there is no hidden file we are writing
        to.

        """
        pass


class TestFileCacherBase:
    """Base class for performing tests for the FileCacher service.

    """

    def _setUp(self, file_cacher):
        """Common initialization that should be called by derived classes."""
        self.file_cacher = file_cacher
        self.cache_base_path = self.file_cacher.file_dir
        self.cache_path = None
        self.content = None
        self.fake_content = None
        self.digest = None
        self.file_obj = None

    def check_stored_file(self, digest):
        """Ensure that a given file digest has been stored correctly."""
        # Remove it from the filesystem.
        cache_path = os.path.join(self.cache_base_path, digest)
        try:
            os.unlink(cache_path)
        except FileNotFoundError:
            pass

        # Pull it out of the file_cacher and compute the hash
        hash_file = HashingFile()
        try:
            self.file_cacher.get_file_to_fobj(digest, hash_file)
        except Exception as error:
            self.fail("Error received: %r." % error)
        my_digest = hash_file.digest
        hash_file.close()

        # Ensure the digest matches.
        if digest != my_digest:
            self.fail("Content differs.")
        if not os.path.exists(cache_path):
            self.fail("File not stored in local cache.")

    def test_file_life(self):
        """Send a ~100B random binary file to the storage through
        FileCacher as a file-like object. FC should cache the content
        locally.

        Then retrieve it.

        Then check its size.

        Then get it back.

        Then delete it.

        """
        self.size = 100
        self.content = bytes(random.getrandbits(8) for _ in range(self.size))

        data = self.file_cacher.put_file_from_fobj(BytesIO(self.content),
                                                   "Test #000")

        if not os.path.exists(os.path.join(self.cache_base_path, data)):
            self.fail("File not stored in local cache.")
        with open(os.path.join(self.cache_base_path, data), "rb") as f:
            if f.read() != self.content:
                self.fail("Local cache's content differ "
                          "from original file.")
        self.cache_path = os.path.join(self.cache_base_path, data)
        self.digest = data

        # Retrieve the file.
        self.fake_content = b"Fake content.\n"
        with open(self.cache_path, "wb") as cached_file:
            cached_file.write(self.fake_content)
        try:
            data = self.file_cacher.get_file(self.digest)
        except Exception as error:
            self.fail("Error received: %r." % error)

        received = data.read()
        data.close()
        if received != self.fake_content:
            if received == self.content:
                self.fail("Did not use the cache even if it could.")
            self.fail("Content differ.")

        # Check the size of the file.
        try:
            size = self.file_cacher.get_size(self.digest)
        except Exception as error:
            self.fail("Error received: %r." % error)

        if size != self.size:
            self.fail("The size is wrong: %d instead of %d" %
                      (size, self.size))

        # Get file from FileCacher.
        os.unlink(self.cache_path)
        try:
            data = self.file_cacher.get_file(self.digest)
        except Exception as error:
            self.fail("Error received: %r." % error)

        received = data.read()
        data.close()
        if received != self.content:
            self.fail("Content differ.")
        if not os.path.exists(self.cache_path):
            self.fail("File not stored in local cache.")
        with open(self.cache_path, "rb") as f:
            if f.read() != self.content:
                self.fail("Local cache's content differ " +
                          "from original file.")

        # Delete the file through FS and tries to get it again through
        # FC.
        try:
            self.file_cacher.delete(digest=self.digest)
        except Exception as error:
            self.fail("Error received: %s." % error)

        else:
            with self.assertRaises(Exception):
                self.file_cacher.get_file(self.digest)

    def test_fetch_missing_file(self):
        """Get unexisting file from FileCacher.

        """
        with self.assertRaises(Exception):
            self.file_cacher.get_file(self.digest)

    def test_file_as_content(self):
        """Send a ~100B random binary file to the storage through
        FileCacher as a string. FC should cache the content locally.

        Then retrieve it as a string.

        """
        self.content = bytes(random.getrandbits(8) for _ in range(100))

        try:
            data = self.file_cacher.put_file_content(self.content,
                                                     "Test #005")
        except Exception as error:
            self.fail("Error received: %r." % error)
            return

        if not os.path.exists(os.path.join(self.cache_base_path, data)):
            self.fail("File not stored in local cache.")
        with open(os.path.join(self.cache_base_path, data), "rb") as f:
            if f.read() != self.content:
                self.fail("Local cache's content differ "
                          "from original file.")
        self.cache_path = os.path.join(self.cache_base_path, data)
        self.digest = data

        # Retrieve the file as a string.
        self.fake_content = b"Fake content.\n"
        with open(self.cache_path, "wb") as cached_file:
            cached_file.write(self.fake_content)
        try:
            data = self.file_cacher.get_file_content(self.digest)
        except Exception as error:
            self.fail("Error received: %r." % error)
            return

        if data != self.fake_content:
            if data == self.content:
                self.fail("Did not use the cache even if it could.")
            else:
                self.fail("Content differ.")

    def test_big_file(self):
        """Put a ~10MB file into the storage (using a specially
        crafted file-like object).

        Then get it back.

        """
        rand_file = RandomFile(10_000_000)
        try:
            data = self.file_cacher.put_file_from_fobj(rand_file, "Test #007")
        except Exception as error:
            self.fail("Error received: %r." % error)
        if rand_file.dim != 0:
            self.fail("The input file wasn't read completely.")
        my_digest = rand_file.digest
        rand_file.close()

        if not os.path.exists(os.path.join(self.cache_base_path, data)):
            self.fail("File not stored in local cache.")
        if my_digest != data:
            self.fail("File received with wrong hash.")
        self.cache_path = os.path.join(self.cache_base_path, data)
        self.digest = data

        # Check file is stored correctly in FileCacher.
        self.check_stored_file(self.digest)

        self.file_cacher.delete(self.digest)

    def test_file_duplicates(self):
        """Send multiple copies of the a file into FileCacher.

        Generates a random file and attempts to store them into the FileCacher.
        FC should handle this gracefully and only end up with one copy.

        """
        content = os.urandom(100)
        digest = bytes_digest(content)

        # Test writing the same file to the DB in parallel.
        # Create empty files.
        num_files = 4
        fobjs = []
        for _ in range(num_files):
            fobj = self.file_cacher.backend.create_file(digest)
            # As the file contains random data, we don't expect to have put
            # this into the DB previously.
            assert fobj is not None
            fobjs.append(fobj)

        # Close them in a different order. Seed to make the shuffle
        # deterministic.
        r = random.Random()
        r.seed(num_files)
        r.shuffle(fobjs)

        # Write the files and commit them.
        for i, fobj in enumerate(fobjs):
            fobj.write(content)
            # Ensure that only one copy made it into the database.
            commit_ok = \
                self.file_cacher.backend.commit_file(fobj,
                                                     digest,
                                                     desc='Copy %d' % i)
            # Only the first commit should succeed.
            assert commit_ok == (i == 0), \
                "Commit of %d was %s unexpectedly" % (i, commit_ok)

        # Check that the file was stored correctly.
        self.check_stored_file(digest)


class TestFileCacherDB(TestFileCacherBase, DatabaseMixin, unittest.TestCase):
    """Tests for the FileCacher service with a database backend."""

    def setUp(self):
        super().setUp()
        file_cacher = FileCacher()
        self._setUp(file_cacher)


class TestFileCacherFS(TestFileCacherBase, unittest.TestCase):
    """Tests for the FileCacher service with a filesystem backend."""

    def setUp(self):
        super().setUp()
        file_cacher = FileCacher(path="fs-storage")
        self._setUp(file_cacher)

    def tearDown(self):
        shutil.rmtree("fs-storage", ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
