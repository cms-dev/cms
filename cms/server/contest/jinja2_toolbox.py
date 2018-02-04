#!/usr/bin/env python2
# -*- coding: utf-8 -*-

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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *
from future.builtins import *
from six import iteritems

from jinja2 import contextfilter, PackageLoader

import cms.grading
import cms.server.contest.formatting
from cms.server.jinja2_toolbox import GLOBAL_ENVIRONMENT


@contextfilter
def format_datetime(ctx, dt):
    translation = ctx["translation"]
    timezone = ctx["timezone"]
    return translation.format_datetime(dt, timezone)


@contextfilter
def format_time(ctx, dt):
    translation = ctx["translation"]
    timezone = ctx["timezone"]
    return translation.format_time(dt, timezone)


@contextfilter
def format_datetime_smart(ctx, dt):
    translation = ctx["translation"]
    now = ctx["now"]
    timezone = ctx["timezone"]
    return translation.format_datetime_smart(dt, now, timezone)


@contextfilter
def format_timedelta(ctx, td):
    translation = ctx["translation"]
    return translation.format_timedelta(td)


@contextfilter
def format_duration(ctx, d, length="short"):
    translation = ctx["translation"]
    return translation.format_duration(d, length)


@contextfilter
def format_size(ctx, s):
    translation = ctx["translation"]
    return translation.format_size(s)


@contextfilter
def format_decimal(ctx, n):
    translation = ctx["translation"]
    return translation.format_decimal(n)


@contextfilter
def format_token_rules(ctx, tokens, t_type=None):
    translation = ctx["translation"]
    return cms.server.contest.formatting.format_token_rules(
        tokens, t_type, translation=translation)


@contextfilter
def format_status_text(ctx, status_text):
    translation = ctx["translation"]
    return cms.grading.format_status_text(status_text, translation=translation)


def instrument_formatting_toolbox(env):
    env.filters["format_datetime"] = format_datetime
    env.filters["format_time"] = format_time
    env.filters["format_datetime_smart"] = format_datetime_smart
    env.filters["format_timedelta"] = format_timedelta
    env.filters["format_duration"] = format_duration
    env.filters["format_size"] = format_size
    env.filters["format_decimal"] = format_decimal
    env.filters["format_token_rules"] = format_token_rules
    env.filters["format_status_text"] = format_status_text


def extract_token_params(o):
    return {k[6:]: v
            for k, v in iteritems(o.__dict__) if k.startswith("token_")}


def instrument_cms_toolbox(env):
    env.filters["extract_token_params"] = extract_token_params


CWS_ENVIRONMENT = GLOBAL_ENVIRONMENT.overlay(
    # Allow the use of {% trans %} tags to localize strings.
    extensions=['jinja2.ext.i18n'],
    # Load templates from CWS's package (use package rather than file
    # system as that works even in case of a compressed distribution).
    loader=PackageLoader('cms.server.contest', 'templates'))
# This compresses all leading/trailing whitespace and line breaks of
# internationalized messages when translating and extracting them.
CWS_ENVIRONMENT.policies['ext.i18n.trimmed'] = True


instrument_formatting_toolbox(CWS_ENVIRONMENT)
instrument_cms_toolbox(CWS_ENVIRONMENT)
