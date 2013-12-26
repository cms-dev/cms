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

import json
import logging
import os
import sys

from cms.io import ServiceCoord, Address, config as async_config


logger = logging.getLogger(__name__)


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
