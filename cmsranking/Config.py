#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2011-2016 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

import errno
import logging
import os
import sys
import tomllib
import typing

import pkg_resources

from cmsranking.Logger import add_file_handler


logger = logging.getLogger(__name__)


CMS_RANKING_CONFIG_ENV_VAR = "CMS_RANKING_CONFIG"


class Config:
    """An object holding the current configuration.

    """
    def __init__(self):
        """Fill this object with the default values for each key.

        """
        # Connection.
        self.bind_address = ''
        self.http_port: int | None = 8890
        self.https_port: int | None = None
        self.https_certfile: str | None = None
        self.https_keyfile: str | None = None
        # TODO unused???
        self.timeout = 600  # 10 minutes (in seconds)

        # Authentication.
        self.realm_name = 'Scoreboard'
        self.username = 'usern4me'
        self.password = 'passw0rd'

        # Buffers
        self.buffer_size = 100  # Needs to be strictly positive.

        self.web_dir = pkg_resources.resource_filename("cmsranking", "static")

        # Try to find CMS installation root from the venv in which we run
        self.base_dir = sys.prefix
        if self.base_dir == '/usr':
            logger.critical('CMS must be run within a Python virtual environment')
            sys.exit(1)
        self.log_dir = os.path.join(self.base_dir, 'log/ranking')
        self.lib_dir = os.path.join(self.base_dir, 'lib/ranking')

        # Default config file path can be overridden using environment
        # variable 'CMS_RANKING_CONFIG'.
        default_config_file = os.path.join(self.base_dir, 'etc/cms_ranking.toml')
        self.config_file = os.environ.get('CMS_RANKING_CONFIG', default_config_file)

    def get(self, key):
        """Get the config value for the given key.

        """
        return getattr(self, key)

    def load(self, config_override: str | None = None):
        """Load the configuration file.

        """

        config_file = config_override if config_override is not None else self.config_file
        if not self._load_config(config_file):
            logging.critical(f'Cannot load configuration file {config_file}')
            sys.exit(1)

        try:
            os.makedirs(self.lib_dir)
        except OSError:
            pass  # We assume the directory already exists...

        try:
            os.makedirs(self.web_dir)
        except OSError:
            pass  # We assume the directory already exists...

        try:
            os.makedirs(self.log_dir)
        except OSError:
            pass  # We assume the directory already exists...

        add_file_handler(self.log_dir)

    def _load_config(self, path: str) -> bool:
        """Populate config parameters from the given file.

        Parse it as TOML and store in self all configuration properties
        it defines. Log critical message and return False if anything
        goes wrong or seems odd.

        path: the path of the TOML config file.
        returns: whether parsing was successful.

        """
        # Load config file.
        try:
            with open(path, 'rb') as f:
                data = tomllib.load(f)
        except FileNotFoundError:
            logger.debug("Couldn't find config file %s (maybe you need to "
                         "convert it from cms_ranking.conf to cms_ranking.toml?).", path)
            return False
        except OSError as error:
            logger.warning("I/O error while opening file %s: [%s] %s",
                           path, errno.errorcode[error.errno],
                           os.strerror(error.errno))
            return False
        except ValueError as error:
            logger.warning("Invalid syntax in file %s: %s", path, error)
            return False

        # Store every config property.
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                logger.warning("Unrecognized key %s in config!", key)

        return True
