#!/usr/bin/python

"""Simple service that ask for echo from all ServiceB, and request a
file from ServiceB,0.

"""

import time
import base64

from AsyncLibrary import Service, rpc_callback, logger
from Utils import ServiceCoord


class ServiceA(Service):
    """Simple service that ask for echo from all ServiceB, and request
    a file from ServiceB,0.

    """

    def __init__(self, shard):
        logger.initialize(ServiceCoord("ServiceA", shard))
        logger.debug("ServiceA.__init__")
        Service.__init__(self, shard)
        self.ServiceB = []
        self.ServiceB.append(self.connect_to(
                ServiceCoord("ServiceB", 0)))
        self.ServiceB.append(self.connect_to(
                ServiceCoord("ServiceB", 1)))
        self.add_timeout(self.ask_for_echo, None, 10,
                         immediately=True)
        self.add_timeout(self.ask_for_file, None, 2,
                         immediately=True)

    def ask_for_echo(self):
        """Ask all ServiceB for a echo.

        """
        logger.debug("ServiceA.ask_for_echo")
        for i in xrange(0, 2):
            remote_service = self.ServiceB[i]
            if remote_service.connected:
                logger.info("Asking %s for echo..."
                            % str(remote_service.remote_service_coord))
                remote_service.echo(string=str(time.time()),
                                    callback=ServiceA.echo_callback,
                                    plus=i)
            else:
                logger.info("%s not connected, not asking!"
                            % str(remote_service.remote_service_coord))
        return True

    @rpc_callback
    def echo_callback(self, data, plus, error=None):
        """Callback for ask_for_echo.

        """
        logger.debug("ServiceA.echo_callback")
        if error != None:
            return
        logger.info("ServiceB,%d answered %s" % (plus, data))

    def ask_for_file(self):
        """Ask ServiceB,0 for file aaa.

        """
        logger.debug("ServiceA.ask_for_file")
        if not self.ServiceB[0].connected:
            logger.info("Not asking file because not connected!")
            return True
        self.ServiceB[0].binary_cat(filename="./aaa",
                                     callback=ServiceA.file_callback,
                                     plus=time.time())
        return False

    @rpc_callback
    def file_callback(self, data, plus, error=None):
        """Callback for ask_for_file. It writes the file to bbb.

        """
        if error != None:
            logger.error(error)
            return
        logger.debug("ServiceA.file_callback")
        seconds = time.time() - plus
        data = base64.decodestring(data)
        megabytes = len(data) / 1024.0 / 1024.0
        logger.info("%5.3lf MB in %5.3lf seconds (%5.3lf MB/s)"
                    % (megabytes, seconds, megabytes / seconds))
        bbb = open("bbb", "w")
        bbb.write(data)
        bbb.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print sys.argv[0], "shard"
    else:
        ServiceA(int(sys.argv[1])).run()
