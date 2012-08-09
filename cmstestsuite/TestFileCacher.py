#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
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
from StringIO import StringIO
import hashlib

from cms import default_argument_parser, config, logger
from cms.async import ServiceCoord
from cms.async.TestService import TestService
from cms.db.FileCacher import FileCacher


class RandomFile:
    """Simulate a random file with dim bytes, calculating its
    SHA1 hash.

    """
    def __init__(self, dim):
        self.dim = dim
        self.source = open('/dev/urandom')
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


class HashingFile:
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


class TestFileCacher(TestService):
    """Service that performs automatically some tests for the
    FileCacher service.

    """

    def __init__(self, shard):
        logger.initialize(ServiceCoord("TestFileCacher", shard))
        TestService.__init__(self, shard, custom_logger=logger)

        # Assume we store the cache in "./cache/fs-cache-TestFileCacher-0/"
        self.cache_base_path = os.path.join(config.cache_dir,
                                            "fs-cache-TestFileCacher-0")
        self.cache_path = None
        self.content = None
        self.fake_content = None
        self.digest = None
        self.file_obj = None
        self.file_cacher = FileCacher(self)
        #self.file_cacher = FileCacher(self, path="fs-storage")

    def prepare(self):
        """Initialization for the test code - make sure that the cache
        is empty before testing.

        """
        logger.info("Please delete directory %s before." %
                    self.cache_base_path)

### TEST 000 ###

    def test_000(self):
        """Send a ~100B random binary file to the storage through
        FileCacher as a file-like object. FC should cache the content
        locally.

        """
        self.size = 100
        self.content = "".join(chr(random.randint(0, 255))
                               for unused_i in xrange(self.size))

        logger.info("  I am sending the ~100B binary file to FileCacher")
        try:
            data = self.file_cacher.put_file(file_obj=StringIO(self.content),
                                             description="Test #000")
        except Exception as error:
            self.test_end(False, "Error received: %r." % error)

        if not os.path.exists(
            os.path.join(self.cache_base_path, "objects", data)):
            self.test_end(False, "File not stored in local cache.")
        elif open(os.path.join(self.cache_base_path, "objects", data),
                  "rb").read() != self.content:
            self.test_end(False, "Local cache's content differ "
                          "from original file.")
        else:
            self.cache_path = os.path.join(self.cache_base_path, "objects",
                                           data)
            self.digest = data
            self.test_end(True, "Data sent and cached without error.")

### TEST 001 ###

    def test_001(self):
        """Retrieve the file.

        """
        logger.info("  I am retrieving the ~100B binary file from FileCacher")
        self.fake_content = "Fake content.\n"
        with open(self.cache_path, "wb") as cached_file:
            cached_file.write(self.fake_content)
        try:
            data = self.file_cacher.get_file(digest=self.digest,
                                             temp_file_obj=True)
        except Exception as error:
            self.test_end(False, "Error received: %r." % error)

        received = data.read()
        data.close()
        if received != self.fake_content:
            if received == self.content:
                self.test_end(False,
                              "Did not use the cache even if it could.")
            else:
                self.test_end(False, "Content differ.")
        else:
            self.test_end(True, "Data object received correctly.")

### TEST 002 ###

    def test_002(self):
        """Check the size of the file.

        """
        logger.info("  I am checking the size of the ~100B binary file")
        try:
            size = self.file_cacher.get_size(self.digest)
        except Exception as error:
            self.test_end(False, "Error received: %r." % error)

        if size == self.size:
            self.test_end(True, "The size is correct.")
        else:
            self.test_end(False, "The size is wrong: %d instead of %d" %
                          (size, self.size))

### TEST 003 ###

    def test_003(self):
        """Get file from FileCacher.

        """
        logger.info("  I am retrieving the file from FileCacher " +
                    "after deleting the cache.")
        os.unlink(self.cache_path)
        try:
            data = self.file_cacher.get_file(digest=self.digest,
                                             temp_file_obj=True)
        except Exception as error:
            self.test_end(False, "Error received: %r." % error)

        received = data.read()
        data.close()
        if received != self.content:
            self.test_end(False, "Content differ.")
        elif not os.path.exists(self.cache_path):
            self.test_end(False, "File not stored in local cache.")
        elif open(self.cache_path).read() != self.content:
            self.test_end(False, "Local cache's content differ " +
                          "from original file.")
        else:
            self.test_end(True, "Content object received " +
                          "and cached correctly.")

### TEST 004 ###

    def test_004(self):
        """Delete the file through FS and tries to get it again through FC.

        """
        logger.info("  I am deleting the file from FileCacher.")
        try:
            self.file_cacher.delete(digest=self.digest)
        except Exception as error:
            self.test_end(False, "Error received: %s." % error)

        else:
            logger.info("  File deleted correctly.")
            logger.info("  I am getting the file from FileCacher.")
            try:
                self.file_cacher.get_file(digest=self.digest)
            except Exception as error:
                self.test_end(True, "Correctly received an error: %r." % error)
            else:
                self.test_end(False, "Did not receive error.")

### TEST 005 ###

    def test_005(self):
        """Get unexisting file from FileCacher.

        """
        logger.info("  I am retrieving an unexisting file from FileCacher.")
        try:
            self.file_cacher.get_file(digest=self.digest, temp_file_obj=True)
        except Exception as error:
            self.test_end(True, "Correctly received an error: %r." % error)
        else:
            self.test_end(False, "Did not receive error.")

### TEST 006 ###

    def test_006(self):
        """Send a ~100B random binary file to the storage through
        FileCacher as a string. FC should cache the content locally.

        """
        self.content = "".join(chr(random.randint(0, 255))
                               for unused_i in xrange(100))

        logger.info("  I am sending the ~100B binary file to FileCacher")
        try:
            data = self.file_cacher.put_file(binary_data=self.content,
                                             description="Test #005")
        except Exception as error:
            self.test_end(False, "Error received: %r." % error)

        if not os.path.exists(
            os.path.join(self.cache_base_path, "objects", data)):
            self.test_end(False, "File not stored in local cache.")
        elif open(os.path.join(self.cache_base_path, "objects", data),
                  "rb").read() != self.content:
            self.test_end(False, "Local cache's content differ "
                          "from original file.")
        else:
            self.cache_path = os.path.join(self.cache_base_path, "objects",
                                           data)
            self.digest = data
            self.test_end(True, "Data sent and cached without error.")

### TEST 007 ###

    def test_007(self):
        """Retrieve the file as a string.

        """
        logger.info("  I am retrieving the ~100B binary file from FileCacher "
                    "using get_file_to_string()")
        self.fake_content = "Fake content.\n"
        with open(self.cache_path, "wb") as cached_file:
            cached_file.write(self.fake_content)
        try:
            data = self.file_cacher.get_file(digest=self.digest, string=True)
        except Exception as error:
            self.test_end(False, "Error received: %r." % error)

        if data != self.fake_content:
            if data == self.content:
                self.test_end(False,
                              "Did not use the cache even if it could.")
            else:
                self.test_end(False, "Content differ.")
        else:
            self.test_end(True, "Data received correctly.")

### TEST 008 ###

    def test_008(self):
        """Put a ~100MB file into the storage (using a specially
        crafted file-like object).

        """
        logger.info("  I am sending the ~100MB binary file to FileCacher")
        rand_file = RandomFile(100000000)
        try:
            data = self.file_cacher.put_file(file_obj=rand_file,
                                             description="Test #007")
        except Exception as error:
            self.test_end(False, "Error received: %r." % error)
        if rand_file.dim != 0:
            self.test_end(False, "The input file wasn't read completely.")
        my_digest = rand_file.digest
        rand_file.close()

        if not os.path.exists(
            os.path.join(self.cache_base_path, "objects", data)):
            self.test_end(False, "File not stored in local cache.")
        elif my_digest != data:
            self.test_end(False, "File received with wrong hash.")
        else:
            self.cache_path = os.path.join(self.cache_base_path, "objects",
                                           data)
            self.digest = data
            self.test_end(True, "Data sent and cached without error.")

### TEST 009 ###

    def test_009(self):
        """Get the ~100MB file from FileCacher.

        """
        logger.info("  I am retrieving the ~100MB file from FileCacher " +
                    "after deleting the cache.")
        os.unlink(self.cache_path)
        hash_file = HashingFile()
        try:
            self.file_cacher.get_file(digest=self.digest, file_obj=hash_file)
        except Exception as error:
            self.test_end(False, "Error received: %r." % error)
        my_digest = hash_file.digest
        hash_file.close()

        try:
            if self.digest != my_digest:
                self.test_end(False, "Content differs.")
            elif not os.path.exists(self.cache_path):
                self.test_end(False, "File not stored in local cache.")
            else:
                self.test_end(True, "Content object received " +
                              "and cached correctly.")
        finally:
            self.file_cacher.delete(self.digest)


def main():
    """Parse arguments and launch service.

    """
    default_argument_parser("Test for CMS FileCacher class.",
                            TestFileCacher).run()

if __name__ == "__main__":
    main()
