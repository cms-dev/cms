#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
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

from cms.service.FileStorage import FileCacher
from cms.db.Utils import default_argument_parser
from cms.async.AsyncLibrary import Service, rpc_method, \
     rpc_binary_response, rpc_threaded, logger, async_lock
from cms.async import ServiceCoord


class ServiceB(Service):
    """Simple service that offer a file, overwrite the standard echo
    method, and offer a quite long version of the echo method.

    """

    def __init__(self, shard):
        logger.initialize(ServiceCoord("ServiceB", shard))
        logger.debug("ServiceB.__init__")
        Service.__init__(self, shard)
        self.FC = FileCacher(self)
        self.add_timeout(self.operate, True, 100000, immediately=True)

    def operate(self, put):
        """Operate.

        """
        start = time.time()
        s = "Tentative binary file \xff\xff\n"
        s = s * 100000
        digest = "d727e20eb5580ad553433f1cb805bac3380ba174"
        if put:
            try:
                digest = self.FC.put_file(binary_data=s,
                                          description="Tentative")
            except Exception as e:
                logger.error(repr(e))
                return
        logger.info("Time elapsed for put: %.3lf" % (time.time() - start))
        self.FC.delete_from_cache(digest)
        start = time.time()
        try:
            data = self.FC.get_file(digest=digest, string=True)
        except Exception as e:
            logger.error(repr(e))
            return
        if s == data:
            logger.info("File %s put and got ok." % digest)
        else:
            logger.error("Files not equal.")
        logger.info("Time elapsed for get: %.3lf" % (time.time() - start))

    @rpc_method
    def long_rpc_method(self, string):
        """Anoter example RPC method that takes a while.

        """
        with async_lock:
            logger.debug("ServiceB.long_rpc_method")
            logger.info("Start long method, par = %s" % string)
        time.sleep(3)
        with async_lock:
            logger.info("End long method, par = %s" % string)
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
    default_argument_parser("Example service B for CMS.", ServiceB).run()
