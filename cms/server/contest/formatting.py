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

from future.moves.urllib.parse import quote

import tornado.locale

from cmscommon.datetime import make_datetime, utc
from cms.locale import locale_format


# Dummy functions to mark strings for translation: N_ is a dummy for
# gettext/_ and Nn_ is a dummy for ngettext/n_ (for plural forms).
def N_(msgid):
    pass


def Nn_(msgid1, msgid2, c):
    pass


# Some strings in templates that for some reason don't get included in cms.pot.
N_("loading...")
N_("unknown")

# Other messages used in this file.
Nn_("%d second", "%d seconds", 0)
Nn_("%d minute", "%d minutes", 0)
Nn_("%d hour", "%d hours", 0)
Nn_("%d day", "%d days", 0)


def format_datetime(dt, timezone, locale=None):
    """Return the date and time of dt formatted as per locale.

    dt (datetime): a datetime object.
    timezone (tzinfo): the timezone the output should be in.

    return (str): the date and time of dt, formatted using the given
        locale.

    """
    if locale is None:
        locale = tornado.locale.get()

    _ = locale.translate

    # convert dt from UTC to local time
    dt = dt.replace(tzinfo=utc).astimezone(timezone)

    return dt.strftime(_("%Y-%m-%d %H:%M:%S"))


def format_time(dt, timezone, locale=None):
    """Return the time of dt formatted according to the given locale.

    dt (datetime): a datetime object.
    timezone (tzinfo): the timezone the output should be in.

    return (str): the time of dt, formatted using the given locale.

    """
    if locale is None:
        locale = tornado.locale.get()

    _ = locale.translate

    # convert dt from UTC to local time
    dt = dt.replace(tzinfo=utc).astimezone(timezone)

    return dt.strftime(_("%H:%M:%S"))


def format_datetime_smart(dt, timezone, locale=None):
    """Return dt formatted as '[date] time'.

    Date is present in the output if it is not today.

    dt (datetime): a datetime object.
    timezone (tzinfo): the timezone the output should be in.

    return (str): the [date and] time of dt, formatted using the given
        locale.

    """
    if locale is None:
        locale = tornado.locale.get()

    _ = locale.translate

    # convert dt and 'now' from UTC to local time
    dt = dt.replace(tzinfo=utc).astimezone(timezone)
    now = make_datetime().replace(tzinfo=utc).astimezone(timezone)

    if dt.date() == now.date():
        return dt.strftime(_("%H:%M:%S"))
    else:
        return dt.strftime(_("%Y-%m-%d %H:%M:%S"))


def format_amount_of_time(seconds, precision=2, locale=None):
    """Return the number of seconds formatted 'X days, Y hours, ...'

    The time units that will be used are days, hours, minutes, seconds.
    Only the first "precision" units will be output. If they're not
    enough, a "more than ..." will be prefixed (non-positive precision
    means infinite).

    seconds (int): the length of the amount of time in seconds.
    precision (int): see above
    locale (Locale|None): the locale to be used, or None for the
        default.

    return (string): seconds formatted as above.

    """
    seconds = abs(int(seconds))

    if locale is None:
        locale = tornado.locale.get()

    _ = locale.translate
    n_ = locale.translate

    if seconds == 0:
        return n_("%d second", "%d seconds", 0) % 0

    units = [(("%d day", "%d days"), 60 * 60 * 24),
             (("%d hour", "%d hours"), 60 * 60),
             (("%d minute", "%d minutes"), 60),
             (("%d second", "%d seconds"), 1)]

    ret = list()
    counter = 0

    for name, length in units:
        tmp = seconds // length
        seconds %= length
        if tmp == 0:
            continue
        else:
            ret.append(_(name[0], name[1], tmp) % tmp)
        counter += 1
        if counter == precision:
            break

    if len(ret) == 1:
        ret = ret[0]
    else:
        ret = _("%s and %s") % (", ".join(ret[:-1]), ret[-1])

    if seconds > 0:
        ret = _("more than %s") % ret

    return ret


UNITS = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB']
DIMS = list(1024 ** x for x in range(9))


def format_size(n, _=lambda s: s):
    """Format the given number of bytes.

    Return a size, given as a number of bytes, properly formatted
    using the most appropriate size unit. Always use three
    significant digits.

    """
    if n == 0:
        return '0 B'

    # Use the last unit that's smaller than n
    try:
        unit_index = next(i for i, x in enumerate(DIMS) if n < x) - 1
    except StopIteration:
        unit_index = -1
    n = n / DIMS[unit_index]

    if n < 10:
        d = 2
    elif n < 100:
        d = 1
    else:
        d = 0
    return locale_format(_, "{0:g} {1}", round(n, d), UNITS[unit_index])


def format_token_rules(tokens, t_type=None, locale=None):
    """Return a human-readable string describing the given token rules

    tokens (dict): all the token rules (as seen in Task or Contest),
        without the "token_" prefix.
    t_type (string|None): the type of tokens the string should refer to
        (can be "contest" to mean contest-tokens, "task" to mean
        task-tokens, any other value to mean normal tokens).
    locale (Locale|NullTranslation|None): the locale to be used (None
        for the default).

    return (unicode): localized string describing the rules.

    """
    if locale is None:
        locale = tornado.locale.get()

    _ = locale.translate
    n_ = locale.translate

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
