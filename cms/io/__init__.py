#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2013 Stefano Maggiolo <s.maggiolo@gmail.com>
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

import gevent.socket

Address = namedtuple("Address", "ip port")


class ServiceCoord(namedtuple("ServiceCoord", "name shard")):
    """A compact representation for the name and the shard number of a
    service (thus identifying it).

    """
    def __repr__(self):
        return "%s,%d" % (self.name, self.shard)


class Config(object):
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
        raise KeyError("Service not found.")


def get_shard_from_addresses(service, addrs):
    """Returns the first shard of a service that listens in one of the
    specified addresses.

    service (string): the name of the service.
    addrs ([(int, str)]): a list like the one returned by
                          find_local_addresses().

    returns (int): the found shard, or -1 in case it doesn't exist.

    """
    i = 0
    ipv4_addrs = set()
    ipv6_addrs = set()
    for proto, addr in addrs:
        if proto == gevent.socket.AF_INET:
            ipv4_addrs.add(addr)
        elif proto == gevent.socket.AF_INET6:
            ipv6_addrs.add(addr)
    while True:
        try:
            host, port = get_service_address(ServiceCoord(service, i))
            res_ipv4_addrs = set()
            res_ipv6_addrs = set()
            # For magic numbers, see getaddrinfo() documentation
            try:
                res_ipv4_addrs = set([x[4][0] for x in
                                      gevent.socket.getaddrinfo(
                                          host, port,
                                          family=gevent.socket.AF_INET,
                                          socktype=gevent.socket.SOCK_STREAM)])
            except (gevent.socket.gaierror, gevent.socket.error):
                res_ipv4_addrs = set()

            try:
                res_ipv6_addrs = set([x[4][0] for x in
                                      gevent.socket.getaddrinfo(
                                          host, port,
                                          family=gevent.socket.AF_INET6,
                                          socktype=gevent.socket.SOCK_STREAM)])
            except (gevent.socket.gaierror, gevent.socket.error):
                res_ipv6_addrs = set()

            if not ipv4_addrs.isdisjoint(res_ipv4_addrs) or \
                    not ipv6_addrs.isdisjoint(res_ipv6_addrs):
                return i
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
