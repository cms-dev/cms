#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2015 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2017 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
# Copyright © 2016 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2016 Amir Keivan Mohtashami <akmohtashami97@gmail.com>
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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *
from future.builtins import *

import copy
import math
from future.moves.urllib.parse import quote

from cmscommon.datetime import utc
from cms.locale import DEFAULT_TRANSLATION


# Dummy functions to mark strings for translation: N_ is a dummy for
# gettext/_ and Nn_ is a dummy for ngettext/n_ (for plural forms).
def N_(msgid):
    pass


# Some strings in templates that for some reason don't get included in cms.pot.
N_("loading...")
N_("unknown")


def format_datetime(dt, timezone, translation=DEFAULT_TRANSLATION):
    """Return the date and time of dt formatted as per locale.

    dt (datetime): a datetime object.
    timezone (tzinfo): the timezone the output should be in.
    translation (Translation): the translation to use.

    return (str): the date and time of dt, formatted using the given
        locale.

    """
    return translation.format_datetime(dt, tzinfo=timezone)


def format_time(dt, timezone, translation=DEFAULT_TRANSLATION):
    """Return the time of dt formatted according to the given locale.

    dt (datetime): a datetime object.
    timezone (tzinfo): the timezone the output should be in.
    translation (Translation): the translation to use.

    return (str): the time of dt, formatted using the given locale.

    """
    return translation.format_time(dt, tzinfo=timezone)


def format_datetime_smart(dt, now, timezone, translation=DEFAULT_TRANSLATION):
    """Return dt formatted as '[date] time'.

    Date is present in the output if it is not today.

    dt (datetime): a datetime object to format.
    now (datetime): a datetime object representing the moment in time
        at which the previous parameter (dt) is being formatted.
    timezone (tzinfo): the timezone the output should be in.
    translation (Translation): the translation to use.

    return (str): the [date and] time of dt, formatted using the given
        locale.

    """
    dt_date = dt.replace(tzinfo=utc).astimezone(timezone).date()
    now_date = now.replace(tzinfo=utc).astimezone(timezone).date()
    if dt_date == now_date:
        return format_time(dt, timezone, translation)
    else:
        return format_datetime(dt, timezone, translation)


SECONDS_PER_HOUR = 3600
SECONDS_PER_MINUTE = 60


def format_timedelta(td, translation=DEFAULT_TRANSLATION):
    """Return the timedelta formatted to high precision.

    The result will be formatted as 'A days, B hours, C minutes and D
    seconds', with components that would have a zero value removed. The
    number of seconds has fractional digits, without trailing zeros.
    Unlike Babel's built-in format_timedelta, no approximation or
    rounding is performed.

    td (timedelta): a timedelta.
    translation (Translation): the translation to use.

    return (string): the formatted timedelta.

    """
    td = abs(td)

    res = []

    if td.days > 0:
        res.append(translation.format_unit(td.days, "duration-day"))

    secs = td.seconds
    if secs >= SECONDS_PER_HOUR:
        res.append(translation.format_unit(secs // SECONDS_PER_HOUR,
                                           "duration-hour"))
        secs %= SECONDS_PER_HOUR
    if secs >= SECONDS_PER_MINUTE:
        res.append(translation.format_unit(secs // SECONDS_PER_MINUTE,
                                           "duration-minute"))
        secs %= SECONDS_PER_MINUTE
    if secs > 0:
        res.append(translation.format_unit(secs, "duration-second"))

    if len(res) == 0:
        res.append(translation.format_unit(0, "duration-second"))

    return translation.format_list(res)


def format_duration(d, length="short", translation=DEFAULT_TRANSLATION):
    """Format a duration in seconds.

    Format the duration, usually of an operation performed in the
    sandbox (compilation, evaluation, ...), given as a number of
    seconds, always using a millisecond precision.

    d (float): a duration, as a number of seconds.
    translation (Translation): the translation to use.

    returns (str): the formatted duration.

    """
    d = abs(d)

    f = copy.copy(translation.locale.decimal_formats[None])
    f.frac_prec = (3, 3)
    return translation.format_unit(d, "duration-second",
                                   length=length, format=f)


PREFIX_FACTOR = 1000
SIZE_UNITS = ["byte", "kilobyte", "megabyte", "gigabyte", "terabyte"]


def format_size(n, translation=DEFAULT_TRANSLATION):
    """Format the given number of bytes.

    Format the size of a file, a memory allocation, etc. which is given
    as a number of bytes. Use the most appropriate unit, from bytes up
    to terabytes. Always use three significant digits, except when this
    would mean:
    - rounding the integral part (happens only for > 1000 terabytes),
      in which case use more than three;
    - showing sub-byte values (happens only for < 100 bytes), in which
      case use less than three.

    n (int): a size, as number of bytes.
    translation (Translation): the translation to use.

    return (str): the formatted size.

    """
    n = abs(n)

    if n < PREFIX_FACTOR:
        return translation.format_unit(round(n), "digital-%s" % SIZE_UNITS[0],
                                       length="short")
    for unit in SIZE_UNITS[1:]:
        n /= PREFIX_FACTOR
        if n < PREFIX_FACTOR:
            f = copy.copy(translation.locale.decimal_formats[None])
            d = max(int(math.ceil(math.log10(PREFIX_FACTOR / n))) - 1, 0)
            f.frac_prec = (d, d)
            return translation.format_unit(n, "digital-%s" % unit,
                                           length="short", format=f)
    return translation.format_unit(round(n), "digital-%s" % SIZE_UNITS[-1],
                                   length="short")


def format_decimal(n, translation=DEFAULT_TRANSLATION):
    """Format a (possibly decimal) number

    n (float): the number to format.
    translation (Translation): the translation to use.

    returns (str): the formatted number.

    """
    return translation.format_decimal(n)


def format_token_rules(tokens, t_type=None, translation=DEFAULT_TRANSLATION):
    """Return a human-readable string describing the given token rules

    tokens (dict): all the token rules (as seen in Task or Contest),
        without the "token_" prefix.
    t_type (string|None): the type of tokens the string should refer to
        (can be "contest" to mean contest-tokens, "task" to mean
        task-tokens, any other value to mean normal tokens).
    translation (Translation): the translation to use.

    return (unicode): localized string describing the rules.

    """
    _ = translation.gettext
    n_ = translation.ngettext

    if t_type == "contest":
        tokens["type_s"] = _("contest-token")
        tokens["type_pl"] = _("contest-tokens")
    elif t_type == "task":
        tokens["type_s"] = _("task-token")
        tokens["type_pl"] = _("task-tokens")
    else:
        tokens["type_s"] = _("token")
        tokens["type_pl"] = _("tokens")

    tokens["min_interval"] = tokens["min_interval"].total_seconds()
    tokens["gen_interval"] = tokens["gen_interval"].total_seconds() / 60

    result = ""

    if tokens["mode"] == "disabled":
        # This message will only be shown on tasks in case of a mixed
        # modes scenario.
        result += \
            _("You don't have %(type_pl)s available for this task.") % tokens
    elif tokens["mode"] == "infinite":
        # This message will only be shown on tasks in case of a mixed
        # modes scenario.
        result += \
            _("You have an infinite number of %(type_pl)s "
              "for this task.") % tokens
    else:
        if tokens['gen_initial'] == 0:
            result += _("You start with no %(type_pl)s.") % tokens
        else:
            result += n_("You start with one %(type_s)s.",
                         "You start with %(gen_initial)d %(type_pl)s.",
                         tokens['gen_initial'] == 1) % tokens

        result += " "

        if tokens['gen_number'] > 0:
            result += n_("Every minute ",
                         "Every %(gen_interval)g minutes ",
                         tokens['gen_interval']) % tokens
            if tokens['gen_max'] is not None:
                result += n_("you get another %(type_s)s, ",
                             "you get %(gen_number)d other %(type_pl)s, ",
                             tokens['gen_number']) % tokens
                result += n_("up to a maximum of one %(type_s)s.",
                             "up to a maximum of %(gen_max)d %(type_pl)s.",
                             tokens['gen_max']) % tokens
            else:
                result += n_("you get another %(type_s)s.",
                             "you get %(gen_number)d other %(type_pl)s.",
                             tokens['gen_number']) % tokens
        else:
            result += _("You don't get other %(type_pl)s.") % tokens

        result += " "

        if tokens['min_interval'] > 0 and tokens['max_number'] is not None:
            result += n_("You can use a %(type_s)s every second ",
                         "You can use a %(type_s)s every %(min_interval)g "
                         "seconds ",
                         tokens['min_interval']) % tokens
            result += n_("and no more than one %(type_s)s in total.",
                         "and no more than %(max_number)d %(type_pl)s in "
                         "total.",
                         tokens['max_number']) % tokens
        elif tokens['min_interval'] > 0:
            result += n_("You can use a %(type_s)s every second.",
                         "You can use a %(type_s)s every %(min_interval)g "
                         "seconds.",
                         tokens['min_interval']) % tokens
        elif tokens['max_number'] is not None:
            result += n_("You can use no more than one %(type_s)s in total.",
                         "You can use no more than %(max_number)d %(type_pl)s "
                         "in total.",
                         tokens['max_number']) % tokens
        else:
            result += \
                _("You have no limitations on how you use them.") % tokens

    return result


def get_score_class(score, max_score):
    """Return a CSS class to visually represent the score/max_score

    score (float): the score of the submission.
    max_score (float): maximum score.

    return (unicode): class name

    """
    if score <= 0:
        return "score_0"
    elif score >= max_score:
        return "score_100"
    else:
        return "score_0_100"


def encode_for_url(url_fragment):
    """Return the string encoded safely for becoming a url fragment.

    In particular, this means encoding it to UTF-8 and then
    percent-encoding it.

    url_fragment(unicode): the string to be encoded.

    return (str): the encoded string.

    """
    return quote(url_fragment.encode('utf-8'), safe='')
