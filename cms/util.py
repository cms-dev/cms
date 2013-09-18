#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2014 Stefano Maggiolo <s.maggiolo@gmail.com>
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
from __future__ import print_function
from __future__ import unicode_literals

import errno
import logging
import netifaces
import os
import sys
from argparse import ArgumentParser
from collections import namedtuple

import six

import gevent.socket


logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Exception for critical configuration errors."""
    pass


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


def utf8_decoder(value):
    """Decode given binary to text (if it isn't already) using UTF8.

    value (string): value to decode.

    return (unicode): decoded value.

    raise (TypeError): if value isn't a string.

    """
    if isinstance(value, six.text_type):
        return value
    elif isinstance(value, six.binary_type):
        return value.decode('utf-8')
    else:
        raise TypeError("Not a string.")


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


def get_safe_shard(service, provided_shard):
    """Return a safe shard number for the provided service, or raise.

    service (string): the name of the service trying to get its shard,
        for looking it up in the config.
    provided_shard (int|None): the shard number provided by the admin
        via command line, or None (the default value).

    return (int): the provided shard number if it makes sense,
        otherwise the shard number found matching the IP address with
        the configuration.

    raise (ValueError): if no safe shard can be returned.

    """
    if provided_shard is None:
        addrs = _find_local_addresses()
        computed_shard = _get_shard_from_addresses(service, addrs)
        if computed_shard is None:
            logger.critical("Couldn't autodetect shard number and "
                            "no shard specified for service %s, "
                            "quitting.", service)
            raise ValueError("No safe shard found for %s." % service)
        else:
            return computed_shard
    else:
        coord = ServiceCoord(service, provided_shard)
        if coord not in async_config.core_services:
            logger.critical("The provided shard number for service %s "
                            "cannot be found in the configuration, "
                            "quitting.", service)
            raise ValueError("No safe shard found for %s." % service)
        else:
            return provided_shard


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
    """Default argument parser for services.

    This has two versions, depending on whether the service needs a
    contest_id, or not.

    description (string): description of the service.
    cls (type): service's class.
    ask_contest (function|None): None if the service does not require
        a contest, otherwise a function that returns a contest_id
        (after asking the admins?)

    return (object): an instance of a service.

    """
    parser = ArgumentParser(description=description)
    parser.add_argument("shard", action="store", type=int, nargs="?")

    # We need to allow using the switch "-c" also for services that do
    # not need the contest_id because RS needs to be able to restart
    # everything without knowing which is which.
    contest_id_help = "id of the contest to automatically load"
    if ask_contest is None:
        contest_id_help += " (ignored)"
    parser.add_argument("-c", "--contest-id", action="store", type=int,
                        help=contest_id_help)
    args = parser.parse_args()

    try:
        args.shard = get_safe_shard(cls.__name__, args.shard)
    except ValueError:
        raise ConfigError("Couldn't autodetect shard number and "
                          "no shard specified for service %s, "
                          "quitting." % (cls.__name__))

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


def _find_local_addresses():
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


def _get_shard_from_addresses(service, addrs):
    """Returns the first shard of a service that listens at one of the
    specified addresses.

    service (string): the name of the service.
    addrs ([(int, str)]): a list like the one returned by
        find_local_addresses().

    returns (int|None): the found shard, or None in case it doesn't
        exist.

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
            return None
        i += 1
