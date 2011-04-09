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
        logger.info("  I am retrieving the short binary file from FileStorage")
        self.FS.get_file(digest=self.digest,
                         callback=TestFileStorage.test_001_callback,
                         plus=("Test #", 1))

    @rpc_callback
    def test_001_callback(self, data, plus, error=None):
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
        if error == None:
            self.test_end(False, "No error received.")
        elif plus != ("Test #", 5):
            self.test_end(False, "Plus object not received correctly.")
        elif data != None:
            self.test_end(False, "Some data received.")
        else:
            self.test_end(True,
                          "Correctly received an error: %s." % error)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print sys.argv[0], "shard"
    else:
        TestFileStorage(int(sys.argv[1])).run()
