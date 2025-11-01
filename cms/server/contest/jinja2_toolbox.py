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

"""Provide a Jinja2 environment tailored to CWS.

Extend the global generic Jinja2 environment to inject tools that are
useful specifically to the use that CWS makes of it.

"""

from jinja2 import contextfilter, PackageLoader

from cms.server.jinja2_toolbox import GLOBAL_ENVIRONMENT
from .formatting import format_token_rules, get_score_class


def extract_token_params(o):
    return {k[6:]: v
            for k, v in o.__dict__.items() if k.startswith("token_")}


def instrument_cms_toolbox(env):
    env.filters["extract_token_params"] = extract_token_params


@contextfilter
def wrapped_format_token_rules(ctx, tokens, t_type=None):
    translation = ctx["translation"]
    return format_token_rules(tokens, t_type, translation=translation)


def instrument_formatting_toolbox(env):
    env.globals["get_score_class"] = get_score_class

    env.filters["format_token_rules"] = wrapped_format_token_rules


CWS_ENVIRONMENT = GLOBAL_ENVIRONMENT.overlay(
    # Load templates from CWS's package (use package rather than file
    # system as that works even in case of a compressed distribution).
    loader=PackageLoader('cms.server.contest', 'templates'))


instrument_cms_toolbox(CWS_ENVIRONMENT)
instrument_formatting_toolbox(CWS_ENVIRONMENT)
