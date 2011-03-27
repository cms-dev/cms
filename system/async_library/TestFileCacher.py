#!/usr/bin/python

"""Testing suite for FileCacher

"""

import os
import random

from AsyncLibrary import rpc_callback, logger
from DecoratedServices import TestService
from Utils import ServiceCoord, random_string
from FileStorage import FileCacher


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
            logger.info("  Error received: %s." % error)
            self.test_end(False)
        elif plus != ("Test #", 0):
            logger.info("  Plus object not received correctly.")
            self.test_end(False)
        elif not os.path.exists(os.path.join("fs-cache", "objects", data)):
            logger.info("  File not stored in local cache.")
            self.test_end(False)
        elif open(os.path.join("fs-cache", "objects", data), "rb").read() != \
             self.content:
            logger.info("  Local cache's content differ from original file.")
            self.test_end(False)
        else:
            logger.info("  Data sent and cached without error " +
                        "and plus object received.")
            self.cache_path = os.path.join("fs-cache", "objects", data)
            self.digest = data
            self.test_end(True)


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
            logger.info("  Error received: %s." % error)
            self.test_end(False)
        elif plus != ("Test #", 1):
            logger.info("  Plus object not received correctly.")
            self.test_end(False)
        elif data != self.fake_content:
            if data == self.content:
                logger.info("  Did not use the cache even if it could.")
            else:
                logger.info("  Content differ.")
            self.test_end(False)
        else:
            logger.info("  Data and plus object received correctly.")
            self.test_end(True)


### TEST 002 ###

    def test_002(self):
        """Get file from FileCacher

        """
        logger.info("  I am retrieving the file from FileCacher after deleting the cache.")
        os.unlink(self.cache_path)
        self.FC.get_file(digest=self.digest,
                         callback=TestFileCacher.test_002_callback,
                         plus=("Test #", 2))

    @rpc_callback
    def test_002_callback(self, data, plus, error=None):
        if error != None:
            logger.info("  Error received: %s." % error)
            self.test_end(False)
        elif plus != ("Test #", 2):
            logger.info("  Plus object not received correctly.")
            self.test_end(False)
        elif data != self.content:
            logger.info("  Content differ.")
            self.test_end(False)
        elif not os.path.exists(self.cache_path):
            logger.info("  File not stored in local cache.")
            self.test_end(False)
        elif open(self.cache_path).read() != self.content:
            logger.info("  Local cache's content differ from original file.")
            self.test_end(False)
        else:
            logger.info("  Content and plus object received and cached correctly.")
            self.test_end(True)


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
            logger.info("  Error received: %s." % error)
            self.test_end(False)
        elif plus != ("Test #", 3):
            logger.info("  Plus object not received correctly.")
            self.test_end(False)
        elif not data:
            logger.info("  File not deleted correctly.")
            self.test_end(False)
        else:
            logger.info("  File deleted correctly.")
            logger.info("  I am getting the file from FileCacher.")
            self.FC.get_file(digest=self.digest,
                             callback=TestFileCacher.test_003_callback_2,
                             plus=("Test #", 3))

    @rpc_callback
    def test_003_callback_2(self, data, plus, error=None):
        if error == None:
            logger.info("  No error received.")
            self.test_end(False)
        elif plus != ("Test #", 3):
            logger.info("  Plus object not received correctly.")
            self.test_end(False)
        elif data != None:
            logger.info("  Some data received.")
            self.test_end(False)
        else:
            logger.info("  Correctly received an error: %s." % error)
            self.test_end(True)


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
            logger.info("  No error received.")
            self.test_end(False)
        elif plus != ("Test #", 4):
            logger.info("  Plus object not received correctly.")
            self.test_end(False)
        elif data != None:
            logger.info("  Some data received.")
            self.test_end(False)
        else:
            logger.info("  Correctly received an error: %s." % error)
            self.test_end(True)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print sys.argv[0], "shard"
    else:
        TestFileCacher(int(sys.argv[1])).run()
