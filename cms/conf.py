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

    def __init__(self):
        """Default values for configuration, plus decide if this
        instance is running from the system path or from the source
        directory.

        """
        self.async_config = async_config

        # System-wide.
        self.cmsuser: str = "cmsuser"
        self.temp_dir: str = "/tmp"
        self.backdoor: bool = False
        self.file_log_debug: bool = False
        self.stream_log_detailed: bool = False

        # Database.
        self.database: str = "postgresql+psycopg2://cmsuser@localhost/cms"
        self.database_debug: bool = False
        self.twophase_commit: bool = False

        # Worker.
        self.keep_sandbox: bool = False
        self.use_cgroups: bool = True
        self.sandbox_implementation: str = 'isolate'

        # Sandbox.
        # Max size of each writable file during an evaluation step, in KiB.
        self.max_file_size: int = 1024 * 1024  # 1 GiB
        # Max processes, CPU time (s), memory (KiB) for compilation runs.
        self.compilation_sandbox_max_processes: int = 1000
        self.compilation_sandbox_max_time_s: float = 10.0
        self.compilation_sandbox_max_memory_kib: int = 512 * 1024  # 512 MiB
        # Max processes, CPU time (s), memory (KiB) for trusted runs.
        self.trusted_sandbox_max_processes: int = 1000
        self.trusted_sandbox_max_time_s: float = 10.0
        self.trusted_sandbox_max_memory_kib: int = 4 * 1024 * 1024  # 4 GiB

        # WebServers.
        self.secret_key_default: str = "8e045a51e4b102ea803c06f92841a1fb"
        self.secret_key: str = self.secret_key_default
        self.tornado_debug: bool = False

        # ContestWebServer.
        self.contest_listen_address: list[str] = [""]
        self.contest_listen_port: list[int] = [8888]
        self.contest_cookie_duration: int = 30 * 60  # 30 minutes
        self.submit_local_copy: bool = True
        self.submit_local_copy_path: str = "%s/submissions/"
        self.tests_local_copy: bool = True
        self.tests_local_copy_path: str = "%s/tests/"
        self.is_proxy_used: Optional[bool] = None  # (deprecated)
        self.contest_num_proxies_used: Optional[int] = None
        self.max_submission_length: int = 100_000  # 100 KB
        self.max_input_length: int = 5_000_000  # 5 MB
        self.stl_path: str = "/usr/share/cppreference/doc/html/"
        # Prefix of 'shared-mime-info'[1] installation. It can be found
        # out using `pkg-config --variable=prefix shared-mime-info`, but
        # it's almost universally the same (i.e. '/usr') so it's hardly
        # necessary to change it.
        # [1] http://freedesktop.org/wiki/Software/shared-mime-info
        self.shared_mime_info_prefix: str = "/usr"

        # AdminWebServer.
        self.admin_listen_address: str = ""
        self.admin_listen_port: int = 8889
        self.admin_cookie_duration: int = 10 * 60 * 60  # 10 hours
        self.admin_num_proxies_used: Optional[int] = None

        # ProxyService.
        self.rankings: list[str] = ["http://usern4me:passw0rd@localhost:8890/"]
        self.https_certfile: Optional[str] = None

        # PrintingService.
        self.max_print_length: int = 10_000_000  # 10 MB
        self.printer: Optional[str] = None
        self.paper_size: str = "A4"
        self.max_pages_per_job: int = 10
        self.max_jobs_per_user: int = 10
        self.pdf_printing_allowed: bool = False

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

        paths = [os.path.join(p, "cms.conf") for p in etc_paths] + \
                [os.path.join(p, "cms.toml") for p in etc_paths]

        # Allow user to override config file path using environment
        # variable 'CMS_CONFIG'.
        CMS_CONFIG_ENV_VAR = "CMS_CONFIG"
        if CMS_CONFIG_ENV_VAR in os.environ:
            paths = [os.environ[CMS_CONFIG_ENV_VAR]] + paths

        # Attempt to load a config file.
        self._load(paths)

        # If the configuration says to print detailed log on stdout,
        # change the log configuration.
        set_detailed_logs(self.stream_log_detailed)

    def _load(self, paths):
        """Try to load the config files one at a time, until one loads
        correctly.

        """
        for conf_file in paths:
            if self._load_unique(conf_file):
                break
        else:
            logging.warning("No valid configuration file found: "
                            "falling back to default values.")

    def _load_unique(self, path):
        """Populate the Config class with everything that sits inside
        the TOML file path (usually something like /etc/cms.toml). The
        only pieces of data treated differently are the elements of
        core_services and other_services that are sent to async
        config.

        Services whose name begins with an underscore are ignored, so
        they can be commented out in the configuration file.

        path (string): the path of the TOML (or JSON) config file.

        """

        # Load config file.
        for loader, loader_name, success_handler in \
            ((tomli, "TOML", lambda p, d: None),
             (json, "JSON", self._suggest_updated_legacy_config)):
            try:
                with open(path, 'rb') as f:
                    data = loader.load(f)
            except FileNotFoundError:
                logger.debug("Couldn't find config file %s.", path)
                return False
            except OSError as error:
                logger.warning("I/O error while opening file %s: [%s] %s",
                               path, errno.errorcode[error.errno],
                               os.strerror(error.errno))
                return False
            except ValueError as error:
                logger.warning("Invalid syntax (assuming %s) in file %s: %s",
                               loader_name, path, error)
            else:
                success_handler(path, data)
                break
        else:
            return False

        logger.info("Using configuration file %s.", path)

        if "is_proxy_used" in data:
            logger.warning("The 'is_proxy_used' setting is deprecated, please "
                           "use 'contest_num_proxies_used' instead.")

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

        # These keys have been renamed. If the old key name is still used, it
        # is still regarded.
        for key in ("cookie_duration", "num_proxies_used"):
            if key in data:
                new_key = "contest_" + key
                if new_key in data:
                    logger.error("Conflicting keys %s and %s.", key, new_key)
                    continue
                else:
                    data[new_key] = data[key]
                del data[key]

        # A value of "" means None for these attributes
        for key in ("https_certfile", "printer"):
            if key in data and data[key] == "":
                data[key] = None

        # Put everything else in self.
        for key, value in data.items():
            # Ignore keys whose name begins with "_".
            if key.startswith("_"):
                continue
            # Warn about unknown keys.
            if not hasattr(self, key):
                logger.warning("Key %s unknown.", key)
            setattr(self, key, value)

        return True

    def _suggest_updated_legacy_config(self, path, legacy_data):
        logger.error("Legacy json config file found at %s. "
                     "The format for configuration files has changed to TOML. "
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
            logger.warning("Key %s in legacy config unknown (but will be "
                           "exported).", k)

        # Attributes in the legacy config that don't appear in the TOML
        # template will be put under a 'stray' "header".
        if len(legacy_attr_not_in_template) == 0:
            stray = ""
        else:
            stray = "\n### stray ###\n\n" + \
                '\n'.join("{} = {}".format(k, json.dumps(v))
                          for k, v in legacy_attr_not_in_template.items()) + \
                "\n"
        assert "stray" not in legacy_data
        template_data = legacy_data.copy()
        template_data["stray"] = stray

        for k in template_attr_not_in_legacy:
            logger.warning("Key %s is missing in legacy config; "
                           "the value will be set to the default.", k)

        template = jinja_env.get_template("cms_conf_legacy_mapping.toml.jinja")
        updated_config = template.render(template_data)

        logger.info("==== Config heuristically translated to new format below ====\n"
                    "%s\n"
                    "==== Config heuristically translated to new format above ====\n"
                    "You can find your legacy config updated to the "
                    "current config format above. "
                    "Please check the output, save it as %s and remove %s. ",
                    updated_config,
                    os.path.join(os.path.dirname(path), "cms.toml"),
                    path)


config = Config()
