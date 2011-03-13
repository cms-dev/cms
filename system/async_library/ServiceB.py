#!/usr/bin/python

"""Simple service that offer a file, overwrite the standard echo
method, and offer a quite long version of the echo method.

"""

import time
import base64

from AsyncLibrary import Service
from Utils import log


class ServiceB(Service):
    """Simple service that offer a file, overwrite the standard echo
    method, and offer a quite long version of the echo method.

    """

    def __init__(self, shard):
        log.debug("ServiceB.__init__")
        Service.__init__(self, shard)

    def long_rpc_method(self, string):
        """Anoter example RPC method that takes a while.

        """
        log.debug("ServiceB.long_rpc_method")
        log.info("Start long method")
        time.sleep(7)
        log.info("End long method")
        return string

    def echo(self, string):
        """Overwritten RPC method echo.

        """
        log.debug("ServiceB.echo")
        log.info("Echo received.")
        return string

    def binary_cat(self, filename):
        """RPC method that returns the base64 encoded content of a
        file.

        filename (string): the file to cat.
        """
        log.debug("ServiceB.binary_cat")
        log.info("Catting %s." % filename)
        data = base64.encodestring(open(filename).read())
        log.info("Ended catting.")
        return data

    def text_cat(self, filename):
        """RPC method that returns the content of a file.

        filename (string): the file to cat.
        """
        log.debug("ServiceB.text_cat")
        log.info("Catting %s." % filename)
        data = open(filename).read()
        log.info("Ended catting.")
        return data

    def sum_of_two(self, a, b):
        """RPC method that returns the sum of two integers.

        a, b (int): summands
        returns (int): the sum
        """
        log.debug("ServiceB.sum_of_two")
        return a + b


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print sys.argv[0], "shard"
    else:
        ServiceB(int(sys.argv[1])).run()
