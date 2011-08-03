#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2011 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2011 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2011 Matteo Boscariol <boscarim@hotmail.com>
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

"""Load the configuration of the services.

"""

import os
from collections import namedtuple


Address = namedtuple("Address", "ip port")


class ServiceCoord(namedtuple("ServiceCoord", "name shard")):
    """A compact representation for the name and the shard number of a
    service (thus identifying it).

    """
    def __repr__(self):
        return "%s,%d" % (self.name, self.shard)


class Config:
    """This class just contains the addresses configurations.

    """
    services = {
        ServiceCoord("LogService", 0): Address("localhost", 29000),
        ServiceCoord("ResourceService", 0): Address("localhost", 28000),
        ServiceCoord("FileStorage", 0): Address("localhost", 27000),
        ServiceCoord("Sofa", 0): Address("localhost", 26000),
        ServiceCoord("Checker", 0): Address("localhost", 22000),

        ServiceCoord("TestFileStorage", 0): Address("localhost", 27500),
        ServiceCoord("TestFileCacher", 0): Address("localhost", 27501),
        ServiceCoord("TestSofa", 0): Address("localhost", 26500),

#        ServiceCoord("ServiceA", 0): Address("localhost", 20000),
#        ServiceCoord("ServiceB", 0): Address("localhost", 21000),
#        ServiceCoord("ServiceB", 1): Address("localhost", 21001),
#        ServiceCoord("WebServiceA", 0): Address("localhost", 23000),
        }


def get_service_address(key):
    """Give the Address of a ServiceCoord.

    key (ServiceCoord): the service needed.
    returns (Address): listening address of key.

    """
    if key in Config.services:
        return Config.services[key]
    else:
        raise KeyError
