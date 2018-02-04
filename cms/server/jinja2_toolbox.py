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

from jinja2 import Environment, StrictUndefined, contextfilter, contextfunction

from cmscommon.datetime import make_timestamp, utc
from cmscommon.mimetypes import get_type_for_file_name, get_name_for_type, \
    get_icon_for_type
from cms.grading.languagemanager import get_language
from cms.grading.scoretypes import get_score_type
from cms.grading.tasktypes import get_task_type
from cms.server.contest.formatting import get_score_class


@contextfilter
def all_(ctx, l, test=None, *args):
    """Check if all elements of the given list pass the given test.

    ctx (Context): a Jinja2 context, needed to retrieve the test
        function by its name and to execute it.
    l (list): a list of objects.
    test (str|None): the name of the test to execute on each object of
        l (leave unspecified to just check their truth value).
    *args: parameters to pass to the test function.

    return (bool): all(test(i, *args) for i in l).

    """
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
    """Check if any element of the given list passes the given test.

    ctx (Context): a Jinja2 context, needed to retrieve the test
        function by its name and to execute it.
    l (list): a list of objects.
    test (str|None): the name of the test to execute on each object of
        l (leave unspecified to just check their truth value).
    *args: parameters to pass to the test function.

    return (bool): any(test(i, *args) for i in l).

    """
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
    """Filter the given dict: keep only items that pass the given test.

    ctx (Context): a Jinja2 context, needed to retrieve the test
        function by its name and execute it.
    d (dict): a dict.
    test (str|None): the name of the test to execute on either the key
        or the value of each item of d (leave unspecified to just check
        the truth value).
    *args: parameters to pass to the test function.
    by (str): either "key" (default) or "value", specifies on which
        component to perform the test.

    return (dict): {k, v for k, v in d.items() if test(k/v, *args)}.

    """
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
    return dict((k, v) for k, v in iteritems(d)
                if ctx.call(test, {"key": k, "value": v}[by], *args))


@contextfunction
def today(ctx, dt):
    """Returns whether the given datetime is today.

    ctx (Context): a Jinja2 context, needed to retrieve the current
        datetime and the timezone to use when comparing.
    dt (datetime): a datetime.

    return (bool): whether dt occurred today in the timezone.

    """
    now = ctx["now"]
    timezone = ctx["timezone"]
    return dt.replace(tzinfo=utc).astimezone(timezone).date() \
        == now.replace(tzinfo=utc).astimezone(timezone).date()


def instrument_generic_toolbox(env):
    env.globals["iterkeys"] = iterkeys
    env.globals["itervalues"] = itervalues
    env.globals["iteritems"] = iteritems
    env.globals["next"] = next

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

    env.filters["to_language"] = get_language

    env.tests["contains"] = lambda s, p: p in s
    env.tests["endswith"] = lambda s, p: s.endswith(p)

    env.tests["today"] = today


GLOBAL_ENVIRONMENT = Environment(
    # These cause a line that only contains a control block to be
    # suppressed from the output, making it more readable.
    trim_blocks=True, lstrip_blocks=True,
    # This causes an error when we try to render an undefined value.
    undefined=StrictUndefined,
    # Force autoescape of string, always and forever.
    autoescape=True,
    # Cache all templates, no matter how many.
    cache_size=-1,
    # Don't check the disk every time to see whether the templates'
    # files have changed.
    auto_reload=False)


instrument_generic_toolbox(GLOBAL_ENVIRONMENT)
