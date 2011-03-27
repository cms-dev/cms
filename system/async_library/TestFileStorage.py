#!/usr/bin/python

"""Testing suite for FileStorage

"""

import time
import random

from AsyncLibrary import rpc_callback, logger
from DecoratedServices import TestService
from Utils import ServiceCoord, random_string


class TestFileStorage(TestService):
    """Service that performs automatically some tests for the
    FileStorage service.

    """

    def __init__(self, shard):
        logger.initialize(ServiceCoord("TestFileStorage", shard))
        logger.debug("TestFileStorage.__init__")
        TestService.__init__(self, shard)
        self.FS = self.connect_to(
            ServiceCoord("FileStorage", 0))
        if not self.FS.connected:
            logger.error("Please run the FileStorage service.")
            self.exit()


### TEST 000 ###

    def test_000(self):
        """Send a short random binary file to FileStorage.

        """
        path = random_string(16)
        self.content = ""
        for i in xrange(100):
            self.content += chr(random.randint(0, 255))

        logger.info("  I am sending the short binary file %s to FileStorage")
        self.FS.put_file(binary_data=self.content,
                         description="Test #000",
                         callback=TestFileStorage.test_000_callback,
                         plus=("Test #", 0))

    @rpc_callback
    def test_000_callback(self, data, plus, error=None):
        if error == None and plus == ("Test #", 0):
            logger.info("  Data sent without error and plus object received.")
            self.ok += 1
            self.digest = data
        else:
            if error != None:
                logger.info("  Error received: %s." % error)
            if plus != ("Test #", 0):
                logger.info("  Plus object not received correctly.")
        self.test_end()


### TEST 001 ###

    def test_001(self):
        """Retrieve the file.

        """
        logger.info("  I am retrieving the short binary file from FileStorage")
        self.FS.get_file(digest=self.digest,
                         callback=TestFileStorage.test_001_callback,
                         plus=("Test #", 1))

    @rpc_callback
    def test_001_callback(self, data, plus, error=None):
        if error == None and plus == ("Test #", 1) and data == self.content:
            logger.info("  Data and plus object received correctly.")
            self.ok += 1
        else:
            if error != None:
                logger.info("  Error received: %s." % error)
            if plus != ("Test #", 1):
                logger.info("  Plus object not received correctly.")
            if data != self.content:
                logger.info("  Content differ.")
        self.test_end()


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
        if error == None and plus == ("Test #", 2) and data == "Test #000":
            logger.info("  Description and plus object received correctly.")
            self.ok += 1
        else:
            if error != None:
                logger.info("  Error received: %s." % error)
            if plus != ("Test #", 2):
                logger.info("  Plus object not received correctly.")
            if data != self.content:
                logger.info("  Description not correct.")
        self.test_end()


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
        if error == None and plus == ("Test #", 3) and data:
            logger.info("  File deleted correctly.")
            self.FS.get_file(digest=self.digest,
                             callback=TestFileStorage.test_003_callback_2,
                             plus=("Test #", 3))
        else:
            if error != None:
                logger.info("  Error received: %s." % error)
            if plus != ("Test #", 3):
                logger.info("  Plus object not received correctly.")
            if not data:
                logger.info("  File not deleted correctly.")
            self.test_end()

    @rpc_callback
    def test_003_callback_2(self, data, plus, error=None):
        if error != None and plus == ("Test #", 3) and data == None:
            logger.info("  Correctly received an error: %s." % error)
            self.ok += 1
        else:
            if error == None:
                logger.info("  No error received.")
            if plus != ("Test #", 3):
                logger.info("  Plus object not received correctly.")
            if data != None:
                logger.info("  Some data received.")
                print data
        self.test_end()


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
        if error != None and plus == ("Test #", 4) and data == None:
            logger.info("  Correctly received an error: %s." % error)
            self.ok += 1
        else:
            if error == None:
                logger.info("  No error received.")
            if plus != ("Test #", 4):
                logger.info("  Plus object not received correctly.")
            if data != None:
                logger.info("  Some data received.")
        self.test_end()


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
        if error != None and plus == ("Test #", 5) and data == None:
            logger.info("  Correctly received an error: %s." % error)
            self.ok += 1
        else:
            if error == None:
                logger.info("  No error received.")
            if plus != ("Test #", 5):
                logger.info("  Plus object not received correctly.")
            if data != None:
                logger.info("  Some data received.")
        self.test_end()


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print sys.argv[0], "shard"
    else:
        TestFileStorage(int(sys.argv[1])).run()
