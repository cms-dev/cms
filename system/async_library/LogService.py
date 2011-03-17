#!/usr/bin/python

"""Logger service.

"""

import os
import time

import codecs
import base64

from AsyncLibrary import Service, rpc_method, logger, ServiceCoord

class LogService(Service):
    """Logger service.

    """

    def __init__(self, shard):
        logger.initialize(ServiceCoord("LogService", shard))
        Service.__init__(self, shard)

        self._log_file = codecs.open(os.path.join("logs", "%d.log" %
                                                  time.time()),
                                     "w", "utf-8")


    @rpc_method
    def Log(self, msg):
        """Log a message.

        """
        print msg
        print >> self._log_file, msg
        return True


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print sys.argv[0], "shard"
    else:
        LogService(int(sys.argv[1])).run()
