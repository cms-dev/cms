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
# Copyright © 2018 Edoardo Morassutto <edoardo.morassutto@gmail.com>
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

from collections.abc import Iterable
import copy
import logging
import math

import babel.core
import babel.dates
import babel.lists
import babel.numbers
import babel.support
import babel.units
import importlib.resources

from cmscommon.datetime import utc
from cmscommon.mimetypes import get_name_for_type
from datetime import datetime, tzinfo, timedelta


logger = logging.getLogger(__name__)


def N_(msgid: str):
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

    @property
    def identifier(self) -> str:
        return babel.core.get_locale_identifier(
            (self.locale.language, self.locale.territory,
             self.locale.script, self.locale.variant), sep="-")

    @property
    def name(self) -> str:
        return self.locale.display_name

    def gettext(self, msgid: str) -> str:
        return self.translation.gettext(msgid)

    def ngettext(self, msgid1: str, msgid2: str, n: int) -> str:
        return self.translation.ngettext(msgid1, msgid2, n)

    def format_datetime(self, dt: datetime, timezone: tzinfo) -> str:
        """Return the date and time of dt.

        dt: a datetime.
        timezone: the timezone the output should be in.

        return: the formatted date and time of the datetime.

        """
        return babel.dates.format_datetime(dt, tzinfo=timezone,
                                           locale=self.locale)

    def format_time(self, dt: datetime, timezone: tzinfo) -> str:
        """Return the time of dt.

        dt: a datetime.
        timezone: the timezone the output should be in.

        return: the formatted time of the datetime.

        """
        return babel.dates.format_time(dt, tzinfo=timezone, locale=self.locale)

    def format_datetime_smart(
        self, dt: datetime, now: datetime, timezone: tzinfo
    ) -> str:
        """Return dt formatted as '[date] time'.

        Date is present in the output if it is not today.

        dt: a datetime.
        now: a datetime representing the moment in time at
            which the previous parameter (dt) is being formatted.
        timezone: the timezone the output should be in.

        return: the formatted [date and] time of the datetime.

        """
        dt_date = dt.replace(tzinfo=utc).astimezone(timezone).date()
        now_date = now.replace(tzinfo=utc).astimezone(timezone).date()
        if dt_date == now_date:
            return self.format_time(dt, timezone)
        else:
            return self.format_datetime(dt, timezone)

    SECONDS_PER_HOUR = 60 * 60
    SECONDS_PER_MINUTE = 60

    def format_timedelta(self, td: timedelta) -> str:
        """Return the timedelta formatted to high precision.

        The result will be formatted as 'A days, B hours, C minutes and D
        seconds', with components that would have a zero value removed. The
        number of seconds has fractional digits, without trailing zeros.
        Unlike Babel's built-in format_timedelta, no approximation or
        rounding is performed.

        td: a timedelta.

        return: the formatted timedelta.

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

    def format_duration(self, d: float, length: str = "short") -> str:
        """Format a duration in seconds.

        Format the duration, usually of an operation performed in the
        sandbox (compilation, evaluation, ...), given as a number of
        seconds, always using a millisecond precision.

        d: a duration, as a number of seconds.

        returns: the formatted duration.

        """
        d = abs(d)

        f = copy.copy(self.locale.decimal_formats[None])
        f.frac_prec = (3, 3)
        return babel.units.format_unit(
            d, "duration-second", length=length, format=f, locale=self.locale)

    PREFIX_FACTOR = 1024
    SIZE_UNITS = [None, N_("%s KiB"), N_("%s MiB"), N_("%s GiB"), N_("%s TiB")]

    def format_size(self, n: int) -> str:
        """Format the given number of bytes.

        Format the size of a file, a memory allocation, etc. which is
        given as a number of bytes. Use the most appropriate unit, from
        bytes up to tebibytes. Always show the entire integral part plus
        as many fractional digits as needed to reach at least three
        significant digits in total, except when this would mean showing
        sub-byte values (happens only for less than 100 bytes).

        n: a size, as number of bytes.

        return: the formatted size.

        """
        n = abs(n)

        if n < self.PREFIX_FACTOR:
            return babel.units.format_unit(
                round(n), "digital-byte", locale=self.locale)
        for unit in self.SIZE_UNITS[1:]:
            n /= self.PREFIX_FACTOR
            if n < self.PREFIX_FACTOR:
                f = copy.copy(self.locale.decimal_formats[None])
                # if 1000 <= n < 1024 d can be negative, cap to 0 decimals
                d = max(0, 2 - math.floor(math.log10(n)))
                f.frac_prec = (d, d)
                return (self.gettext(unit)
                        % babel.numbers.format_decimal(n, format=f,
                                                       locale=self.locale))
        return (self.gettext(self.SIZE_UNITS[-1])
                % babel.numbers.format_decimal(round(n), locale=self.locale))

    def format_decimal(self, n: float) -> str:
        """Format a (possibly decimal) number

        n: the number to format.

        returns: the formatted number.

        """
        return babel.numbers.format_decimal(n, locale=self.locale)

    def format_locale(self, code: str) -> str:
        """Format a locale identifier.

        Return a natural language description of the locale specified
        by the given identifier, e.g., "American English" for "en_US".

        code: a locale identifier, consisting of identifiers for
            the language (as for ISO 639), the script, the territory
            (as for ISO 3166) and the variant, joined by underscores,
            with undefined components suppressed.

        return: the formatted locale description.

        """
        try:
            return babel.core.Locale.parse(code).get_display_name(self.locale)
        except (ValueError, babel.core.UnknownLocaleError):
            return code

    def translate_mimetype(self, mimetype: str) -> str:
        lang_code = self.identifier
        alt_lang_code = babel.core.get_locale_identifier(
            (self.locale.language, self.locale.territory), sep="_"
        )
        return get_name_for_type(mimetype, lang_code, alt_lang_code)


DEFAULT_TRANSLATION = Translation("en")


def get_translations() -> dict[str, Translation]:
    """Return the translations for all the languages we support.

    Search for the message catalogs that were installed and load them.

    return: for each language its message catalog

    """
    result = {DEFAULT_TRANSLATION.identifier: DEFAULT_TRANSLATION}

    try:
        locale_pkg = importlib.resources.files("cms.locale")
        for lang_dir in locale_pkg.iterdir():
            if lang_dir.is_dir() and not lang_dir.name.startswith('_'):
                lang_code = lang_dir.name
                try:
                    mofile_path = lang_dir / "LC_MESSAGES" / "cms.mo"
                    with mofile_path.open("rb") as f:
                        t = Translation(lang_code, f)
                        logger.info("Found translation %s", t.identifier)
                        result[t.identifier] = t
                except Exception:
                    logger.warning(
                        "Failed to load translation for %s",
                        lang_code,
                        exc_info=True,
                    )
    except Exception:
        logger.warning("Failed to scan locale directory", exc_info=True)

    return result


def filter_language_codes(lang_codes: list[str], prefixes: list[str]) -> list[str]:
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

    lang_codes: list of language codes
    prefixes: whitelist of prefix

    return: the codes that match one of the prefixes

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

    if len(parsed_filtered_lang_codes) == 0:
        logger.warning("No allowed locale matches any installed one. "
                       "Resorting to %s.", DEFAULT_TRANSLATION.identifier)
        return [DEFAULT_TRANSLATION.identifier]

    filtered_lang_codes = list()
    for parsed_lang_code in parsed_filtered_lang_codes:
        lang_code = babel.core.get_locale_identifier(parsed_lang_code, sep="-")
        filtered_lang_codes.append(lang_code)

    return filtered_lang_codes


def choose_language_code(
    preferred: Iterable[str], available: Iterable[str]
) -> str | None:
    return babel.core.negotiate_locale(preferred, available, sep="-")
