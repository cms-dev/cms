#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import io
import os
import random
from StringIO import StringIO
import hashlib
import shutil
import unittest

from cms.db.filecacher import FileCacher


class RandomFile(object):
    """Simulate a random file with dim bytes, calculating its
    SHA1 hash.

    """
    def __init__(self, dim):
        self.dim = dim
        # FIXME We could use os.urandom() instead.
        self.source = io.open('/dev/urandom', 'rb')
        self.hasher = hashlib.sha1()

    def read(self, byte_num):
        """Read byte_num bytes from the source and return them,
        updating the hashing.

        byte_num (int): number of bytes to read.

        return (string): byte_num bytes of content.

        """
        if byte_num > self.dim:
            byte_num = self.dim
        if byte_num == 0:
            return ''
        buf = self.source.read(byte_num)
        self.dim -= len(buf)
        self.hasher.update(buf)
        return buf

    def close(self):
        """Close the source file.

        """
        self.source.close()

    @property
    def digest(self):
        """Digest of the data read from the source file.

        return (string): digest.

        """
        return self.hasher.hexdigest()


class HashingFile(object):
    """Hashes the content written to this files.

    """
    def __init__(self):
        self.hasher = hashlib.sha1()

    def write(self, buf):
        """Update the hashing with the content of buf.

        buf (string): new content for the file.

        return (int): length of buf.

        """
        self.hasher.update(buf)
        return len(buf)

    @property
    def digest(self):
        """Digest of the data written in the file.

        return (string): digest.

        """
        return self.hasher.hexdigest()

    def close(self):
        """Do nothing, because there is no hidden file we are writing
        to.

        """
        pass


class TestFileCacher(unittest.TestCase):
    """Service that performs automatically some tests for the
    FileCacher service.

    """

    def setUp(self):
        self.file_cacher = FileCacher()
        #self.file_cacher = FileCacher(self, path="fs-storage")
        self.cache_base_path = self.file_cacher.file_dir
        self.cache_path = None
        self.content = None
        self.fake_content = None
        self.digest = None
        self.file_obj = None

    def tearDown(self):
        shutil.rmtree(self.cache_base_path, ignore_errors=True)

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
        self.content = b"".join(chr(random.randint(0, 255))
                                for unused_i in xrange(self.size))

        data = self.file_cacher.put_file_from_fobj(StringIO(self.content),
                                                   u"Test #000")

        if not os.path.exists(os.path.join(self.cache_base_path, data)):
            self.fail("File not stored in local cache.")
        elif io.open(os.path.join(self.cache_base_path, data),
                     "rb").read() != self.content:
            self.fail("Local cache's content differ "
                      "from original file.")
        else:
            self.cache_path = os.path.join(self.cache_base_path, data)
            self.digest = data

        # Retrieve the file.
        self.fake_content = "Fake content.\n"
        with io.open(self.cache_path, "wb") as cached_file:
            cached_file.write(self.fake_content)
        try:
            data = self.file_cacher.get_file(self.digest)
        except Exception as error:
            self.fail("Error received: %r." % error)
            return

        received = data.read()
        data.close()
        if received != self.fake_content:
            if received == self.content:
                self.fail("Did not use the cache even if it could.")
            else:
                self.fail("Content differ.")

        # Check the size of the file.
        try:
            size = self.file_cacher.get_size(self.digest)
        except Exception as error:
            self.fail("Error received: %r." % error)
            return

        if size != self.size:
            self.fail("The size is wrong: %d instead of %d" %
                      (size, self.size))

        # Get file from FileCacher.
        os.unlink(self.cache_path)
        try:
            data = self.file_cacher.get_file(self.digest)
        except Exception as error:
            self.fail("Error received: %r." % error)
            return

        received = data.read()
        data.close()
        if received != self.content:
            self.fail("Content differ.")
        elif not os.path.exists(self.cache_path):
            self.fail("File not stored in local cache.")
        elif io.open(self.cache_path, "rb").read() != self.content:
            self.fail("Local cache's content differ " +
                      "from original file.")

        # Delete the file through FS and tries to get it again through
        # FC.
        try:
            self.file_cacher.delete(digest=self.digest)
        except Exception as error:
            self.fail("Error received: %s." % error)
            return

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
        self.content = b"".join(chr(random.randint(0, 255))
                                for unused_i in xrange(100))

        try:
            data = self.file_cacher.put_file_content(self.content,
                                                     u"Test #005")
        except Exception as error:
            self.fail("Error received: %r." % error)
            return

        if not os.path.exists(os.path.join(self.cache_base_path, data)):
            self.fail("File not stored in local cache.")
        elif io.open(os.path.join(self.cache_base_path, data),
                     "rb").read() != self.content:
            self.fail("Local cache's content differ "
                      "from original file.")
        else:
            self.cache_path = os.path.join(self.cache_base_path, data)
            self.digest = data

        # Retrieve the file as a string.
        self.fake_content = "Fake content.\n"
        with io.open(self.cache_path, "wb") as cached_file:
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
        rand_file = RandomFile(10000000)
        try:
            data = self.file_cacher.put_file_from_fobj(rand_file, u"Test #007")
        except Exception as error:
            self.fail("Error received: %r." % error)
            return
        if rand_file.dim != 0:
            self.fail("The input file wasn't read completely.")
        my_digest = rand_file.digest
        rand_file.close()

        if not os.path.exists(os.path.join(self.cache_base_path, data)):
            self.fail("File not stored in local cache.")
        elif my_digest != data:
            self.fail("File received with wrong hash.")
        else:
            self.cache_path = os.path.join(self.cache_base_path, data)
            self.digest = data

        # Get the ~100MB file from FileCacher.
        os.unlink(self.cache_path)
        hash_file = HashingFile()
        try:
            self.file_cacher.get_file_to_fobj(self.digest, hash_file)
        except Exception as error:
            self.fail("Error received: %r." % error)
            return
        my_digest = hash_file.digest
        hash_file.close()

        try:
            if self.digest != my_digest:
                self.fail("Content differs.")
            elif not os.path.exists(self.cache_path):
                self.fail("File not stored in local cache.")
        finally:
            self.file_cacher.delete(self.digest)


if __name__ == "__main__":
    unittest.main()
