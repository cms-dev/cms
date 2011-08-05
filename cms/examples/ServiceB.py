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

"""Simple service that offer a file, overwrite the standard echo
method, and offer a quite long version of the echo method.

"""

import time
import threading

from cms.async.AsyncLibrary import Service, rpc_method, \
     rpc_binary_response, rpc_threaded, logger
from cms.async import ServiceCoord


class ServiceB(Service):
    """Simple service that offer a file, overwrite the standard echo
    method, and offer a quite long version of the echo method.

    """

    def __init__(self, shard):
        logger.initialize(ServiceCoord("ServiceB", shard))
        logger.debug("ServiceB.__init__")
        Service.__init__(self, shard)

    @rpc_method
    @rpc_threaded
    def long_rpc_method(self, string):
        """Anoter example RPC method that takes a while.

        """
        logger.debug("ServiceB.long_rpc_method")
        logger.info("Start long method, par = %s" % string)
        time.sleep(3)
        logger.info("End long method")
        return string

    @rpc_method
    @rpc_binary_response
    @rpc_threaded
    def binary_cat(self, filename):
        """RPC method that returns the content of a file.

        filename (string): the file to cat.
        """
        logger.debug("ServiceB.binary_cat")
        logger.info("Catting %s." % filename)
        data = open(filename, "rb").read()
        logger.info("Ended catting.")
        return data

    @rpc_method
    def binary_write(self, filename, binary_data):
        """Write content in a file.

        filename (string): where to put the data
        binary_data (string): what to put

        """
        open(filename, "wb").write(binary_data)
        return True

    @rpc_method
    def text_cat(self, filename):
        """RPC method that returns the content of a file.

        filename (string): the file to cat.
        """
        logger.debug("ServiceB.text_cat")
        logger.info("Catting %s." % filename)
        data = open(filename).read()
        logger.info("Ended catting.")
        return data

    @rpc_method
    def sum_of_two(self, a, b):
        """RPC method that returns the sum of two integers.

        a, b (int): summands
        returns (int): the sum
        """
        logger.debug("ServiceB.sum_of_two")
        return a + b


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print sys.argv[0], "shard"
    else:
        ServiceB(int(sys.argv[1])).run()
