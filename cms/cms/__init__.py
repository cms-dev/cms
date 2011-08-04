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

"""Load the configuration.

"""

import os
import simplejson

from cms.async import ServiceCoord, Address, Config

def load_config_file(cmsconf):
    """Populate the Config class with everything that sits inside the
    JSON file cmsconf (usually something/etc/cms.conf). The only
    pieces of data treated differently are the elements of
    core_services and other_services.

    cmsconf (string): the path of the JSON config file

    """
    # Load config file
    d = simplejson.load(open(cmsconf))

    # Put core and test services in Config
    for service in d["core_services"]:
        for shard_number, shard in enumerate(d["core_services"][service]):
            Config.core_services[ServiceCoord(service, shard_number)] = \
                Address(*shard)
    del d["core_services"]

    for service in d["other_services"]:
        for shard_number, shard in enumerate(d["other_services"][service]):
            Config.other_services[ServiceCoord(service, shard_number)] = \
                Address(*shard)
    del d["other_services"]

    # Put everything else. Note that we re-use the Config class, which
    # async thinks it is just for itself. This should cause no
    # problem, though, since Config's usage by async is very
    # read-only.
    for key in d:
        setattr(Config, key, d[key])


load_config_file(os.path.join("/", "usr", "local", "etc", "cms.conf"))

