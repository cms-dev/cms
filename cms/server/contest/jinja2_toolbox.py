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

from jinja2 import PackageLoader

import cms.grading.languagemanager
from cmscommon.datetime import utc
from cms.server.jinja2_toolbox import GLOBAL_ENVIRONMENT


def extract_token_params(o):
    return {k[6:]: v
            for k, v in iteritems(o.__dict__) if k.startswith("token_")}


def astimezone(dt, tz):
    return dt.replace(tzinfo=utc).astimezone(tz).replace(tzinfo=None)


def instrument_cms_toolbox(env):
    env.filters["extract_token_params"] = extract_token_params
    env.filters["get_language"] = cms.grading.languagemanager.get_language
    env.filters["astimezone"] = astimezone


CWS_ENVIRONMENT = GLOBAL_ENVIRONMENT.overlay(
    extensions=['jinja2.ext.i18n'],
    loader=PackageLoader('cms.server.contest', 'templates'))
CWS_ENVIRONMENT.policies['ext.i18n.trimmed'] = True


instrument_cms_toolbox(CWS_ENVIRONMENT)
