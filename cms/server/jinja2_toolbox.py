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

"""Provide a generic Jinja2 environment.

Create a Jinja2 environment and instrument it with utilities (globals,
filters, tests, etc. that are useful for generic global usage.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *
from future.builtins import *
from six import iterkeys, itervalues, iteritems

from jinja2 import environmentfilter, Environment, StrictUndefined


@environmentfilter
def dictselect(env, d, *args, **kwargs):
    if len(args) == 0:
        test = bool
    else:
        test = env.tests[args[0]]
        args = args[1:]
    by = kwargs.pop("by", "key")
    if len(kwargs) > 0:
        raise ValueError("Invalid keyword argument: %s"
                         % next(iterkeys(kwargs)))
    if by == "key":
        return dict((k, v) for k, v in iteritems(d) if test(k, *args))
    if by == "value":
        return dict((k, v) for k, v in iteritems(d) if test(v, *args))
    raise ValueError("Invalid value of \"by\" keyword argument: %s" % by)

import cmscommon.mimetypes
from cms.grading.scoretypes import get_score_type
from cms.grading.tasktypes import get_task_type
from cms.server.contest.formatting import get_score_class


def instrument_generic_toolbox(env):
    env.globals["iterkeys"] = iterkeys
    env.globals["itervalues"] = itervalues
    env.globals["iteritems"] = iteritems

    env.globals["get_task_type"] = get_task_type
    env.globals["get_score_type"] = get_score_type

    env.globals["get_score_class"] = get_score_class()

    env.globals["get_mimetype_for_file_name"] = \
        cmscommon.mimetypes.get_type_for_file_name
    env.globals["get_name_for_mimetype"] = \
        cmscommon.mimetypes.get_name_for_type
    env.globals["get_icon_for_mimetype"] = \
        cmscommon.mimetypes.get_icon_for_type

    env.filters["call"] = lambda c, *args, **kwargs: c(*args, **kwargs)
    env.filters["dictselect"] = dictselect

    env.tests["contains"] = lambda s, p: p in s
    env.tests["endswith"] = lambda s, p: s.endswith(p)


GLOBAL_ENVIRONMENT = Environment(
    trim_blocks=True, lstrip_blocks=True, undefined=StrictUndefined,
    autoescape=True, cache_size=-1, auto_reload=False)


instrument_generic_toolbox(GLOBAL_ENVIRONMENT)
