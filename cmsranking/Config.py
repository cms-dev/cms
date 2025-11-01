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

from dataclasses import dataclass, field
import logging
import os
import sys

from cmscommon import conf_parser
from cmsranking.Logger import add_file_handler


logger = logging.getLogger(__name__)


# Try to find CMS installation root from the venv in which we run
if sys.prefix == "/usr":
    logger.critical("CMS must be run within a Python virtual environment")
    sys.exit(1)

def default_path(name):
    return os.path.join(sys.prefix, name)


@dataclass
class PublicConfig:
    show_id_column: bool = False


@dataclass
class Config:
    # Connection.
    bind_address: str = "127.0.0.1"
    http_port: int | None = 8890
    https_port: int | None = None
    https_certfile: str | None = None
    https_keyfile: str | None = None

    # Authentication.
    realm_name: str = "Scoreboard"
    username: str = "usern4me"
    password: str = "passw0rd"

    # UI.
    public: PublicConfig = field(default_factory=PublicConfig)

    # Buffers
    buffer_size: int = 100

    log_dir: str = default_path("log/ranking")
    lib_dir: str = default_path("lib/ranking")

    def __post_init__(self):
        os.makedirs(self.lib_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)
        add_file_handler(self.log_dir)


def load_config(config_override: str | None = None) -> Config:
    default_config_file = default_path("etc/cms_ranking.toml")
    config_file = os.environ.get("CMS_RANKING_CONFIG", default_config_file)
    if config_override is not None:
        config_file = config_override
    hint = " (maybe you need to convert it from cms.ranking.conf to cms_ranking.toml?)"
    return conf_parser.parse_config(config_file, Config, hint)
