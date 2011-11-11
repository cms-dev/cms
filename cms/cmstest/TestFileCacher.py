#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2011 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2011 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2011 Matteo Boscariol <boscarim@hotmail.com>
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

from cms.async.AsyncLibrary import rpc_callback, logger
from cms.async.TestService import TestService
from cms.async import ServiceCoord, Config
from cms.service.FileStorage import FileCacher


class TestFileCacher(TestService):
    """Service that performs automatically some tests for the
    FileCacher service.

    """

    def __init__(self, shard):
        logger.initialize(ServiceCoord("TestFileCacher", shard))
        logger.debug("TestFileCacher.__init__")
        TestService.__init__(self, shard)

        # Assume we store the cache in "./cache/fs-cache-TestFileCacher-0/"
        self.cache_base_path = os.path.join(Config._cache_dir, "fs-cache-TestFileCacher-0")
        self.cache_path = None
        self.content = None
        self.fake_content = None
        self.digest = None
        self.file_obj = None

    def prepare(self):
        self.FS = self.connect_to(ServiceCoord("FileStorage", 0))
        if os.path.exists(self.cache_base_path):
            logger.error("Please delete directory %s before." %
                         self.cache_base_path)
            self.exit()
        self.FC = FileCacher(self, self.FS)

### TEST 000 ###

    def test_000(self):
        """Send a ~100B random binary file to FileStorage through
        FileCacher as a file-like object. FC should cache the content
        locally.

        """
        if not self.FS.connected:
            self.test_end(False, "Please start FileStorage.", True)
            return

        self.content = ""
        for i in xrange(100):
            self.content += chr(random.randint(0, 255))

        logger.info("  I am sending the ~100B binary file to FileCacher")
        try:
            data = self.FC.put_file(file_obj=StringIO(self.content),
                                    description="Test #000")
        except Exception as e:
            self.test_end(False, "Error received: %r." % e)

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
        if not self.FS.connected:
            self.test_end(False, "Please start FileStorage.", True)
            return

        logger.info("  I am retrieving the ~100B binary file from FileCacher")
        self.fake_content = "Fake content.\n"
        with open(self.cache_path, "wb") as cached_file:
            cached_file.write(self.fake_content)
        try:
            data = self.FC.get_file(digest=self.digest, temp_file_obj=True)
        except Exception as e:
            self.test_end(False, "Error received: %r." % e)

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
        """Get file from FileCacher.

        """
        if not self.FS.connected:
            self.test_end(False, "Please start FileStorage.", True)
            return

        logger.info("  I am retrieving the file from FileCacher " +
                    "after deleting the cache.")
        os.unlink(self.cache_path)
        try:
            data = self.FC.get_file(digest=self.digest, temp_file_obj=True)
        except Exception as e:
            self.test_end(False, "Error received: %r." % e)

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

### TEST 003 ###

    def test_003(self):
        """Delete the file through FS and tries to get it again through FC.

        """
        if not self.FS.connected:
            self.test_end(False, "Please start FileStorage.", True)
            return

        logger.info("  I am deleting the file from FileStorage.")
        self.FS.delete(digest=self.digest,
                       callback=TestFileCacher.test_003_callback,
                       plus=("Test #", 3))

    @rpc_callback
    def test_003_callback(self, data, plus, error=None):
        """Called with an error.

        """
        if error is not None:
            self.test_end(False, "Error received: %s." % error)
        elif plus != ("Test #", 3):
            self.test_end(False, "Plus object not received correctly.")
        elif not data:
            self.test_end(False, "File not deleted correctly.")
        else:
            logger.info("  File deleted correctly.")
            logger.info("  I am getting the file from FileCacher.")
            try:
                data = self.FC.get_file(digest=self.digest)
            except Exception as e:
                self.test_end(True, "Correctly received an error: %r." % e)
            else:
                self.test_end(False, "Did not receive error.")

### TEST 004 ###

    def test_004(self):
        """Get unexisting file from FileCacher.

        """
        if not self.FS.connected:
            self.test_end(False, "Please start FileStorage.", True)
            return

        logger.info("  I am retrieving an unexisting file from FileCacher.")
        try:
            data = self.FC.get_file(digest=self.digest, temp_file_obj=True)
        except Exception as e:
            self.test_end(True, "Correctly received an error: %r." % e)
        else:
            self.test_end(False, "Did not receive error.")

### TEST 005 ###

    def test_005(self):
        """Send a ~100B random binary file to FileStorage through
        FileCacher as a string. FC should cache the content locally.

        """
        if not self.FS.connected:
            self.test_end(False, "Please start FileStorage.", True)
            return

        self.content = ""
        for i in xrange(100):
            self.content += chr(random.randint(0, 255))

        logger.info("  I am sending the ~100B binary file to FileCacher")
        try:
            data = self.FC.put_file(binary_data=self.content,
                                    description="Test #005")
        except Exception as e:
            self.test_end(False, "Error received: %r." % e)

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

### TEST 006 ###

    def test_006(self):
        """Retrieve the file as a string.

        """
        if not self.FS.connected:
            self.test_end(False, "Please start FileStorage.", True)
            return

        logger.info("  I am retrieving the ~100B binary file from FileCacher "
                    "using get_file_to_string()")
        self.fake_content = "Fake content.\n"
        with open(self.cache_path, "wb") as cached_file:
            cached_file.write(self.fake_content)
        try:
            data = self.FC.get_file(digest=self.digest, string=True)
        except Exception as e:
            self.test_end(False, "Error received: %r." % e)

        if data != self.fake_content:
            if data == self.content:
                self.test_end(False,
                              "Did not use the cache even if it could.")
            else:
                self.test_end(False, "Content differ.")
        else:
            self.test_end(True, "Data received correctly.")


def main():
    import sys
    if len(sys.argv) != 2:
        print sys.argv[0], "shard"
    else:
        TestFileCacher(int(sys.argv[1])).run()


if __name__ == "__main__":
    main()
