#!/usr/bin/python

"""Testing suite for FileStorage

"""

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

        logger.info("  I am sending the short binary file to FileStorage")
        self.FS.put_file(binary_data=self.content,
                         description="Test #000",
                         callback=TestFileStorage.test_000_callback,
                         plus=("Test #", 0))

    @rpc_callback
    def test_000_callback(self, data, plus, error=None):
        if error != None:
            logger.info("  Error received: %s." % error)
        elif plus != ("Test #", 0):
            logger.info("  Plus object not received correctly.")
        else:
            logger.info("  Data sent without error and plus object received.")
            self.ok += 1
            self.digest = data
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
        if error != None:
            logger.info("  Error received: %s." % error)
        elif plus != ("Test #", 1):
            logger.info("  Plus object not received correctly.")
        elif data != self.content:
            logger.info("  Content differ.")
        else:
            logger.info("  Data and plus object received correctly.")
            self.ok += 1
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
        if error != None:
            logger.info("  Error received: %s." % error)
        elif plus != ("Test #", 2):
            logger.info("  Plus object not received correctly.")
        elif data != "Test #000":
            logger.info("  Description not correct.")
        else:
            logger.info("  Description and plus object received correctly.")
            self.ok += 1
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
        if error != None:
            logger.info("  Error received: %s." % error)
            self.test_end()
        elif plus != ("Test #", 3):
            logger.info("  Plus object not received correctly.")
            self.test_end()
        elif not data:
            logger.info("  File not deleted correctly.")
            self.test_end()
        else:
            logger.info("  File deleted correctly.")
            self.FS.get_file(digest=self.digest,
                             callback=TestFileStorage.test_003_callback_2,
                             plus=("Test #", 3))

    @rpc_callback
    def test_003_callback_2(self, data, plus, error=None):
        if error == None:
            logger.info("  No error received.")
        elif plus != ("Test #", 3):
            logger.info("  Plus object not received correctly.")
        elif data != None:
            logger.info("  Some data received.")
        else:
            logger.info("  Correctly received an error: %s." % error)
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
        if error == None:
            logger.info("  No error received.")
        elif plus != ("Test #", 4):
            logger.info("  Plus object not received correctly.")
        elif data != None:
            logger.info("  Some data received.")
        else:
            logger.info("  Correctly received an error: %s." % error)
            self.ok += 1
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
        if error == None:
            logger.info("  No error received.")
        elif plus != ("Test #", 5):
            logger.info("  Plus object not received correctly.")
        elif data != None:
            logger.info("  Some data received.")
        else:
            logger.info("  Correctly received an error: %s." % error)
            self.ok += 1
        self.test_end()


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print sys.argv[0], "shard"
    else:
        TestFileStorage(int(sys.argv[1])).run()
