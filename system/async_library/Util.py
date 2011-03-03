#!/usr/bin/python

"""Random utility and logging facilities.

"""

import logging
from collections import namedtuple
from random import choice

logging.basicConfig(level=logging.INFO,
                    format="%(created)-15s %(msecs)3d %(levelname)8s " +
                    "%(message)s")
log = logging.getLogger(__name__)
BACKLOG = 5
SIZE = 1024


Address = namedtuple("Address", "ip port")


class ServiceCoord(namedtuple("ServiceCoord", "name shard")):
    """A compact representation for the name and the shard number of a
    service (thus identifying it).

    """
    def __repr__(self):
        return "%s,%d" % (self.name, self.shard)


def random_string(length):
    """Returns a random string of ASCII letters of specified length.

    """
    letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    string = ""
    for i in range(length):
        string += choice(letters)
    return string
