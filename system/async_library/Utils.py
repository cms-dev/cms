#!/usr/bin/python

"""Random utility and logging facilities.

"""

import os
import sys

import simplejson
from collections import namedtuple
from random import choice


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


def mkdir(path):
    """Make a directory without complaining for errors.

    path (string): the path of the directory to create
    returns (bool): True if the dir is ok, False if it is not

    """
    try:
        os.mkdir(path)
        return True
    except OSError:
        if os.path.isdir(path):
            return True
    return False


def encode_length(length):
    """Encode an integer as a 4 bytes string

    length (int): the integer to encode
    return (string): a 4 bytes representation of length

    """
    try:
        s = ""
        tmp = length / (1 << 24)
        s += chr(tmp)
        length -= tmp * (1 << 24)
        tmp = length / (1 << 16)
        s += chr(tmp)
        length -= tmp * (1 << 16)
        tmp = length / (1 << 8)
        s += chr(tmp)
        length -= tmp * (1 << 8)
        s += chr(length)
        return s
    except Exception as e:
        print >> sys.stderr, "Can't encode length: %d %s" % (length, repr(e))
        raise ValueError


def decode_length(string):
    """Decode an integer from a 4 bytes string

    string (string): a 4 bytes representation of an integer
    return (int): the corresponding integer

    """
    try:
        return ord(string[0]) * (2 << 24) + \
               ord(string[1]) * (2 << 16) + \
               ord(string[2]) * (2 << 8) + \
               ord(string[3])
    except:
        print >> sys.stderr, "Can't decode length"
        raise ValueError


def encode_json(obj):
    """Encode a dictionary as a JSON string; on failure, returns None.

    obj (object): the object to encode
    return (string): an encoded string

    """
    try:
        return simplejson.dumps(obj)
    except:
        print >> sys.stderr, "Can't encode JSON: %s" % repr(obj)
        raise ValueError


def decode_json(string):
    """Decode a JSON string to a dictionary; on failure, raises an
    exception.

    string (string): the Unicode string to decode
    return (object): the decoded object

    """
    try:
        string = string.decode("utf8")
        return simplejson.loads(string)
    except simplejson.JSONDecodeError:
        print >> sys.stderr, "Can't decode JSON: %s" % string
        raise ValueError


def encode_binary(string):
    """Encode a string for binary transmission - escape character is
    '\\' and we escape '\r' as '\\r', so we can use again '\r\n' as
    terminator string.

    string (string): the binary string to encode
    returns (string): the escaped string

    """
    try:
        return string.replace('\\', '\\\\').replace('\r', '\\r')
    except:
        print >> sys.stderr, "Can't encode binary."
        raise ValueError


def decode_binary(string):
    """Decode an escaped string to a usual string.

    string (string): the escaped string to decode
    return (object): the decoded string
    """
    try:
        return string.replace('\\r', '\r').replace('\\\\', '\\')
    except:
        print >> sys.stderr, "Can't decode binary."
        raise ValueError


