#!/usr/bin/env python3

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

import copy
import logging
import math
import os

import babel.core
import babel.dates
import babel.lists
import babel.numbers
import babel.support
import babel.units
import pkg_resources

from cms import config
from cmscommon.datetime import utc


logger = logging.getLogger(__name__)


def N_(msgid):
    return msgid


class Translation:
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
        self.mimetype_translation = babel.support.Translations.load(
            os.path.join(config.shared_mime_info_prefix, "share", "locale"),
            [self.locale], "shared-mime-info")

    @property
    def identifier(self):
        return babel.core.get_locale_identifier(
            (self.locale.language, self.locale.territory,
             self.locale.script, self.locale.variant), sep="-")

    @property
    def name(self):
        return self.locale.display_name

    def gettext(self, msgid):
        return self.translation.gettext(msgid)

    def ngettext(self, msgid1, msgid2, n):
        return self.translation.ngettext(msgid1, msgid2, n)

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

    SECONDS_PER_HOUR = 60 * 60
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

        if not res:
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
        return babel.units.format_unit(
            d, "duration-second", length=length, format=f, locale=self.locale)

    PREFIX_FACTOR = 1024
    SIZE_UNITS = [None, N_("%s KiB"), N_("%s MiB"), N_("%s GiB"), N_("%s TiB")]

    def format_size(self, n):
        """Format the given number of bytes.

        Format the size of a file, a memory allocation, etc. which is
        given as a number of bytes. Use the most appropriate unit, from
        bytes up to tebibytes. Always show the entire integral part plus
        as many fractional digits as needed to reach at least three
        significant digits in total, except when this would mean showing
        sub-byte values (happens only for less than 100 bytes).

        n (int): a size, as number of bytes.

        return (str): the formatted size.

        """
        n = abs(n)

        if n < self.PREFIX_FACTOR:
            return babel.units.format_unit(
                round(n), "digital-byte", locale=self.locale)
        for unit in self.SIZE_UNITS[1:]:
            n /= self.PREFIX_FACTOR
            if n < self.PREFIX_FACTOR:
                f = copy.copy(self.locale.decimal_formats[None])
                # We need int because floor returns a float in py2.
                d = int(2 - math.floor(math.log10(n)))
                f.frac_prec = (d, d)
                return (self.gettext(unit)
                        % babel.numbers.format_decimal(n, format=f,
                                                       locale=self.locale))
        return (self.gettext(self.SIZE_UNITS[-1])
                % babel.numbers.format_decimal(round(n), locale=self.locale))

    def format_decimal(self, n):
        """Format a (possibly decimal) number

        n (float): the number to format.

        returns (str): the formatted number.

        """
        return babel.numbers.format_decimal(n, locale=self.locale)

    def format_locale(self, code):
        """Format a locale identifier.

        Return a natural language description of the locale specified
        by the given identifier, e.g., "American English" for "en_US".

        code (str): a locale identifier, consisting of identifiers for
            the language (as for ISO 639), the script, the territory
            (as for ISO 3166) and the variant, joined by underscores,
            with undefined components suppressed.

        return (str): the formatted locale description.

        """
        try:
            return babel.core.Locale.parse(code).get_display_name(self.locale)
        except (ValueError, babel.core.UnknownLocaleError):
            return code

    def translate_mimetype(self, mimetype):
        return self.mimetype_translation.gettext(mimetype)


DEFAULT_TRANSLATION = Translation("en")


def get_translations():
    """Return the translations for all the languages we support.

    Search for the message catalogs that were installed and load them.

    return ({string: Translation}): for each language its message
        catalog

    """
    result = {DEFAULT_TRANSLATION.identifier: DEFAULT_TRANSLATION}

    for lang_code in sorted(pkg_resources.resource_listdir("cms.locale", "")):
        mofile_path = os.path.join(lang_code, "LC_MESSAGES", "cms.mo")
        if pkg_resources.resource_exists("cms.locale", mofile_path):
            with pkg_resources.resource_stream("cms.locale", mofile_path) as f:
                t = Translation(lang_code, f)
                logger.info("Found translation %s", t.identifier)
                result[t.identifier] = t

    return result


def filter_language_codes(lang_codes, prefixes):
    """Keep only codes that begin with one of the given prefixes.

    Filter the given list of language codes (i.e., locale identifiers)
    and return only those that are more specific than any of the given
    allowed prefixes. By "more specific" it is meant that there exists
    a prefix that, for each of the four components of the language code
    (namely language, territory, script and variant), either matches
    the component or leaves it unspecified. This way, for example, the
    prefix "en" matches the language codes "en", "en_US", etc. It's the
    same approach promoted by HTTP in its Accept header parsing rules.
    The returned language codes will be in the same relative order as
    they were given.

    lang_codes ([string]): list of language codes
    prefixes ([string]): whitelist of prefix

    return ([string]): the codes that match one of the prefixes

    """
    parsed_lang_codes = list()
    for lang_code in lang_codes:
        try:
            parsed_lang_code = babel.core.parse_locale(lang_code, sep="-")
        except ValueError:
            logger.error("Invalid installed locale: %s", lang_code)
        else:
            parsed_lang_codes.append(parsed_lang_code)

    parsed_prefixes = list()
    for prefix in prefixes:
        try:
            parsed_prefix = babel.core.parse_locale(prefix, sep="-")
        except ValueError:
            logger.error("Invalid allowed locale: %s", prefix)
        else:
            parsed_prefixes.append(parsed_prefix)

    parsed_filtered_lang_codes = list()
    for parsed_lang_code in parsed_lang_codes:
        for parsed_prefix in parsed_prefixes:
            # parsed_lang_code and parsed_prefix are tuples, whose
            # components are language, territory, script and variant.
            # All the components of lang_code need to match the
            # corresponding ones in prefix. An undefined component in
            # prefix acts like a wildcard.
            if all(p_c is None or lc_c == p_c
                   for lc_c, p_c in zip(parsed_lang_code, parsed_prefix)):
                parsed_filtered_lang_codes.append(parsed_lang_code)
                break

    if not parsed_filtered_lang_codes:
        logger.warning("No allowed locale matches any installed one. "
                       "Resorting to %s.", DEFAULT_TRANSLATION.identifier)
        return [DEFAULT_TRANSLATION.identifier]

    filtered_lang_codes = list()
    for parsed_lang_code in parsed_filtered_lang_codes:
        lang_code = babel.core.get_locale_identifier(parsed_lang_code, sep="-")
        filtered_lang_codes.append(lang_code)

    return filtered_lang_codes


def choose_language_code(preferred, available):
    return babel.core.negotiate_locale(preferred, available, sep="-")
