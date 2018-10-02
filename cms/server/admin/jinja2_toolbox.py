#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""Provide a Jinja2 environment tailored to AWS.

Extend the global generic Jinja2 environment to inject tools that are
useful specifically to the use that AWS makes of it.

"""

from jinja2 import PackageLoader

from cms.grading.languagemanager import LANGUAGES
from cms.grading.scoretypes import SCORE_TYPES
from cms.grading.tasktypes import TASK_TYPES
from cms.server.admin.formatting import format_dataset_attrs
from cms.server.jinja2_toolbox import GLOBAL_ENVIRONMENT
from cmscommon.crypto import get_hex_random_key, parse_authentication


def safe_parse_authentication(auth):
    try:
        method, password = parse_authentication(auth)
    except ValueError:
        method, password = "plaintext", ""
    return method, password


def instrument_cms_toolbox(env):
    env.globals["TASK_TYPES"] = TASK_TYPES
    env.globals["SCORE_TYPES"] = SCORE_TYPES
    env.globals["LANGUAGES"] = LANGUAGES
    env.globals["get_hex_random_key"] = get_hex_random_key
    env.globals["parse_authentication"] = safe_parse_authentication


def instrument_formatting_toolbox(env):
    env.filters["format_dataset_attrs"] = format_dataset_attrs


AWS_ENVIRONMENT = GLOBAL_ENVIRONMENT.overlay(
    # Load templates from AWS's package (use package rather than file
    # system as that works even in case of a compressed distribution).
    loader=PackageLoader('cms.server.admin', 'templates'))


instrument_cms_toolbox(AWS_ENVIRONMENT)
instrument_formatting_toolbox(AWS_ENVIRONMENT)
