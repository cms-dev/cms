#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
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

import dataclasses
import logging
import os
import sys
import typing
from dataclasses import dataclass

from cms.log import set_detailed_logs
from cmscommon import conf_parser
from cmscommon.conf_parser import ConfigError

logger = logging.getLogger(__name__)


class Address(typing.NamedTuple):
    ip: str
    port: int

    def __str__(self):
        return "%s:%d" % (self.ip, self.port)


class ServiceCoord(typing.NamedTuple):
    """A compact representation for the name and the shard number of a
    service (thus identifying it).
    """

    name: str
    shard: int

    def __str__(self):
        return "%s,%d" % (self.name, self.shard)


# Try to find CMS installation root from the venv in which we run
if sys.prefix == "/usr":
    logger.critical("CMS must be run within a Python virtual environment")
    sys.exit(1)

def default_path(name):
    return os.path.join(sys.prefix, name)


@dataclass()
class GlobalConfig:
    temp_dir: str = "/tmp"
    backdoor: bool = False
    file_log_debug: bool = False
    stream_log_detailed: bool = False
    log_dir: str = default_path("log")
    cache_dir: str = default_path("cache")
    data_dir: str = default_path("lib")
    run_dir: str = default_path("run")


@dataclass()
class DatabaseConfig:
    url: str
    debug: bool = False
    twophase_commit: bool = False


@dataclass()
class WorkerConfig:
    keep_sandbox: bool = False


@dataclass()
class SandboxConfig:
    sandbox_implementation: str = "isolate"
    # Max size of each writable file during an evaluation step, in KiB.
    max_file_size: int = 1024 * 1024  # 1 GiB
    # Max processes, CPU time (s), memory (KiB) for compilation runs.
    compilation_sandbox_max_processes: int = 1000
    compilation_sandbox_max_time_s: float = 10.0
    compilation_sandbox_max_memory_kib: int = 512 * 1024  # 512 MiB
    # Max processes, CPU time (s), memory (KiB) for trusted runs.
    trusted_sandbox_max_processes: int = 1000
    trusted_sandbox_max_time_s: float = 10.0
    trusted_sandbox_max_memory_kib: int = 4 * 1024 * 1024  # 4 GiB


@dataclass()
class WebServerConfig:
    # This doesn't have a type hint, so @dataclass (and thus the config parser)
    # ignore it.
    DEFAULT_SECRET_KEY = "8e045a51e4b102ea803c06f92841a1fb"
    secret_key: str = DEFAULT_SECRET_KEY
    tornado_debug: bool = False


@dataclass()
class CWSConfig:
    listen_address: tuple[str, ...] = ("127.0.0.1",)
    listen_port: tuple[int, ...] = (8888,)
    cookie_duration: int = 30 * 60  # 30 minutes
    num_proxies_used: int = 0

    submit_local_copy: bool = True
    submit_local_copy_path: str = "%s/submissions/"
    tests_local_copy: bool = True
    tests_local_copy_path: str = "%s/tests/"

    max_submission_length: int = 100_000  # 100 KB
    max_input_length: int = 5_000_000  # 5 MB

    stl_path: str = "/usr/share/cppreference/doc/html/"
    docs_path: str | None = None

    contest_admin_token: str | None = None


@dataclass()
class AWSConfig:
    listen_address: str = "127.0.0.1"
    listen_port: int = 8889
    cookie_duration: int = 10 * 60 * 60  # 10 hours
    num_proxies_used: int = 0


@dataclass()
class ProxyServiceConfig:
    rankings: tuple[str, ...] = ()
    https_certfile: str | None = None


@dataclass()
class PrometheusConfig:
    listen_address: str = "127.0.0.1"
    listen_port: int = 8811


@dataclass()
class TelegramBotConfig:
    bot_token: str
    chat_id: str


field_helper = lambda T: dataclasses.field(default_factory=T)

@dataclass(kw_only=True)
class Config:
    # Ideally these would all look like
    #   global_: GlobalConfig = GlobalConfig()
    # but dataclasses doesn't like it, because these are all mutable default
    # values. We could make the individual config sections frozen, but then we
    # can't easily patch them for unit tests.
    global_: GlobalConfig = field_helper(GlobalConfig)
    database: DatabaseConfig
    worker: WorkerConfig = field_helper(WorkerConfig)
    sandbox: SandboxConfig = field_helper(SandboxConfig)
    web_server: WebServerConfig = field_helper(WebServerConfig)
    contest_web_server: CWSConfig = field_helper(CWSConfig)
    admin_web_server: AWSConfig = field_helper(AWSConfig)
    proxy_service: ProxyServiceConfig = field_helper(ProxyServiceConfig)
    prometheus: PrometheusConfig = field_helper(PrometheusConfig)
    telegram_bot: TelegramBotConfig | None = None
    # This is the one that will be provided in the config file.
    services_: dict[str, list[tuple[str, int]]]
    # And this is the one we want to use inside CMS.
    services: dict[ServiceCoord, Address] = dataclasses.field(init=False)

    def __post_init__(self):
        self.services = {}
        for service_name, instances in self.services_.items():
            for shard_number, shard in enumerate(instances):
                coord = ServiceCoord(service_name, shard_number)
                self.services[coord] = Address(*shard)

        # If the configuration says to print detailed log on stdout,
        # change the log configuration.
        set_detailed_logs(self.global_.stream_log_detailed)


def make_config():
    # Default config file path can be overridden using environment
    # variable 'CMS_CONFIG'.
    default_config_file = default_path("etc/cms.toml")
    config_file = os.environ.get("CMS_CONFIG", default_config_file)

    hint = " (maybe you need to convert it from cms.conf to cms.toml?)"
    return conf_parser.parse_config(config_file, Config, hint)


config = make_config()
