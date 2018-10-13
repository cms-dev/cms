#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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

from jinja2 import Environment, StrictUndefined, contextfilter, \
    contextfunction, environmentfunction

from cms import TOKEN_MODE_DISABLED, TOKEN_MODE_FINITE, TOKEN_MODE_INFINITE, \
    TOKEN_MODE_MIXED, FEEDBACK_LEVEL_FULL, FEEDBACK_LEVEL_RESTRICTED
from cms.db import SubmissionResult, UserTestResult
from cms.grading import format_status_text
from cms.grading.languagemanager import get_language
from cms.locale import DEFAULT_TRANSLATION
from cmscommon.constants import \
    SCORE_MODE_MAX, SCORE_MODE_MAX_SUBTASK, SCORE_MODE_MAX_TOKENED_LAST
from cmscommon.datetime import make_datetime, make_timestamp, utc, local_tz
from cmscommon.mimetypes import get_type_for_file_name, get_name_for_type, \
    get_icon_for_type


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
    if kwargs:
        raise ValueError("Invalid keyword argument: %s"
                         % next(iter(kwargs.keys())))
    if by not in {"key", "value"}:
        raise ValueError("Invalid value of \"by\" keyword argument: %s" % by)
    return dict((k, v) for k, v in d.items()
                if ctx.call(test, {"key": k, "value": v}[by], *args))


@contextfunction
def today(ctx, dt):
    """Returns whether the given datetime is today.

    ctx (Context): a Jinja2 context, needed to retrieve the current
        datetime and the timezone to use when comparing.
    dt (datetime): a datetime.

    return (bool): whether dt occurred today in the timezone.

    """
    now = ctx.get("now", make_datetime())
    timezone = ctx.get("timezone", local_tz)
    return dt.replace(tzinfo=utc).astimezone(timezone).date() \
        == now.replace(tzinfo=utc).astimezone(timezone).date()


def instrument_generic_toolbox(env):
    env.globals["iter"] = iter
    env.globals["next"] = next

    # Needed for some constants.
    env.globals["SubmissionResult"] = SubmissionResult
    env.globals["UserTestResult"] = UserTestResult

    env.globals["SCORE_MODE_MAX_TOKENED_LAST"] = SCORE_MODE_MAX_TOKENED_LAST
    env.globals["SCORE_MODE_MAX"] = SCORE_MODE_MAX
    env.globals["SCORE_MODE_MAX_SUBTASK"] = SCORE_MODE_MAX_SUBTASK

    env.globals["TOKEN_MODE_DISABLED"] = TOKEN_MODE_DISABLED
    env.globals["TOKEN_MODE_FINITE"] = TOKEN_MODE_FINITE
    env.globals["TOKEN_MODE_INFINITE"] = TOKEN_MODE_INFINITE
    env.globals["TOKEN_MODE_MIXED"] = TOKEN_MODE_MIXED

    env.globals["FEEDBACK_LEVEL_FULL"] = FEEDBACK_LEVEL_FULL
    env.globals["FEEDBACK_LEVEL_RESTRICTED"] = FEEDBACK_LEVEL_RESTRICTED

    env.filters["all"] = all_
    env.filters["any"] = any_
    env.filters["dictselect"] = dictselect
    env.filters["make_timestamp"] = make_timestamp

    env.tests["contains"] = lambda s, p: p in s
    env.tests["endswith"] = lambda s, p: s.endswith(p)

    env.tests["today"] = today


# TODO When dropping py2, let the arguments be `env, *, dataset` in
# order to force the users to pass the dataset as a keyword argument.
@environmentfunction
def safe_get_task_type(env, dataset):
    try:
        return dataset.task_type_object
    # The task type's constructor is called, which may raise any
    # arbitrary exception, hence we stay as general as possible.
    except Exception as err:
        return env.undefined("TaskType not found: %s" % err)


# TODO When dropping py2, let the arguments be `env, *, dataset` in
# order to force the users to pass the dataset as a keyword argument.
@environmentfunction
def safe_get_score_type(env, dataset):
    try:
        return dataset.score_type_object
    # The score type's constructor is called, which may raise any
    # arbitrary exception, hence we stay as general as possible.
    except Exception as err:
        return env.undefined("ScoreType not found: %s" % err)


def instrument_cms_toolbox(env):
    env.globals["get_task_type"] = safe_get_task_type
    env.globals["get_score_type"] = safe_get_score_type

    env.globals["get_mimetype_for_file_name"] = get_type_for_file_name
    env.globals["get_name_for_mimetype"] = get_name_for_type
    env.globals["get_icon_for_mimetype"] = get_icon_for_type

    env.filters["to_language"] = get_language


@contextfilter
def format_datetime(ctx, dt):
    translation = ctx.get("translation", DEFAULT_TRANSLATION)
    timezone = ctx.get("timezone", local_tz)
    return translation.format_datetime(dt, timezone)


@contextfilter
def format_time(ctx, dt):
    translation = ctx.get("translation", DEFAULT_TRANSLATION)
    timezone = ctx.get("timezone", local_tz)
    return translation.format_time(dt, timezone)


@contextfilter
def format_datetime_smart(ctx, dt):
    translation = ctx.get("translation", DEFAULT_TRANSLATION)
    now = ctx.get("now", make_datetime())
    timezone = ctx.get("timezone", local_tz)
    return translation.format_datetime_smart(dt, now, timezone)


@contextfilter
def format_timedelta(ctx, td):
    translation = ctx.get("translation", DEFAULT_TRANSLATION)
    return translation.format_timedelta(td)


@contextfilter
def format_duration(ctx, d, length="short"):
    translation = ctx.get("translation", DEFAULT_TRANSLATION)
    return translation.format_duration(d, length)


@contextfilter
def format_size(ctx, s):
    translation = ctx.get("translation", DEFAULT_TRANSLATION)
    return translation.format_size(s)


@contextfilter
def format_decimal(ctx, n):
    translation = ctx.get("translation", DEFAULT_TRANSLATION)
    return translation.format_decimal(n)


@contextfilter
def format_locale(ctx, n):
    translation = ctx.get("translation", DEFAULT_TRANSLATION)
    return translation.format_locale(n)


@contextfilter
def wrapped_format_status_text(ctx, status_text):
    translation = ctx.get("translation", DEFAULT_TRANSLATION)
    return format_status_text(status_text, translation=translation)


def instrument_formatting_toolbox(env):
    env.filters["format_datetime"] = format_datetime
    env.filters["format_time"] = format_time
    env.filters["format_datetime_smart"] = format_datetime_smart
    env.filters["format_timedelta"] = format_timedelta
    env.filters["format_duration"] = format_duration
    env.filters["format_size"] = format_size
    env.filters["format_decimal"] = format_decimal
    env.filters["format_locale"] = format_locale

    env.filters["format_status_text"] = wrapped_format_status_text


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
    auto_reload=False,
    # Allow the use of {% trans %} tags to localize strings.
    extensions=['jinja2.ext.i18n'])
# This compresses all leading/trailing whitespace and line breaks of
# internationalized messages when translating and extracting them.
GLOBAL_ENVIRONMENT.policies['ext.i18n.trimmed'] = True


instrument_generic_toolbox(GLOBAL_ENVIRONMENT)
instrument_cms_toolbox(GLOBAL_ENVIRONMENT)
instrument_formatting_toolbox(GLOBAL_ENVIRONMENT)
