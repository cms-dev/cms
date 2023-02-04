#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
# Copyright © 2022-2023 Manuel Gundlach <manuel.gundlach@gmail.com>
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

from __future__ import annotations

import errno
import jinja2
import jinja2.meta
import json
import logging
import os
import sys
import tomli
from dataclasses import dataclass, field
from datetime import datetime
from collections import namedtuple
from typing import Optional

from .log import set_detailed_logs


logger = logging.getLogger(__name__)


class Address(namedtuple("Address", "ip port")):
    def __repr__(self):
        return "%s:%d" % (self.ip, self.port)


class ServiceCoord(namedtuple("ServiceCoord", "name shard")):
    """A compact representation for the name and the shard number of a
    service (thus identifying it).

    """

    def __repr__(self):
        return "%s,%d" % (self.name, self.shard)


class ConfigError(Exception):
    """Exception for critical configuration errors."""
    pass


class AsyncConfig:
    """This class will contain the configuration for the
    services. This needs to be populated at the initilization stage.

    The *_services variables are dictionaries indexed by ServiceCoord
    with values of type Address.

    Core services are the ones that are supposed to run whenever the
    system is up.

    Other services are not supposed to run when the system is up, or
    anyway not constantly.

    """
    core_services = {}
    other_services = {}


async_config = AsyncConfig()


class Config:
    """This class will contain the configuration for CMS. This needs
    to be populated at the initilization stage. This is loaded by
    default with some sane data. See cms.toml.sample in the config
    directory for information on the meaning of the fields.

    """

    @dataclass
    class Systemwide:
        cmsuser: str = "cmsuser"
        temp_dir: str = "/tmp"
        backdoor: bool = False
        file_log_debug: bool = False
        stream_log_detailed: bool = False

    @dataclass
    class Database:
        database: str = "postgresql+psycopg2://cmsuser@localhost/cms"
        database_debug: bool = False
        twophase_commit: bool = False

    @dataclass
    class Worker:
        keep_sandbox: bool = False
        use_cgroups: bool = True
        sandbox_implementation: str = 'isolate'

    @dataclass
    class Sandbox:
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

    @dataclass
    class WebServers:
        secret_key_default: str = "8e045a51e4b102ea803c06f92841a1fb"
        secret_key: str = secret_key_default
        tornado_debug: bool = False

    @dataclass
    class ContestWebServer:
        listen_address: list[str] = \
            field(default_factory=lambda: [""])
        listen_port: list[int] = \
            field(default_factory=lambda: [8888])
        cookie_duration: int = 30 * 60  # 30 minutes
        submit_local_copy: bool = True
        submit_local_copy_path: str = "%s/submissions/"
        tests_local_copy: bool = True
        tests_local_copy_path: str = "%s/tests/"
        # (deprecated in favor of num_proxies_used)
        is_proxy_used: Optional[bool] = None
        num_proxies_used: Optional[int] = None
        max_submission_length: int = 100_000  # 100 KB
        max_input_length: int = 5_000_000  # 5 MB
        stl_path: str = "/usr/share/cppreference/doc/html/"
        # Prefix of 'shared-mime-info'[1] installation. It can be found
        # out using `pkg-config --variable=prefix shared-mime-info`, but
        # it's almost universally the same (i.e. '/usr') so it's hardly
        # necessary to change it.
        # [1] http://freedesktop.org/wiki/Software/shared-mime-info
        shared_mime_info_prefix: str = "/usr"

    @dataclass
    class AdminWebServer:
        listen_address: str = ""
        listen_port: int = 8889
        cookie_duration: int = 10 * 60 * 60  # 10 hours
        num_proxies_used: Optional[int] = None

    @dataclass
    class ProxyService:
        rankings: list[str] = \
            field(default_factory=lambda:
                  ["http://usern4me:passw0rd@localhost:8890/"])
        https_certfile: Optional[str] = None

    @dataclass
    class PrintingService:
        max_print_length: int = 10_000_000  # 10 MB
        printer: Optional[str] = None
        paper_size: str = "A4"
        max_pages_per_job: int = 10
        max_jobs_per_user: int = 10
        pdf_printing_allowed: bool = False

    def __init__(self):
        """Default values for configuration, plus decide if this
        instance is running from the system path or from the source
        directory.

        """
        self.async_config = async_config

        self.systemwide = self.Systemwide()
        self.database = self.Database()
        self.worker = self.Worker()
        self.sandbox = self.Sandbox()
        self.webservers = self.WebServers()
        self.cws = self.ContestWebServer()
        self.aws = self.AdminWebServer()
        self.proxyservice = self.ProxyService()
        self.printingservice = self.PrintingService()

        # Installed or from source?
        # We declare we are running from installed if the program was
        # NOT invoked through some python flavor, and the file is in
        # the prefix (or real_prefix to accommodate virtualenvs).
        bin_path = os.path.join(os.getcwd(), sys.argv[0])
        bin_name = os.path.basename(bin_path)
        bin_is_python = bin_name in ["ipython", "python", "python2", "python3"]
        bin_in_installed_path = bin_path.startswith(sys.prefix) or (
            hasattr(sys, 'real_prefix')
            and bin_path.startswith(sys.real_prefix))
        self.installed = bin_in_installed_path and not bin_is_python

        if self.installed:
            self.log_dir = os.path.join("/", "var", "local", "log", "cms")
            self.cache_dir = os.path.join("/", "var", "local", "cache", "cms")
            self.data_dir = os.path.join("/", "var", "local", "lib", "cms")
            self.run_dir = os.path.join("/", "var", "local", "run", "cms")
            etc_paths = [os.path.join("/", "usr", "local", "etc"),
                     os.path.join("/", "etc")]
        else:
            self.log_dir = "log"
            self.cache_dir = "cache"
            self.data_dir = "lib"
            self.run_dir = "run"
            etc_paths = [os.path.join(".", "config")]
            if '__file__' in globals():
                etc_paths += [os.path.abspath(os.path.join(
                          os.path.dirname(__file__),
                          '..', 'config'))]
            etc_paths += [os.path.join("/", "usr", "local", "etc"),
                      os.path.join("/", "etc")]

        legacy_paths = [os.path.join(p, "cms.conf") for p in etc_paths]
        paths = [os.path.join(p, "cms.toml") for p in etc_paths]

        # Allow user to override config file path using environment
        # variable 'CMS_CONFIG'.
        CMS_CONFIG_ENV_VAR = "CMS_CONFIG"
        if CMS_CONFIG_ENV_VAR in os.environ:
            legacy_paths = [os.environ[CMS_CONFIG_ENV_VAR]] + legacy_paths
            paths = [os.environ[CMS_CONFIG_ENV_VAR]] + paths

        # Attempt to load a config file.
        self._load(paths, legacy_paths)

        # If the configuration says to print detailed log on stdout,
        # change the log configuration.
        set_detailed_logs(self.systemwide.stream_log_detailed)

    def _load(self, paths, legacy_paths):
        """Try to load the config files one at a time, until one loads
        correctly.

        """
        for conf_file in legacy_paths:
            if self._load_unique(conf_file, True):
                break
        else:
            for conf_file in paths:
                if self._load_unique(conf_file):
                    break
            else:
                logging.warning("No valid configuration file found: "
                                "falling back to default values.")

    def _load_unique(self, path, is_legacy=False):
        """Populate the Config class with everything that sits inside
        the TOML file path (usually something like /etc/cms.toml). The
        only pieces of data treated differently are the elements of
        core_services and other_services that are sent to async
        config.

        Services whose name begins with an underscore are ignored, so
        they can be commented out in the configuration file.

        path (string): the path of the TOML (or JSON) config file.
        is_legacy (boolean): Whether the file is a legacy JSON file.

        """
        if is_legacy:
            # Load legacy config file.
            # Advice of incompatibility if config file is in legacy json format.
            try:
                with open(path, 'rb') as f:
                    legacy_data = json.load(f)
            except FileNotFoundError:
                return False
            except OSError as error:
                logger.warning("I/O error while opening file %s: [%s] %s",
                            path, errno.errorcode[error.errno],
                            os.strerror(error.errno))
                return False
            except ValueError as error:
                # FIXME With ENV var, this would FAIL (as in, show a misguided warning).
                logger.warning("Invalid syntax in file %s: %s", path, error)
                return False
            else:
                # Found legacy config file.
                # Parse it and try to create a TOML config from it that the user
                # can replace it with
                self._suggest_updated_legacy_config(path, legacy_data)
                return False
        else:
            # Load config file.
            try:
                with open(path, 'rb') as f:
                    data = tomli.load(f)
            except FileNotFoundError:
                logger.debug("Couldn't find config file %s.", path)
                return False
            except OSError as error:
                logger.warning("I/O error while opening file %s: [%s] %s",
                            path, errno.errorcode[error.errno],
                            os.strerror(error.errno))
                return False
            except ValueError as error:
                logger.warning("Invalid syntax in file %s: %s", path, error)
                return False

        logger.info("Using configuration file %s.", path)

        if "is_proxy_used" in data:
            logger.warning("The 'is_proxy_used' setting is deprecated, please "
                           "use 'num_proxies_used' instead.")

        # Put core and test services in async_config, ignoring those
        # whose name begins with "_".
        for part in ("core_services", "other_services"):
            for service in data[part]:
                if service.startswith("_"):
                    continue
                for shard_number, shard in \
                        enumerate(data[part][service]):
                    coord = ServiceCoord(service, shard_number)
                    getattr(self.async_config, part)[coord] = Address(*shard)
            del data[part]

        # Put everything else in self.
        for key, value in data.items():
            # Handle keys that have not been put under a proper section yet
            # and are instead in the generic "stray" section.
            # Here, it is checked that the respective attribute does _not_
            # exist to make sure nothing is overwritten inadvertently.
            if key == "stray":
                for key2, value2 in value.items():
                    if hasattr(self, key2):
                        logger.warning("Key %s in section stray can not be "
                                       "used because the attribute already "
                                       "exists.", key2)
                        return False
                    setattr(self, key2, value2)
                continue

            if not hasattr(self, key):
                logger.warning("Section name %s unknown.", key)
                return False
            section = getattr(self, key)

            for key2, value2 in value.items():
                if not hasattr(section, key2):
                    logger.warning("Key %s unknown in section %s.", key2, key)
                    return False
                setattr(section, key2, value2)

        # A value of "" means None for these attributes
        if self.proxyservice.https_certfile == "":
            self.proxyservice.https_certfile = None
        if self.printingservice.printer == "":
            self.printingservice.printer = None

        return True

    def _suggest_updated_legacy_config(self, path, legacy_data):
        logger.error("Legacy json config file found at %s. "
                     "The format for configuration files has changed to TOML. "
                     "With this change, the attributes are also structured "
                     "differently: They are put under sections, and variable "
                     "names have changed. "
                     "You should rewrite your configuration file for the new "
                     "format. A suggested translation will follow.", path)

        # Load data into the TOML config template

        # NOTE Values are rendered using json.dumps. This is only
        # heuristically correct and might in some cases not adhere to the
        # TOML specification. However, for the usual configuration values of
        # CMS this should be fine.

        jinja_env = jinja2.Environment(
            loader=jinja2.PackageLoader("cms", ""))

        ast = jinja_env.parse(
            jinja_env.loader.get_source(jinja_env,
                                        "cms_conf_legacy_mapping.toml.jinja")
        )
        attr_in_template = jinja2.meta.find_undeclared_variables(ast)

        legacy_attr_not_in_template = {
            k: v for k, v in legacy_data.items()
            if k not in attr_in_template and not k.startswith('_')
        }
        template_attr_not_in_legacy = [
            k for k in attr_in_template
            if k not in legacy_data and k != "stray"
        ]

        for k in legacy_attr_not_in_template:
            logger.warning("Key %s in legacy config is unknown and will "
                           "be exported to the Stray section.", k)

        # Attributes in the legacy config that don't appear in the TOML
        # template will be put under their own 'stray' section.
        if len(legacy_attr_not_in_template) == 0:
            stray = ""
        else:
            stray = "\n\n[stray]\n\n" + \
                '\n'.join("{} = {}".format(k, json.dumps(v))
                          for k, v in legacy_attr_not_in_template.items())
        legacy_data["stray"] = stray

        for k in template_attr_not_in_legacy:
            logger.warning("Key %s is missing in legacy config; "
                           "the value will be set to the default.", k)

        template = jinja_env.get_template("cms_conf_legacy_mapping.toml.jinja")
        updated_config = template.render(legacy_data)

        logger.info("==== Config heuristically translated to new format below ====\n"
                    "%s\n"
                    "==== Config heuristically translated to new format above ====\n"
                    "You can find your legacy config updated to the "
                    "current config format above. "
                    "Please check the output and save it as %s. ",
                    updated_config,
                    os.path.join(os.path.dirname(path), "cms.toml"))


config = Config()
