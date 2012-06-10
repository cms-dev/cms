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

"""Useful classes and methods for async.

"""

from collections import namedtuple
from functools import wraps
from types import GeneratorType
import socket

Address = namedtuple("Address", "ip port")


class ServiceCoord(namedtuple("ServiceCoord", "name shard")):
    """A compact representation for the name and the shard number of a
    service (thus identifying it).

    """
    def __repr__(self):
        return "%s,%d" % (self.name, self.shard)


class Config:
    """This class will contain the configuration for the
    services. This needs to be populated at the initilization stage.

    The *_services variables are dictionaries indexed by ServiceCoord
    with values of type Address.

    Core services are the ones that are supposed to run whenever the
    system is up.

    Other services are not supposed to run when the system is up, or
    anyway not constantly.

    """
    core_services = {}
    other_services = {}


config = Config()


def get_service_address(key):
    """Give the Address of a ServiceCoord.

    key (ServiceCoord): the service needed.
    returns (Address): listening address of key.

    """
    if key in config.core_services:
        return config.core_services[key]
    elif key in config.other_services:
        return config.other_services[key]
    else:
        raise KeyError


def get_shard_from_addresses(service, addrs):
    """Returns the first shard of a service that listens in one of the
    specified addresses.

    service (string): the name of the service.
    addrs (list): a list of strings, the addresses that can match the
                  shard.
    returns (int): the found shard, or -1 in case it doesn't exist.

    """
    i = 0
    while True:
        try:
            host, port = get_service_address(ServiceCoord(service, i))
            try:
                if socket.gethostbyname(host) in addrs:
                    return i
            except socket.gaierror:
                # If the address can't be resolved, we simply skip it
                pass
        except KeyError:
            return -1
        i += 1


def get_service_shards(service):
    """Returns the number of shards that a service has.

    service (string): the name of the service.
    returns (int): the number of shards defined in the configuration.

    """
    i = 0
    while True:
        try:
            get_service_address(ServiceCoord(service, i))
        except KeyError:
            return i
        i += 1


def make_async(func):
    """Decorator to allow the use of yields in a method instead of
    splitting the computation in several methods/callbacks. RPC calls
    in the method are done in the same way as a normal call, but one
    must omit the parameters 'callback' and 'plus' (because the former
    makes no sense and the second is useless), and add the parameter
    timeout. Note that giving a timeout is essential because otherwise
    we don't know that the call is yielded.

    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        generator = func(*args, **kwargs)
        if not isinstance(generator, GeneratorType):
            # The method we are decorating is not a generator (i.e.,
            # containes no yields), hence we return immediately its
            # value.
            return generator
        try:
            result = generator.next()
            while True:
                new_result = None
                if result == False:
                    new_result = generator.throw(
                        Exception("Service not connected"))
                elif result["completed"] == False:
                    new_result = generator.throw(
                        Exception("RPC call timeout"))
                elif result["error"] is not None:
                    new_result = generator.throw(
                        Exception(result["error"]))
                else:
                    new_result = generator.send(result["data"])
                result = new_result
        except StopIteration:
            return result['data']
        except TypeError:
            raise TypeError("Did you pass the 'timeout' argument to the RPC?")

    return wrapper


def async_response(data):
    """Return a dictionary that encodes a standard not-error response
    in a make_async context.

    data (object): the response.
    return (dict): the response ready to be yielded.

    """
    return {"data": data,
            "error": None,
            "completed": True}


def async_error(message):
    """Return a dictionary that encodes a standard error response in a
    make_async context.

    message (string): the error message.
    return (dict): am error response ready to be yielded.

    """
    return {"data": None,
            "error": message,
            "completed": True}
