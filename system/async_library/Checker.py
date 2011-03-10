#!/usr/bin/python

"""Service that checks the answering times of all services.

"""

import time

from AsyncLibrary import Service, rpc_callback
from Util import ServiceCoord, log


class Checker(Service):
    """Service that checks the answering times of all services.

    """

    def __init__(self):
        log.debug("Checker.__init__")
        Service.__init__(self)
        self.connect_to(ServiceCoord("Checker", 0))
        self.connect_to(ServiceCoord("ServiceA", 0))
        self.connect_to(ServiceCoord("ServiceB", 0))
        self.connect_to(ServiceCoord("ServiceB", 1))
        self.connect_to(ServiceCoord("WebServer", 0))
        self.add_timeout(self.check, None, 10, immediately=True)

        self.waiting_for = {}

    def check(self):
        """For all services, send an echo request and logs the time of
        the request.

        """
        log.debug("Checker.check")
        now = time.time()
        for coordinates, service in self.remote_services.iteritems():
            if coordinates in self.waiting_for:
                log.info("Service %s timeout, retrying."
                         % str(coordinates))
                del self.waiting_for[coordinates]

            if service.connected:
                self.waiting_for[coordinates] = now
                service.echo(string="%s %5.3lf"
                             % (str(coordinates), now),
                             callback=Checker.echo_callback)
            else:
                log.info("Service %s not connected."
                         % str(coordinates))
        return True

    @rpc_callback
    def echo_callback(self, data, error=None):
        """Callback for check.

        """
        log.debug("Checker.echo_callback")
        if error != None:
            return
        current = time.time()
        try:
            service, time_ = data.split()
            time_ = float(time_)
            name, shard = service.split(",")
            shard = int(shard)
            service = ServiceCoord(name, shard)
            if service not in self.waiting_for or current - time_ > 10:
                log.info("Got late reply (%5.3lf s) from %s"
                         % (current - time_, str(service)))
            else:
                if time_ - self.waiting_for[service] > 0.001:
                    log.error("Someone cheated on the timestamp?!")
                log.info("Got reply (%5.3lf s) from %s"
                         % (current - time_, str(service)))
                del self.waiting_for[service]
        except KeyError:
            log.error("Echo answer mis-shapen.")


if __name__ == "__main__":
    Checker().run()
