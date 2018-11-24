#!/usr/bin/env python3

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

from cms import TOKEN_MODE_DISABLED, TOKEN_MODE_FINITE, TOKEN_MODE_INFINITE
from cms.locale import DEFAULT_TRANSLATION


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

    if tokens["mode"] == TOKEN_MODE_DISABLED:
        # This message will only be shown on tasks in case of a mixed
        # modes scenario.
        result += \
            _("You don't have %(type_pl)s available for this task.") % tokens
    elif tokens["mode"] == TOKEN_MODE_INFINITE:
        # This message will only be shown on tasks in case of a mixed
        # modes scenario.
        result += \
            _("You have an infinite number of %(type_pl)s "
              "for this task.") % tokens
    elif tokens["mode"] == TOKEN_MODE_FINITE:
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
    else:
        raise ValueError("Unexpected token mode '%s'" % tokens["mode"])

    return result


def get_score_class(score, max_score, score_precision):
    """Return a CSS class to visually represent the score/max_score

    score (float): the score of the submission.
    max_score (float): maximum score.

    return (unicode): class name

    """
    score = round(score, score_precision)
    max_score = round(max_score, score_precision)
    if score <= 0:
        return "score_0"
    elif score >= max_score:
        return "score_100"
    else:
        return "score_0_100"
