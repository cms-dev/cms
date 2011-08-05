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

"""Simple service that ask for echo from all ServiceB, and request a
file from ServiceB,0.

"""

import time

from cms.async.AsyncLibrary import Service, rpc_callback, logger
from cms.async import ServiceCoord


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

        for i in xrange(10):
            self.ServiceB[1].long_rpc_method(string="%d - %s" %
                                             (i, str(time.time())),
                                             callback=ServiceA.echo_callback,
                                             plus=i)
        self.add_timeout(self.ask_for_echo, None, 4,
                         immediately=True)
        self.t = 5

    def ask_for_echo(self):
        """Ask all ServiceB for a echo.

        """
        self.t -= 1
        if self.t <= 0: return
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
            logger.info("Not asking ServiceB's aaa because not connected!")
            return True
        logger.info("Asking ServiceB's aaa.")
        self.ServiceB[0].binary_cat(filename="./aaa",
                                    callback=ServiceA.file_callback,
                                    plus=time.time())
        return False

    @rpc_callback
    def file_callback(self, data, plus, error=None):
        """Callback for ask_for_file. It writes the file to bbb.

        """
        logger.debug("ServiceA.file_callback")
        if error != None:
            logger.error(error)
            return
        seconds = time.time() - plus
        megabytes = len(data) / 1024.0 / 1024.0
        logger.info(("ServiceB's gave us aaa: %5.3lf MB in %5.3lf seconds " + \
                     "(%5.3lf MB/s)")
                    % (megabytes, seconds, megabytes / seconds))
        with open("bbb", "wb") as bbb:
            bbb.write(data)

        # Now giving back the file
        logger.info("Sending back bbb to ServiceB.")
        with open("bbb", "rb") as bbb:
            self.ServiceB[0].binary_write(filename="ccc",
                                          binary_data=bbb.read())


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print sys.argv[0], "shard"
    else:
        ServiceA(int(sys.argv[1])).run()
