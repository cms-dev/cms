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

from jinja2 import Environment, StrictUndefined, contextfilter

from cmscommon.datetime import make_timestamp, utc
from cmscommon.mimetypes import get_type_for_file_name, get_name_for_type, \
    get_icon_for_type
from cms.grading.languagemanager import get_language
from cms.grading.scoretypes import get_score_type
from cms.grading.tasktypes import get_task_type
from cms.server.contest.formatting import get_score_class


@contextfilter
def all_(ctx, l, test=None, *args):
    if test is None:
        test = bool
    else:
        test = ctx.environment.tests[test]
    for i in l:
        if not ctx.call(test, i, *args):
            return False
    return True


@contextfilter
def any_(ctx, l, test=None, *args):
    if test is None:
        test = bool
    else:
        test = ctx.environment.tests[test]
    for i in l:
        if ctx.call(test, i, *args):
            return True
    return False


# FIXME once we drop py2 do dictselect(ctx, d, test=None, *args, by="key")
@contextfilter
def dictselect(ctx, d, test=None, *args, **kwargs):
    if test is None:
        test = bool
    else:
        test = ctx.environment.tests[test]
    by = kwargs.pop("by", "key")
    if len(kwargs) > 0:
        raise ValueError("Invalid keyword argument: %s"
                         % next(iterkeys(kwargs)))
    if by not in {"key", "value"}:
        raise ValueError("Invalid value of \"by\" keyword argument: %s" % by)
    test = lambda i: ctx.call(test, i[{"key": 0, "value": 1}[by]], *args)
    return dict(i for i in iteritems(d) if test(i))


@contextfilter
def today(ctx, dt):
    now = ctx["now"]
    timezone = ctx["timezone"]
    return dt.replace(tzinfo=utc).astimezone(timezone).date() \
        == now.replace(tzinfo=utc).astimezone(timezone).date()


def instrument_generic_toolbox(env):
    env.globals["iterkeys"] = iterkeys
    env.globals["itervalues"] = itervalues
    env.globals["iteritems"] = iteritems

    env.globals["get_task_type"] = get_task_type
    env.globals["get_score_type"] = get_score_type

    env.globals["get_score_class"] = get_score_class

    env.globals["get_mimetype_for_file_name"] = get_type_for_file_name
    env.globals["get_name_for_mimetype"] = get_name_for_type
    env.globals["get_icon_for_mimetype"] = get_icon_for_type

    env.filters["all"] = all_
    env.filters["any"] = any_
    env.filters["dictselect"] = dictselect
    env.filters["make_timestamp"] = make_timestamp

    env.filters["get_language"] = get_language

    env.tests["endswith"] = lambda s, p: s.endswith(p)


GLOBAL_ENVIRONMENT = Environment(
    trim_blocks=True, lstrip_blocks=True, undefined=StrictUndefined,
    autoescape=True, cache_size=-1, auto_reload=False)


instrument_generic_toolbox(GLOBAL_ENVIRONMENT)
