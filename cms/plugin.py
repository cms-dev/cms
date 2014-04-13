#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
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
from __future__ import print_function
from __future__ import unicode_literals

import imp
import logging
import os.path
import pkgutil

from .conf import config


logger = logging.getLogger(__name__)


def _try_import(plugin_name, dir_name):
    """Try to import a module called plugin_name from a directory
    called dir_name.

    plugin_name (string): name of the module (without extensions).
    dir_name (string): name of the directory where to look.

    return (module): the module if found, None if not found.

    """
    try:
        file_, file_name, description = imp.find_module(plugin_name,
                                                        [dir_name])
    except ImportError:
        return None

    try:
        module = imp.load_module(plugin_name,
                                 file_, file_name, description)
    except ImportError as error:
        logger.warning("Unable to use task type %s from plugin in "
                       "directory %s.\n%r", plugin_name, dir_name, error)
        return None
    else:
        return module
    finally:
        file_.close()


def plugin_lookup(plugin_name, plugin_dir, plugin_family):
    """Try to lookup a plugin in the standard positions.

    plugin_name (string): the name of the plugin: it is both the name
                          of the module and of a class inside that
                          module.
    plugin_dir (string): the place inside cms hierarchy where
                         plugin_name is usually found (e.g.:
                         cms.grading.tasktypes).
    plugin_family (string): the name of the plugin type, as used in
                            <system_plugins_directory>/<plugin_family>.

    return (type): the correct plugin class.

    raise (KeyError): if either the module or the class is not found.

    """
    module = None

    # Try first if the plugin is provided by CMS by default.
    try:
        module = __import__("%s.%s" % (plugin_dir, plugin_name),
                            fromlist=plugin_name)
    except ImportError:
        pass

    # If not found, try in all possible plugin directories.
    if module is None:
        module = _try_import(plugin_name,
                             os.path.join(config.data_dir,
                                          "plugins", plugin_family))

    if module is None:
        raise KeyError("Module %s not found." % plugin_name)

    if plugin_name not in module.__dict__:
        logger.warning("Unable to find class %s in the plugin.", plugin_name)
        raise KeyError("Class %s not found." % plugin_name)

    return module.__dict__[plugin_name]


def plugin_list(plugin_dir, plugin_family):
    """Return the list of plugins classes of the given family.

    plugin_dir (string): the place inside cms hierarchy where
                         plugin_name is usually found (e.g.:
                         cms.grading.tasktypes).
    plugin_family (string): the name of the plugin type, as used in
                            <system_plugins_directory>/<plugin_family>.

    return ([type]): the correct plugin class.

    raise (KeyError): if either the module or the class is not found.

    """
    cms_root_path = os.path.dirname(os.path.dirname(__file__))
    rets = pkgutil.iter_modules([
        os.path.join(cms_root_path, plugin_dir.replace(".", "/")),
        os.path.join(config.data_dir, "plugins", plugin_family),
    ])
    modules = [ret[0].find_module(ret[1]).load_module(ret[1]) for ret in rets]
    return [module.__dict__[module.__name__]
            for module in modules if module.__name__ in module.__dict__]
