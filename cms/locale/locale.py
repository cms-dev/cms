#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2015 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2015 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
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

"""Manage translations and localization stuff.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import copy

import math
from future.builtins.disabled import *
from future.builtins import *
import six

import pkg_resources
import gettext
import logging
import os

import babel.core
import babel.dates
import babel.lists
import babel.numbers
import babel.support
import babel.units

from cms import config
from cmscommon.datetime import utc


logger = logging.getLogger(__name__)


def get_system_translations(lang):
    """Return the translation catalogs for our dependencies.

    Some strings we use come from external software (e.g. language and
    country names, mimetype descriptions, etc.) and their translations
    are thus provided by these packages' catalogs. This function has to
    return the gettext.*Translations classes that translate a string
    according to these message catalogs.

    lang (string): the language we want translations for

    return ([gettext.NullTranslations]): the translation catalogs

    """
    iso_639_locale = gettext.translation(
        "iso_639",
        os.path.join(config.iso_codes_prefix, "share", "locale"),
        [lang],
        fallback=True)
    iso_3166_locale = gettext.translation(
        "iso_3166",
        os.path.join(config.iso_codes_prefix, "share", "locale"),
        [lang],
        fallback=True)
    shared_mime_info_locale = gettext.translation(
        "shared-mime-info",
        os.path.join(config.shared_mime_info_prefix, "share", "locale"),
        [lang],
        fallback=True)

    return [iso_639_locale, iso_3166_locale, shared_mime_info_locale]


class Translation(object):
    """A shim that bundles all sources of translations for a language

    This class is a thin wrapper that collects all message catalogs and
    other pieces of information about a locale and centralizes access
    to them providing a more object-oriented interface.

    """

    def __init__(self, lang_code, mofile=None):
        self.locale = babel.core.Locale.parse(lang_code)
        if mofile is not None:
            self.translation = babel.support.Translations(mofile, domain="cms")
        else:
            self.translation = babel.support.NullTranslations()
        for sys_translation in get_system_translations(lang_code):
            self.translation.add_fallback(sys_translation)

    @property
    def identifier(self):
        return babel.core.get_locale_identifier(
            (self.locale.language, self.locale.territory,
             self.locale.script, self.locale.variant))

    @property
    def name(self):
        return self.locale.display_name

    def gettext(self, msgid):
        if six.PY3:
            return self.translation.gettext(msgid)
        else:
            return self.translation.ugettext(msgid)

    def ngettext(self, msgid1, msgid2, n):
        if six.PY3:
            return self.translation.ngettext(msgid1, msgid2, n)
        else:
            return self.translation.ungettext(msgid1, msgid2, n)

    def format_datetime(self, dt, timezone):
        """Return the date and time of dt.

        dt (datetime): a datetime.
        timezone (tzinfo): the timezone the output should be in.

        return (str): the formatted date and time of the datetime.

        """
        return babel.dates.format_datetime(dt, tzinfo=timezone,
                                           locale=self.locale)

    def format_time(self, dt, timezone):
        """Return the time of dt.

        dt (datetime): a datetime.
        timezone (tzinfo): the timezone the output should be in.

        return (str): the formatted time of the datetime.

        """
        return babel.dates.format_time(dt, tzinfo=timezone, locale=self.locale)

    def format_datetime_smart(self, dt, now, timezone):
        """Return dt formatted as '[date] time'.

        Date is present in the output if it is not today.

        dt (datetime): a datetime.
        now (datetime): a datetime representing the moment in time at
            which the previous parameter (dt) is being formatted.
        timezone (tzinfo): the timezone the output should be in.

        return (str): the formatted [date and] time of the datetime.

        """
        dt_date = dt.replace(tzinfo=utc).astimezone(timezone).date()
        now_date = now.replace(tzinfo=utc).astimezone(timezone).date()
        if dt_date == now_date:
            return self.format_time(dt, timezone)
        else:
            return self.format_datetime(dt, timezone)

    SECONDS_PER_HOUR = 3600
    SECONDS_PER_MINUTE = 60

    def format_timedelta(self, td):
        """Return the timedelta formatted to high precision.

        The result will be formatted as 'A days, B hours, C minutes and D
        seconds', with components that would have a zero value removed. The
        number of seconds has fractional digits, without trailing zeros.
        Unlike Babel's built-in format_timedelta, no approximation or
        rounding is performed.

        td (timedelta): a timedelta.

        return (string): the formatted timedelta.

        """
        td = abs(td)

        res = []

        if td.days > 0:
            res.append(babel.units.format_unit(td.days, "duration-day",
                                               locale=self.locale))

        secs = td.seconds
        if secs >= self.SECONDS_PER_HOUR:
            res.append(babel.units.format_unit(secs // self.SECONDS_PER_HOUR,
                                               "duration-hour",
                                               locale=self.locale))
            secs %= self.SECONDS_PER_HOUR
        if secs >= self.SECONDS_PER_MINUTE:
            res.append(babel.units.format_unit(secs // self.SECONDS_PER_MINUTE,
                                               "duration-minute",
                                               locale=self.locale))
            secs %= self.SECONDS_PER_MINUTE
        if secs > 0:
            res.append(babel.units.format_unit(secs, "duration-second",
                                               locale=self.locale))

        if len(res) == 0:
            res.append(babel.units.format_unit(0, "duration-second",
                                               locale=self.locale))

        return babel.lists.format_list(res, locale=self.locale)

    def format_duration(self, d, length="short"):
        """Format a duration in seconds.

        Format the duration, usually of an operation performed in the
        sandbox (compilation, evaluation, ...), given as a number of
        seconds, always using a millisecond precision.

        d (float): a duration, as a number of seconds.

        returns (str): the formatted duration.

        """
        d = abs(d)

        f = copy.copy(self.locale.decimal_formats[None])
        f.frac_prec = (3, 3)
        return babel.units.format_unit(d, "duration-second",
                                       length=length, format=f, locale=self.locale)

    PREFIX_FACTOR = 1000
    SIZE_UNITS = ["byte", "kilobyte", "megabyte", "gigabyte", "terabyte"]

    def format_size(self, n):
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

        return (str): the formatted size.

        """
        n = abs(n)

        if n < self.PREFIX_FACTOR:
            return babel.units.format_unit(round(n),
                                           "digital-%s" % self.SIZE_UNITS[0],
                                           length="short", locale=self.locale)
        for unit in self.SIZE_UNITS[1:]:
            n /= self.PREFIX_FACTOR
            if n < self.PREFIX_FACTOR:
                f = copy.copy(self.locale.decimal_formats[None])
                d = max(int(math.ceil(math.log10(self.PREFIX_FACTOR / n))) - 1, 0)
                f.frac_prec = (d, d)
                return babel.units.format_unit(n, "digital-%s" % unit,
                                               length="short", format=f, locale=self.locale)
        return babel.units.format_unit(round(n), "digital-%s" % self.SIZE_UNITS[-1],
                                       length="short", locale=self.locale)

    def format_decimal(self, n):
        """Format a (possibly decimal) number

        n (float): the number to format.

        returns (str): the formatted number.

        """
        return babel.numbers.format_decimal(n, locale=self.locale)


DEFAULT_TRANSLATION = Translation("en")


def get_translations():
    """Return the translations for all the languages we support.

    Search for the message catalogs that were installed and load them.

    return ({string: Translation}): for each language its message
        catalog

    """
    result = {"en": DEFAULT_TRANSLATION}

    for lang_code in sorted(pkg_resources.resource_listdir("cms.locale", "")):
        mofile_path = os.path.join(lang_code, "LC_MESSAGES", "cms.mo")
        if pkg_resources.resource_exists("cms.locale", mofile_path):
            with pkg_resources.resource_stream("cms.locale", mofile_path) as f:
                t = Translation(lang_code, f)
                logger.info("Found translation %s", t.identifier)
                result[t.identifier] = t

    return result


def filter_language_codes(lang_codes, prefix_filter):
    """Keep only codes that begin with one of the given prefixes.

    lang_codes ([string]): list of language codes
    prefix_filter ([string]): whitelist of prefix

    return ([string]): the codes that match one of the prefixes

    """
    # TODO Be more fussy with prefix checking: validate strings
    # (match with "[A-Za-z]+(_[A-Za-z]+)*") and verify that the
    # prefix is on the underscores.
    useless = [prefix for prefix in prefix_filter
               if all(not lang_code.startswith(prefix)
                      for lang_code in lang_codes)]
    if useless:
        logger.warning("The following allowed localizations don't match any "
                       "installed one: %s", ",".join(useless))

    # We just check if a prefix of each language is allowed
    # because this way one can just type "en" to include also
    # "en_US" (and similar cases with other languages). It's
    # the same approach promoted by HTTP in its Accept header
    # parsing rules.
    # TODO Be more fussy with prefix checking: validate strings
    # (match with "[A-Za-z]+(_[A-Za-z]+)*") and verify that the
    # prefix is on the underscores.
    # It needs to maintain order of allowed_localizations(prefix_filter)
    lang_codes = [lang_code for prefix in prefix_filter
                  for lang_code in lang_codes
                  if lang_code.startswith(prefix)]

    if not lang_codes:
        logger.warning("No allowed localization matches any installed one."
                       "Resorting to en.")
        lang_codes = ["en"]

    return lang_codes
