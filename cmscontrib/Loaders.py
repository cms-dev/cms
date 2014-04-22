#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
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

"""List of loaders known by CMS, with some support functions.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from cmscontrib.YamlLoader import YamlLoader

LOADERS = dict((loader_class.short_name, loader_class)
               for loader_class in [YamlLoader])


def choose_loader(arg, path, error_callback):
    """Decide which loader to use.

    The choice depends upon the specified argument and possibly
    performing an autodetection.

    The autodetection is done by calling detect() on all the known
    loaders and returning the only one that returns True. If no one or
    more than one return True, then the autodetection is considered
    failed and None is returned.

    arg (string): the argument, possibly None, passed to the program
                  as loader specification.
    path (string): the path passed to the program from which to
                   perform the loading.
    error_callback (method): a method to call to report errors.

    return (type): the chosen loader class.

    """
    if arg is not None:
        try:
            return LOADERS[arg]
        except KeyError:
            error_callback("Specified loader doesn't exist")
    else:
        res = None
        for loader in LOADERS.itervalues():
            if loader.detect(path):
                if res is None:
                    res = loader
                else:
                    error_callback(
                        "Couldn't autodetect the loader, "
                        "please specify it: more than one "
                        "loader accepted the detection")
        if res is None:
            error_callback("Couldn't autodetect the loader, "
                           "please specify it: no "
                           "loader accepted the detection")
        return res


def build_epilog():
    """Build the ArgumentParser epilog.

    Basically, list the known loaders' short names.

    """
    epilog = "The following loaders are supported:\n"
    for short_name, loader_class in sorted(LOADERS.items()):
        epilog += " * %s (%s)\n" % (short_name, loader_class.description)
    return epilog
