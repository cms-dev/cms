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

from cms.async.AsyncLibrary import rpc_callback, logger
from cms.async.TestService import TestService
from cms.async.Utils import random_string
from cms.async import ServiceCoord
from cms.service.FileStorage import FileCacher


class TestFileCacher(TestService):
    """Service that performs automatically some tests for the
    FileCacher service.

    """

    def __init__(self, shard):
        logger.initialize(ServiceCoord("TestFileCacher", shard))
        logger.debug("TestFileCacher.__init__")
        TestService.__init__(self, shard)
        self.FS = self.connect_to(
            ServiceCoord("FileStorage", 0))
        if not self.FS.connected:
            logger.error("Please run the FileStorage service.")
            self.exit()
        if os.path.exists("fs-cache"):
            logger.error("Please delete directory fs-cache before.")
            self.exit()
        self.FC = FileCacher(self, self.FS)


### TEST 000 ###

    def test_000(self):
        """Send a short random binary file to FileCacher through
        FileCacher. FC should cache the content locally.

        """
        path = random_string(16)
        self.content = ""
        for i in xrange(100):
            self.content += chr(random.randint(0, 255))

        logger.info("  I am sending the short binary file to FileCacher")
        self.FC.put_file(binary_data=self.content,
                         description="Test #000",
                         callback=TestFileCacher.test_000_callback,
                         plus=("Test #", 0))

    @rpc_callback
    def test_000_callback(self, data, plus, error=None):
        if error != None:
            self.test_end(False, "Error received: %s." % error)
        elif plus != ("Test #", 0):
            self.test_end(False, "Plus object not received correctly.")
        elif not os.path.exists(
            os.path.join("fs-cache", "objects", data)):
            self.test_end(False, "File not stored in local cache.")
        elif open(os.path.join("fs-cache", "objects", data),
                  "rb").read() != self.content:
            self.test_end(False, "Local cache's content differ " +
                          "from original file.")
        else:
            self.cache_path = os.path.join("fs-cache", "objects", data)
            self.digest = data
            self.test_end(True, "Data sent and cached without error " +
                          "and plus object received.")


### TEST 001 ###

    def test_001(self):
        """Retrieve the file.

        """
        logger.info("  I am retrieving the short binary file from FileCacher")
        self.fake_content = "Fake content.\n"
        with open(self.cache_path, "wb") as f:
            f.write(self.fake_content)
        self.FC.get_file(digest=self.digest,
                         callback=TestFileCacher.test_001_callback,
                         plus=("Test #", 1))

    @rpc_callback
    def test_001_callback(self, data, plus, error=None):
        if error != None:
            self.test_end(False, "Error received: %s." % error)
        elif plus != ("Test #", 1):
            self.test_end(False, "Plus object not received correctly.")
        else:
            received = data.read()
            data.close()
            if received != self.fake_content:
                if received == self.content:
                    self.test_end(False,
                                  "Did not use the cache even if it could.")
                else:
                    self.test_end(False, "Content differ.")
            else:
                self.test_end(True, "Data and plus object received correctly.")


### TEST 002 ###

    def test_002(self):
        """Get file from FileCacher

        """
        logger.info("  I am retrieving the file from FileCacher " +
                    "after deleting the cache.")
        os.unlink(self.cache_path)
        self.FC.get_file(digest=self.digest,
                         callback=TestFileCacher.test_002_callback,
                         plus=("Test #", 2))

    @rpc_callback
    def test_002_callback(self, data, plus, error=None):
        if error != None:
            self.test_end(False, "Error received: %s." % error)
        elif plus != ("Test #", 2):
            self.test_end(False, "Plus object not received correctly.")
        else:
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
                self.test_end(True, "Content and plus object received " +
                              "and cached correctly.")


### TEST 003 ###

    def test_003(self):
        """Delete the file through FS and tries to get it again through FC.

        """
        logger.info("  I am deleting the file from FileStorage.")
        self.FS.delete(digest=self.digest,
                       callback=TestFileCacher.test_003_callback,
                       plus=("Test #", 3))

    @rpc_callback
    def test_003_callback(self, data, plus, error=None):
        if error != None:
            self.test_end(False, "Error received: %s." % error)
        elif plus != ("Test #", 3):
            self.test_end(False, "Plus object not received correctly.")
        elif not data:
            self.test_end(False, "File not deleted correctly.")
        else:
            logger.info("  File deleted correctly.")
            logger.info("  I am getting the file from FileCacher.")
            self.FC.get_file(digest=self.digest,
                             callback=TestFileCacher.test_003_callback_2,
                             plus=("Test #", 3))

    @rpc_callback
    def test_003_callback_2(self, data, plus, error=None):
        if error == None:
            self.test_end(False, "No error received.")
        elif plus != ("Test #", 3):
            self.test_end(False, "Plus object not received correctly.")
        elif data != None:
            self.test_end(False, "Some data received.")
        else:
            self.test_end(True, "Correctly received an error: %s." % error)


### TEST 004 ###

    def test_004(self):
        """Get unexisting file from FileCacher

        """
        logger.info("  I am retrieving an unexisting file from FileCacher.")
        self.FC.get_file(digest=self.digest,
                         callback=TestFileCacher.test_004_callback,
                         plus=("Test #", 4))

    @rpc_callback
    def test_004_callback(self, data, plus, error=None):
        if error == None:
            self.test_end(False, "No error received.")
        elif plus != ("Test #", 4):
            self.test_end(False, "Plus object not received correctly.")
        elif data != None:
            self.test_end(False, "Some data received.")
        else:
            self.test_end(True, "Correctly received an error: %s." % error)


### TEST 005 ###

    def test_005(self):
        """Retrieve the file as a string.

        """
        logger.info("  I am retrieving the short binary file from FileCacher")
        self.fake_content = "Fake content.\n"
        with open(self.cache_path, "wb") as f:
            f.write(self.fake_content)
        self.FC.get_file_to_string(digest=self.digest,
                                   callback=TestFileCacher.test_005_callback,
                                   plus=("Test #", 5))

    @rpc_callback
    def test_005_callback(self, data, plus, error=None):
        if error != None:
            self.test_end(False, "Error received: %s." % error)
        elif plus != ("Test #", 5):
            self.test_end(False, "Plus object not received correctly.")
        elif data != self.fake_content:
            if data == self.content:
                self.test_end(False,
                              "Did not use the cache even if it could.")
            else:
                self.test_end(False, "Content differ.")
        else:
            self.test_end(True, "Data and plus object received correctly.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print sys.argv[0], "shard"
    else:
        TestFileCacher(int(sys.argv[1])).run()
