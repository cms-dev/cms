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

"""Testing suite for FileStorage

"""

import random

from cms.async import ServiceCoord
from cms.async.AsyncLibrary import rpc_callback, logger
from cms.async.TestService import TestService


class TestFileStorage(TestService):
    """Service that performs automatically some tests for the
    FileStorage service.

    """

    def __init__(self, shard):
        logger.initialize(ServiceCoord("TestFileStorage", shard))
        logger.debug("TestFileStorage.__init__")
        TestService.__init__(self, shard)

        self.content = None
        self.digest = None

        self.FS = self.connect_to(
            ServiceCoord("FileStorage", 0))
        if not self.FS.connected:
            logger.error("Please run the FileStorage service.")
            self.exit()

### TEST 000 ###

    def test_000(self):
        """Send a ~100B random binary file to FileStorage.

        """
        self.content = ""
        for i in xrange(100):
            self.content += chr(random.randint(0, 255))

        logger.info("  I am sending the ~100B binary file to FileStorage")
        self.FS.put_file(binary_data=self.content,
                         description="Test #000",
                         callback=TestFileStorage.test_000_callback,
                         plus=("Test #", 0))

    @rpc_callback
    def test_000_callback(self, data, plus, error=None):
        """Called with the digest of the ~100B file.

        """
        if error != None:
            self.test_end(False, "Error received: %s." % error)
        elif plus != ("Test #", 0):
            self.test_end(False, "Plus object not received correctly.")
        else:
            self.digest = data
            self.test_end(True, "Data sent without error " +
                          "and plus object received.")

### TEST 001 ###

    def test_001(self):
        """Retrieve the file.

        """
        logger.info("  I am retrieving the ~100B binary file from FileStorage")
        self.FS.get_file(digest=self.digest,
                         callback=TestFileStorage.test_001_callback,
                         plus=("Test #", 1))

    @rpc_callback
    def test_001_callback(self, data, plus, error=None):
        """Called with the content of the file.

        """
        if error != None:
            self.test_end(False, "Error received: %s." % error)
        elif plus != ("Test #", 1):
            self.test_end(False, "Plus object not received correctly.")
        elif data != self.content:
            self.test_end(False, "Content differ.")
        else:
            self.test_end(True, "Data and plus object " +
                          "received correctly.")

### TEST 002 ###

    def test_002(self):
        """Retrieve the description.

        """
        logger.info("  I am retrieving the description from FileStorage")
        self.FS.describe(digest=self.digest,
                         callback=TestFileStorage.test_002_callback,
                         plus=("Test #", 2))

    @rpc_callback
    def test_002_callback(self, data, plus, error=None):
        """Called with the description of the file.

        """
        if error != None:
            self.test_end(False, "Error received: %s." % error)
        elif plus != ("Test #", 2):
            self.test_end(False, "Plus object not received correctly.")
        elif data != "Test #000":
            self.test_end(False, "Description not correct.")
        else:
            self.test_end(True, "Description and plus object " +
                          "received correctly.")

### TEST 003 ###

    def test_003(self):
        """Delete the file and tries to get it again.

        """
        logger.info("  I am deleting the file from FileStorage")
        self.FS.delete(digest=self.digest,
                       callback=TestFileStorage.test_003_callback,
                       plus=("Test #", 3))

    @rpc_callback
    def test_003_callback(self, data, plus, error=None):
        """Should be called with data == True confirming the deletion.

        """
        if error != None:
            self.test_end(False, "Error received: %s." % error)
        elif plus != ("Test #", 3):
            self.test_end(False, "Plus object not received correctly.")
        elif not data:
            self.test_end(False, "File not deleted correctly.")
        else:
            logger.info("  File deleted correctly.")
            self.FS.get_file(digest=self.digest,
                             callback=TestFileStorage.test_003_callback_2,
                             plus=("Test #", 3))

    @rpc_callback
    def test_003_callback_2(self, data, plus, error=None):
        """Should be called with an error.

        """
        if error == None:
            self.test_end(False, "No error received.")
        elif plus != ("Test #", 3):
            self.test_end(False, "Plus object not received correctly.")
        elif data != None:
            self.test_end(False, "Some data received.")
        else:
            self.test_end(True,
                          "Correctly received an error: %s." % error)

### TEST 004 ###

    def test_004(self):
        """Delete the unexisting file.

        """
        logger.info("  I am deleting the unexisting file from FileStorage")
        self.FS.delete(digest=self.digest,
                       callback=TestFileStorage.test_004_callback,
                       plus=("Test #", 4))

    @rpc_callback
    def test_004_callback(self, data, plus, error=None):
        """Should be called with an error.

        """
        if error == None:
            self.test_end(False, "No error received.")
        elif plus != ("Test #", 4):
            self.test_end(False, "Plus object not received correctly.")
        elif data != None:
            self.test_end(False, "Some data received.")
        else:
            self.test_end(True,
                          "Correctly received an error: %s." % error)

### TEST 005 ###

    def test_005(self):
        """Getting the description of the unexisting file.

        """
        logger.info("  Describing the unexisting file from FileStorage")
        self.FS.delete(digest=self.digest,
                       callback=TestFileStorage.test_005_callback,
                       plus=("Test #", 5))

    @rpc_callback
    def test_005_callback(self, data, plus, error=None):
        """Should be called with error != None.

        """
        if error == None:
            self.test_end(False, "No error received.")
        elif plus != ("Test #", 5):
            self.test_end(False, "Plus object not received correctly.")
        elif data != None:
            self.test_end(False, "Some data received.")
        else:
            self.test_end(True,
                          "Correctly received an error: %s." % error)

### TEST 006 ###

    def test_006(self):
        """Send a ~1MB random binary file to FileStorage.

        """
        # Just use some random bytes, or it slows down for nothing
        self.content = ""
        random_begin = ""
        random_end = ""
        for i in xrange(100):
            random_begin += chr(random.randint(0, 255))
            random_end += chr(random.randint(0, 255))
        self.content = random_begin + ("." * 1000000) + random_end

        logger.info("  I am sending the ~1MB binary file to FileStorage")
        self.FS.put_file(binary_data=self.content,
                         description="Test #006",
                         callback=TestFileStorage.test_006_callback,
                         plus=("Test #", 6))

    @rpc_callback
    def test_006_callback(self, data, plus, error=None):
        """Called with the digest of the ~1MB file.

        """
        if error != None:
            self.test_end(False, "Error received: %s." % error)
        elif plus != ("Test #", 6):
            self.test_end(False, "Plus object not received correctly.")
        else:
            self.digest = data
            self.test_end(True, "Data sent without error " +
                          "and plus object received.")

### TEST 007 ###

    def test_007(self):
        """Retrieve the file.

        """
        logger.info("  I am retrieving the ~1MB binary file from FileStorage")
        self.FS.get_file(digest=self.digest,
                         callback=TestFileStorage.test_007_callback,
                         plus=("Test #", 7))

    @rpc_callback
    def test_007_callback(self, data, plus, error=None):
        """Called with the actual file.

        """
        if error != None:
            self.test_end(False, "Error received: %s." % error)
        elif plus != ("Test #", 7):
            self.test_end(False, "Plus object not received correctly.")
        elif data != self.content:
            self.test_end(False, "Content differ.")
        else:
            self.test_end(True, "Data and plus object " +
                          "received correctly.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print sys.argv[0], "shard"
    else:
        TestFileStorage(int(sys.argv[1])).run()
