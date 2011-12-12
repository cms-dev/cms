#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2011 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

import json
import os


class Config(object):
    """An object holding the current configuration.

    """
    def __init__(self):
        """Fill this object with the default values for each key.

        """
        # connection
        self.host = 'localhost'
        self.port = 8890

        # authentication
        self.realm_name = 'Scoreboard'
        self.username = 'usern4me'
        self.password = 'passw0rd'

        # file system
        self.lib_dir = os.path.join("/", "var", "local", "lib", "cms", "ranking")
        self.web_dir = os.path.dirname(__file__)
        self.log_dir = os.path.join("/", "var", "local", "log", "cms", "ranking")

        # logging
        self.log_color = True

    def get(self, key):
        """Get the config value for the given key.

        """
        return getattr(self, key)

    def set(self, key, value):
        """Set the config value for the given key.

        """
        setattr(self, key, value)


# create an instance of the Config class
config = Config()


for path in [os.path.join("/", "usr", "local", "etc", "cms.ranking.conf"),
             os.path.join(".", "cms.ranking.conf")]:
    try:
        data = json.load(open(path))
        assert isinstance(data, dict)
        for key, value in data.iteritems():
            config.set(key, value)
    except:
        pass

try:
    os.makedirs(config.lib_dir)
except OSError:
    pass  # we assume the directory already exists...

try:
    os.makedirs(config.web_dir)
except OSError:
    pass  # we assume the directory already exists...

try:
    os.makedirs(config.log_dir)
except OSError:
    pass  # we assume the directory already exists...
