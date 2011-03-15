#!/usr/bin/python

"""Simple service that offer a file, overwrite the standard echo
method, and offer a quite long version of the echo method.

"""

import time
import base64

from AsyncLibrary import Service, rpc_method, logger
from Utils import ServiceCoord


class ServiceB(Service):
    """Simple service that offer a file, overwrite the standard echo
    method, and offer a quite long version of the echo method.

    """

    def __init__(self, shard):
        logger.initialize(ServiceCoord("ServiceB", shard))
        logger.debug("ServiceB.__init__")
        Service.__init__(self, shard)

    @rpc_method
    def long_rpc_method(self, string):
        """Anoter example RPC method that takes a while.

        """
        logger.debug("ServiceB.long_rpc_method")
        logger.info("Start long method")
        time.sleep(7)
        logger.info("End long method")
        return string

    @rpc_method
    def echo(self, string):
        """Overwritten RPC method echo.

        """
        logger.debug("ServiceB.echo")
        logger.info("Echo received.")
        return string

    @rpc_method
    def binary_cat(self, filename):
        """RPC method that returns the base64 encoded content of a
        file.

        filename (string): the file to cat.
        """
        logger.debug("ServiceB.binary_cat")
        logger.info("Catting %s." % filename)
        data = base64.encodestring(open(filename).read())
        logger.info("Ended catting.")
        return data

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
