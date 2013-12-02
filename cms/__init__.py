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

"""Load the configuration.

"""

from __future__ import print_function

import imp
import json
import logging
import netifaces
import os
import pkgutil
import sys

from argparse import ArgumentParser

from cms.io import ServiceCoord, Address, config as async_config, \
    get_shard_from_addresses


logger = logging.getLogger(__name__)


# Shorthand codes for all supported languages.
LANG_C = "c"
LANG_CPP = "cpp"
LANG_PASCAL = "pas"
LANG_PYTHON = "py"
LANG_PHP = "php"

LANGUAGE_NAMES = {
    LANG_C: "C",
    LANG_CPP: "C++",
    LANG_PASCAL: "Pascal",
    LANG_PYTHON: "Python",
    LANG_PHP: "PHP",
}

LANGUAGES = [LANG_C, LANG_CPP, LANG_PASCAL, LANG_PYTHON, LANG_PHP]
DEFAULT_LANGUAGES = [LANG_C, LANG_CPP, LANG_PASCAL]

# A reference for extension-based automatic language detection.
# (It's more difficult with headers because ".h" is ambiguous.)
SOURCE_EXT_TO_LANGUAGE_MAP = {
    ".c": LANG_C,
    ".cpp": LANG_CPP,
    ".cxx": LANG_CPP,
    ".cc": LANG_CPP,
    ".C": LANG_CPP,
    ".c++": LANG_CPP,
    ".pas": LANG_PASCAL,
    ".py": LANG_PYTHON,
    ".php": LANG_PHP,
}

# Our preferred source file and header file extension for each language.
LANGUAGE_TO_SOURCE_EXT_MAP = {
    LANG_C: ".c",
    LANG_CPP: ".cpp",
    LANG_PASCAL: ".pas",
    LANG_PYTHON: ".py",
    LANG_PHP: ".php"
}
LANGUAGE_TO_HEADER_EXT_MAP = {
    LANG_C: ".h",
    LANG_CPP: ".h",
    LANG_PASCAL: "lib.pas",
    LANG_PYTHON: ".py",
    LANG_PHP: ".php"
}


## Configuration ##

class Config(object):
    """This class will contain the configuration for CMS. This needs
    to be populated at the initilization stage. This is loaded by
    default with some sane data. See cms.conf.sample in the examples
    for information on the meaning of the fields.

    """
    def __init__(self):
        """Default values for configuration, plus decide if this
        instance is running from the system path or from the source
        directory.

        """
        self.async = async_config

        # System-wide
        self.temp_dir = "/tmp"
        self.backdoor = False

        # Database.
        self.database = "postgresql+psycopg2://cmsuser@localhost/cms"
        self.database_debug = False
        self.twophase_commit = False

        # Worker.
        self.keep_sandbox = True
        self.use_cgroups = True
        self.sandbox_implementation = 'isolate'

        # WebServers.
        self.secret_key = "8e045a51e4b102ea803c06f92841a1fb",
        self.tornado_debug = False

        # ContestWebServer.
        self.contest_listen_address = [""]
        self.contest_listen_port = [8888]
        self.cookie_duration = 1800
        self.submit_local_copy = True
        self.submit_local_copy_path = "%s/submissions/"
        self.tests_local_copy = True
        self.tests_local_copy_path = "%s/tests/"
        self.ip_lock = True
        self.block_hidden_users = False
        self.is_proxy_used = False
        self.max_submission_length = 100000
        self.max_input_length = 5000000
        self.stl_path = "/usr/share/doc/stl-manual/html/"
        self.allow_questions = True
        # Prefix of 'iso-codes'[1] installation. It can be found out
        # using `pkg-config --variable=prefix iso-codes`, but it's
        # almost universally the same (i.e. '/usr') so it's hardly
        # necessary to change it.
        # [1] http://pkg-isocodes.alioth.debian.org/
        self.iso_codes_prefix = "/usr"
        # Prefix of 'shared-mime-info'[2] installation. It can be found
        # out using `pkg-config --variable=prefix shared-mime-info`, but
        # it's almost universally the same (i.e. '/usr') so it's hardly
        # necessary to change it.
        # [2] http://freedesktop.org/wiki/Software/shared-mime-info
        self.shared_mime_info_prefix = "/usr"

        # AdminWebServer.
        self.admin_listen_address = ""
        self.admin_listen_port = 8889

        # ProxyService.
        self.rankings = ["http://usern4me:passw0rd@localhost:8890/"]
        self.https_certfile = None

        # Installed or from source?
        self.installed = sys.argv[0].startswith("/usr/") and \
            sys.argv[0] != '/usr/bin/ipython' and \
            sys.argv[0] != '/usr/bin/python2' and \
            sys.argv[0] != '/usr/bin/python'

        if self.installed:
            self.log_dir = os.path.join("/", "var", "local", "log", "cms")
            self.cache_dir = os.path.join("/", "var", "local", "cache", "cms")
            self.data_dir = os.path.join("/", "var", "local", "lib", "cms")
            self.run_dir = os.path.join("/", "var", "local", "run", "cms")
            paths = [os.path.join("/", "usr", "local", "etc", "cms.conf"),
                     os.path.join("/", "etc", "cms.conf")]
        else:
            self.log_dir = "log"
            self.cache_dir = "cache"
            self.data_dir = "lib"
            self.run_dir = "run"
            paths = [os.path.join(".", "examples", "cms.conf")]
            if '__file__' in globals():
                paths += [os.path.abspath(os.path.join(
                          os.path.dirname(__file__),
                          '..', 'examples', 'cms.conf'))]
            paths += [os.path.join("/", "usr", "local", "etc", "cms.conf"),
                      os.path.join("/", "etc", "cms.conf")]

        # Allow user to override config file path using environment
        # variable 'CMS_CONFIG'.
        CMS_CONFIG_ENV_VAR = "CMS_CONFIG"
        if CMS_CONFIG_ENV_VAR in os.environ:
            paths = [os.environ[CMS_CONFIG_ENV_VAR]] + paths

        # Attempt to load a config file.
        self._load(paths)

    def _load(self, paths):
        """Try to load the config files one at a time, until one loads
        correctly.

        """
        for conf_file in paths:
            try:
                self._load_unique(conf_file)
            except IOError:
                pass
            except ValueError as error:
                print("Unable to load JSON configuration file %s "
                      "because of a JSON decoding error.\n%r" % (conf_file,
                                                                 error))
            else:
                print("Using configuration file %s." % conf_file)
                return
        else:
            print("Warning: no configuration file found "
                  "in following locations:")
            for path in paths:
                print("    %s" % path)
            print("Using default values.")

    def _load_unique(self, path):
        """Populate the Config class with everything that sits inside
        the JSON file path (usually something like /etc/cms.conf). The
        only pieces of data treated differently are the elements of
        core_services and other_services that are sent to async
        config.

        Services whose name begins with an underscore are ignored, so
        they can be commented out in the configuration file.

        path (string): the path of the JSON config file.

        """
        # Load config file
        dic = json.load(open(path))

        # Put core and test services in async_config, ignoring those
        # whose name begins with "_"
        for service in dic["core_services"]:
            if service.startswith("_"):
                continue
            for shard_number, shard in \
                    enumerate(dic["core_services"][service]):
                coord = ServiceCoord(service, shard_number)
                self.async.core_services[coord] = Address(*shard)
        del dic["core_services"]

        for service in dic["other_services"]:
            if service.startswith("_"):
                continue
            for shard_number, shard in \
                    enumerate(dic["other_services"][service]):
                coord = ServiceCoord(service, shard_number)
                self.async.other_services[coord] = Address(*shard)
        del dic["other_services"]

        # Put everything else.
        for key in dic:
            setattr(self, key, dic[key])


config = Config()


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


# As this package initialization code is run by all code that imports
# something in cms.* it's the best place to setup the logging handlers.
# By importing the log module we install a handler on stdout. Other
# handlers will be added by services by calling initialize_logging.
# This operation cannot be done earlier, as it requires config and
# mkdir, which we just defined.
import cms.log


## Plugin helpers. ##

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
                       "directory %s.\n%r" % (plugin_name, dir_name, error))
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
        logger.warning("Unable to find class %s in the plugin." % plugin_name)
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
    cms_root_path = os.path.dirname(__path__[0])
    rets = pkgutil.iter_modules([
        os.path.join(cms_root_path, plugin_dir.replace(".", "/")),
        os.path.join(config.data_dir, "plugins", plugin_family),
    ])
    modules = [ret[0].find_module(ret[1]).load_module(ret[1]) for ret in rets]
    return [module.__dict__[module.__name__]
            for module in modules if module.__name__ in module.__dict__]


## Other utilities. ##

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
