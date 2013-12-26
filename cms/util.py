#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2013 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

import errno
import logging
import netifaces
import os
import sys
from argparse import ArgumentParser
from collections import namedtuple

import gevent.socket


logger = logging.getLogger(__name__)


def mkdir(path):
    """Make a directory without complaining for errors.

    path (string): the path of the directory to create
    returns (bool): True if the dir is ok, False if it is not

    """
    try:
        os.mkdir(path)
    except OSError as error:
        if error.errno != errno.EEXIST:
            return False
    return True


class Address(namedtuple("Address", "ip port")):
    def __repr__(self):
        return "%s:%d" % (self.ip, self.port)


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


async_config = Config()


def get_service_address(key):
    """Give the Address of a ServiceCoord.

    key (ServiceCoord): the service needed.
    returns (Address): listening address of key.

    """
    if key in async_config.core_services:
        return async_config.core_services[key]
    elif key in async_config.other_services:
        return async_config.other_services[key]
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


def default_argument_parser(description, cls, ask_contest=None):
    """Default argument parser for services - in two versions: needing
    a contest_id, or not.

    description (string): description of the service.
    cls (type): service's class.
    ask_contest (function): None if the service does not require a
                            contest, otherwise a function that returns
                            a contest_id (after asking the admins?)

    return (object): an instance of a service.

    """
    parser = ArgumentParser(description=description)
    parser.add_argument("shard", nargs="?", type=int, default=-1)

    # We need to allow using the switch "-c" also for services that do
    # not need the contest_id because RS needs to be able to restart
    # everything without knowing which is which.
    contest_id_help = "id of the contest to automatically load"
    if ask_contest is None:
        contest_id_help += " (ignored)"
    parser.add_argument("-c", "--contest-id", help=contest_id_help,
                        nargs="?", type=int)
    args = parser.parse_args()

    # If the shard is -1 (i.e., unspecified) we find it basing on the
    # local IP addresses
    if args.shard == -1:
        addrs = find_local_addresses()
        args.shard = get_shard_from_addresses(cls.__name__, addrs)
        if args.shard == -1:
            logger.critical("Couldn't autodetect shard number and "
                            "no shard specified for service %s, "
                            "quitting." % (cls.__name__))
            sys.exit(1)

    if ask_contest is not None:
        if args.contest_id is not None:
            # Test if there is a contest with the given contest id.
            from cms.db import is_contest_id
            if not is_contest_id(args.contest_id):
                print("There is no contest with the specified id. "
                      "Please try again.", file=sys.stderr)
                sys.exit(1)
            return cls(args.shard, args.contest_id)
        else:
            return cls(args.shard, ask_contest())
    else:
        return cls(args.shard)


def find_local_addresses():
    """Returns the list of IPv4 and IPv6 addresses configured on the
    local machine.

    returns ([(int, str)]): a list of tuples, each representing a
                            local address; the first element is the
                            protocol and the second one is the
                            address.

    """
    addrs = []
    # Based on http://stackoverflow.com/questions/166506/
    # /finding-local-ip-addresses-using-pythons-stdlib
    for iface_name in netifaces.interfaces():
        for proto in [netifaces.AF_INET, netifaces.AF_INET6]:
            addrs += [(proto, i['addr'])
                      for i in netifaces.ifaddresses(iface_name).
                      setdefault(proto, [])]
    return addrs
