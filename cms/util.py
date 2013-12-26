#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
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

import logging
import netifaces
import os
import sys
from argparse import ArgumentParser

from cms.io import get_shard_from_addresses


logger = logging.getLogger(__name__)


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
