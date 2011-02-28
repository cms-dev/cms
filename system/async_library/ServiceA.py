#!/usr/bin/python

"""Simple service that ask for echo from all ServiceB, and request a
file from ServiceB,0.

"""

import time
import base64

from AsyncLibrary import Service, rpc_callback
from Util import ServiceCoord, log


class ServiceA(Service):
    """Simple service that ask for echo from all ServiceB, and request
    a file from ServiceB,0.

    """

    def __init__(self):
        log.debug("ServiceA.__init__")
        Service.__init__(self)
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
        log.debug("ServiceA.ask_for_echo")
        for i in xrange(0, 2):
            remote_service = self.ServiceB[i]
            if remote_service.connected:
                log.info("Asking %s for echo..."
                         % str(remote_service.remote_service_coord))
                remote_service.echo(string=str(time.time()),
                                    callback=ServiceA.echo_callback,
                                    plus=i)
            else:
                log.info("%s not connected, not asking!"
                         % str(remote_service.remote_service_coord))
        return True

    @rpc_callback
    def echo_callback(self, data, plus, error=None):
        """Callback for ask_for_echo.

        """
        log.debug("ServiceA.echo_callback")
        if error != None:
            return
        log.info("ServiceB,%d answered %s" % (plus, data))

    def ask_for_file(self):
        """Ask ServiceB,0 for file aaa.

        """
        log.debug("ServiceA.ask_for_file")
        if not self.ServiceB[0].connected:
            log.info("Not asking file because not connected!")
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
            log.error(error)
            return
        log.debug("ServiceA.file_callback")
        seconds = time.time() - plus
        data = base64.decodestring(data)
        megabytes = len(data) / 1024.0 / 1024.0
        log.info("%5.3lf MB in %5.3lf seconds (%5.3lf MB/s)"
                 % (megabytes, seconds, megabytes / seconds))
        bbb = open("bbb", "w")
        bbb.write(data)
        bbb.close()


if __name__ == "__main__":
    ServiceA().run()
