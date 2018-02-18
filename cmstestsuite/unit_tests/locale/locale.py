#!/usr/bin/env python
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

"""Tests for CWS formatting functions.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *
from future.builtins import *

import unittest
from datetime import datetime, timedelta

import babel.dates

from cms.locale import Translation, DEFAULT_TRANSLATION


UTC = babel.dates.UTC
ROME = babel.dates.get_timezone("Europe/Rome")

ENGLISH = DEFAULT_TRANSLATION
FRENCH = Translation("fr")
HINDI = Translation("hi")
ITALIAN = Translation("it")
NORWEGIAN = Translation("no")


class TestFormatDatetime(unittest.TestCase):

    def test_utc(self):
        # UTC, in English
        self.assertEqual(
            ENGLISH.format_datetime(datetime(2018, 1, 1, 12, 34, 56),
                                    timezone=UTC),
            "Jan 1, 2018, 12:34:56 PM")

    def test_other_timezone_winter(self):
        # Other timezone, in winter (no DST).
        self.assertEqual(
            ENGLISH.format_datetime(datetime(2018, 1, 1, 12, 34, 56),
                                    timezone=ROME),
            "Jan 1, 2018, 1:34:56 PM")

    def test_other_timezone_summer(self):
        self.assertEqual(
            ENGLISH.format_datetime(datetime(2018, 7, 1, 12, 34, 56),
                                    timezone=ROME),
            "Jul 1, 2018, 2:34:56 PM")

    # As above, localized (use a language with a 24h clock and with a
    # different day/month/year order).

    def test_localized_utc(self):
        self.assertEqual(
            ITALIAN.format_datetime(datetime(2018, 1, 1, 12, 34, 56),
                                    timezone=UTC),
            "01 gen 2018, 12:34:56")

    def test_localized_other_timezone_winter(self):
        self.assertEqual(
            ITALIAN.format_datetime(datetime(2018, 1, 1, 12, 34, 56),
                                    timezone=ROME),
            "01 gen 2018, 13:34:56")

    def test_localized_other_timezone_summer(self):
        self.assertEqual(
            ITALIAN.format_datetime(datetime(2018, 7, 1, 12, 34, 56),
                                    timezone=ROME),
            "01 lug 2018, 14:34:56")


class TestFormatTime(unittest.TestCase):

    def test_utc(self):
        # UTC, in English
        self.assertEqual(ENGLISH.format_time(datetime(2018, 1, 1, 12, 34, 56),
                                             timezone=UTC),
                         "12:34:56 PM")

    def test_other_timezone_winter(self):
        # Other timezone, in winter (no DST).
        self.assertEqual(ENGLISH.format_time(datetime(2018, 1, 1, 12, 34, 56),
                                             timezone=ROME),
                         "1:34:56 PM")

    def test_other_timezone_in_summer(self):
        # Other timezone, in summer (DST).
        self.assertEqual(ENGLISH.format_time(datetime(2018, 7, 1, 12, 34, 56),
                                             timezone=ROME),
                         "2:34:56 PM")

    # As above, localized (use Norwegian as they use periods rather
    # than colons and have a 24h clock).

    def test_localized_utc(self):
        self.assertEqual(NORWEGIAN.format_time(datetime(2018, 1, 1, 12, 34, 56),
                                               timezone=UTC),
                         "12.34.56")

    def test_localized_other_timezone_winter(self):
        self.assertEqual(NORWEGIAN.format_time(datetime(2018, 1, 1, 12, 34, 56),
                                               timezone=ROME),
                         "13.34.56")

    def test_localized_other_timezone_summer(self):
        self.assertEqual(NORWEGIAN.format_time(datetime(2018, 7, 1, 12, 34, 56),
                                               timezone=ROME),
                         "14.34.56")


class TestFormatDatetimeSmart(unittest.TestCase):

    def test_utc(self):
        # UTC, in English
        self.assertEqual(
            ENGLISH.format_datetime_smart(datetime(2018, 1, 1, 12, 34, 56),
                                          datetime(2018, 1, 1, 23, 30),
                                          timezone=UTC),
            "12:34:56 PM")
        self.assertEqual(
            ENGLISH.format_datetime_smart(datetime(2018, 1, 1, 12, 34, 56),
                                          datetime(2018, 1, 2, 0, 30),
                                          timezone=UTC),
            "Jan 1, 2018, 12:34:56 PM")
        self.assertEqual(
            ENGLISH.format_datetime_smart(datetime(2018, 1, 1, 12, 34, 56),
                                          datetime(2017, 12, 31, 23, 30),
                                          timezone=UTC),
            "Jan 1, 2018, 12:34:56 PM")

    def test_other_timezone_winter(self):
        # Other timezone, in winter (no DST).
        self.assertEqual(
            ENGLISH.format_datetime_smart(datetime(2018, 1, 1, 12, 34, 56),
                                          datetime(2018, 1, 1, 22, 30),
                                          timezone=ROME),
            "1:34:56 PM")
        self.assertEqual(
            ENGLISH.format_datetime_smart(datetime(2018, 1, 1, 12, 34, 56),
                                          datetime(2018, 1, 1, 23, 30),
                                          timezone=ROME),
            "Jan 1, 2018, 1:34:56 PM")
        self.assertEqual(
            ENGLISH.format_datetime_smart(datetime(2018, 1, 1, 12, 34, 56),
                                          datetime(2017, 12, 31, 22, 30),
                                          timezone=ROME),
            "Jan 1, 2018, 1:34:56 PM")

    def test_other_timezone_summer(self):
        # Other timezone, in summer (DST).
        self.assertEqual(
            ENGLISH.format_datetime_smart(datetime(2018, 7, 1, 12, 34, 56),
                                          datetime(2018, 7, 1, 21, 30),
                                          timezone=ROME),
            "2:34:56 PM")
        self.assertEqual(
            ENGLISH.format_datetime_smart(datetime(2018, 7, 1, 12, 34, 56),
                                          datetime(2018, 7, 1, 22, 30),
                                          timezone=ROME),
            "Jul 1, 2018, 2:34:56 PM")
        self.assertEqual(
            ENGLISH.format_datetime_smart(datetime(2018, 7, 1, 12, 34, 56),
                                          datetime(2018, 6, 30, 21, 30),
                                          timezone=ROME),
            "Jul 1, 2018, 2:34:56 PM")

    # As above, localized.

    def test_localized_utc(self):
        self.assertEqual(
            ITALIAN.format_datetime_smart(datetime(2018, 1, 1, 12, 34, 56),
                                          datetime(2018, 1, 1, 23, 30),
                                          timezone=UTC),
            "12:34:56")
        self.assertEqual(
            ITALIAN.format_datetime_smart(datetime(2018, 1, 1, 12, 34, 56),
                                          datetime(2018, 1, 2, 0, 30),
                                          timezone=UTC),
            "01 gen 2018, 12:34:56")
        self.assertEqual(
            ITALIAN.format_datetime_smart(datetime(2018, 1, 1, 12, 34, 56),
                                          datetime(2017, 12, 31, 23, 30),
                                          timezone=UTC),
            "01 gen 2018, 12:34:56")

    def test_localized_other_timezone_winter(self):
        self.assertEqual(
            ITALIAN.format_datetime_smart(datetime(2018, 1, 1, 12, 34, 56),
                                          datetime(2018, 1, 1, 22, 30),
                                          timezone=ROME),
            "13:34:56")
        self.assertEqual(
            ITALIAN.format_datetime_smart(datetime(2018, 1, 1, 12, 34, 56),
                                          datetime(2018, 1, 1, 23, 30),
                                          timezone=ROME),
            "01 gen 2018, 13:34:56")
        self.assertEqual(
            ITALIAN.format_datetime_smart(datetime(2018, 1, 1, 12, 34, 56),
                                          datetime(2017, 12, 31, 22, 30),
                                          timezone=ROME),
            "01 gen 2018, 13:34:56")

    def test_localized_other_timezone_summer(self):
        self.assertEqual(
            ITALIAN.format_datetime_smart(datetime(2018, 7, 1, 12, 34, 56),
                                          datetime(2018, 7, 1, 21, 30),
                                          timezone=ROME),
            "14:34:56")
        self.assertEqual(
            ITALIAN.format_datetime_smart(datetime(2018, 7, 1, 12, 34, 56),
                                          datetime(2018, 7, 1, 22, 30),
                                          timezone=ROME),
            "01 lug 2018, 14:34:56")
        self.assertEqual(
            ITALIAN.format_datetime_smart(datetime(2018, 7, 1, 12, 34, 56),
                                          datetime(2018, 6, 30, 21, 30),
                                          timezone=ROME),
            "01 lug 2018, 14:34:56")


class TestFormatTimedelta(unittest.TestCase):

    def test_zero(self):
        # Trivial case.
        self.assertEqual(ENGLISH.format_timedelta(timedelta()),
                         "0 seconds")

    def test_unsupported(self):
        # Unsupported cases.
        self.assertEqual(ENGLISH.format_timedelta(timedelta(milliseconds=123)),
                         "0 seconds")
        self.assertEqual(ENGLISH.format_timedelta(timedelta(seconds=-1)),
                         "1 second")

    def test_different_units_at_different_magnitudes(self):
        # Different units.
        self.assertEqual(ENGLISH.format_timedelta(timedelta(seconds=2)),
                         "2 seconds")
        self.assertEqual(ENGLISH.format_timedelta(timedelta(minutes=3)),
                         "3 minutes")
        self.assertEqual(ENGLISH.format_timedelta(timedelta(hours=4)),
                         "4 hours")
        self.assertEqual(ENGLISH.format_timedelta(timedelta(days=5)),
                         "5 days")
        # Cap at days.
        self.assertEqual(ENGLISH.format_timedelta(timedelta(weeks=6)),
                         "42 days")

    def test_unit_combination(self):
        # Combine units.
        self.assertEqual(ENGLISH.format_timedelta(timedelta(days=1, hours=1,
                                                            minutes=1,
                                                            seconds=1)),
                         "1 day, 1 hour, 1 minute, and 1 second")

    # As above, localized (use a language with a 24h clock and with a
    # different day/month/year order).

    def test_localized_zero(self):
        self.assertEqual(ITALIAN.format_timedelta(timedelta()),
                         "0 secondi")

    def test_localized_unsupported(self):
        self.assertEqual(ITALIAN.format_timedelta(timedelta(milliseconds=123)),
                         "0 secondi")
        self.assertEqual(ITALIAN.format_timedelta(timedelta(seconds=-1)),
                         "1 secondo")

    def test_localized_different_units_at_different_magnitudes(self):
        self.assertEqual(ITALIAN.format_timedelta(timedelta(seconds=2)),
                         "2 secondi")
        self.assertEqual(ITALIAN.format_timedelta(timedelta(minutes=3)),
                         "3 minuti")
        self.assertEqual(ITALIAN.format_timedelta(timedelta(hours=4)),
                         "4 ore")
        self.assertEqual(ITALIAN.format_timedelta(timedelta(days=5)),
                         "5 giorni")
        self.assertEqual(ITALIAN.format_timedelta(timedelta(weeks=6)),
                         "42 giorni")

    def test_localized_unit_combination(self):
        self.assertEqual(ITALIAN.format_timedelta(timedelta(days=1, hours=1,
                                                            minutes=1,
                                                            seconds=1)),
                         "1 giorno, 1 ora, 1 minuto e 1 secondo")


class TestFormatDuration(unittest.TestCase):

    def test_zero(self):
        # Corner case.
        self.assertEqual(ENGLISH.format_duration(0),
                         "0.000 sec")
        self.assertEqual(ENGLISH.format_duration(0, length="long"),
                         "0.000 seconds")

    def test_small_integer_values(self):
        # Singular is used for a value of 1.
        self.assertEqual(ENGLISH.format_duration(1),
                         "1.000 sec")
        self.assertEqual(ENGLISH.format_duration(1, length="long"),
                         "1.000 second")
        self.assertEqual(ENGLISH.format_duration(2),
                         "2.000 sec")
        self.assertEqual(ENGLISH.format_duration(2, length="long"),
                         "2.000 seconds")

    def test_increasing_magnitude(self):
        # At most three fractional digits are shown if needed to get to
        # four significant digits.
        # Large values are *not* cast to minutes (or higher).
        self.assertEqual(ENGLISH.format_duration(0.123456789),
                         "0.123 sec")
        self.assertEqual(ENGLISH.format_duration(0.123456789, length="long"),
                         "0.123 seconds")
        self.assertEqual(ENGLISH.format_duration(1.23456789),
                         "1.235 sec")
        self.assertEqual(ENGLISH.format_duration(1.23456789, length="long"),
                         "1.235 seconds")
        self.assertEqual(ENGLISH.format_duration(12.3456789),
                         "12.346 sec")
        self.assertEqual(ENGLISH.format_duration(12.3456789, length="long"),
                         "12.346 seconds")
        self.assertEqual(ENGLISH.format_duration(123.456789),
                         "123.457 sec")
        self.assertEqual(ENGLISH.format_duration(123.456789, length="long"),
                         "123.457 seconds")
        self.assertEqual(ENGLISH.format_duration(1234.56789),
                         "1,234.568 sec")
        self.assertEqual(ENGLISH.format_duration(1234.56789, length="long"),
                         "1,234.568 seconds")
        self.assertEqual(ENGLISH.format_duration(12345.6789),
                         "12,345.679 sec")
        self.assertEqual(ENGLISH.format_duration(12345.6789, length="long"),
                         "12,345.679 seconds")

    # As above, localized.

    def test_localized_zero(self):
        self.assertEqual(ITALIAN.format_duration(0),
                         "0,000 s")
        self.assertEqual(ITALIAN.format_duration(0, length="long"),
                         "0,000 secondi")

    def test_localized_small_integer_values(self):
        self.assertEqual(ITALIAN.format_duration(1),
                         "1,000 s")
        self.assertEqual(ITALIAN.format_duration(1, length="long"),
                         "1,000 secondo")
        self.assertEqual(ITALIAN.format_duration(2),
                         "2,000 s")
        self.assertEqual(ITALIAN.format_duration(2, length="long"),
                         "2,000 secondi")

    def test_localized_increasing_magnitude(self):
        self.assertEqual(ITALIAN.format_duration(0.123456789),
                         "0,123 s")
        self.assertEqual(ITALIAN.format_duration(0.123456789, length="long"),
                         "0,123 secondi")
        self.assertEqual(ITALIAN.format_duration(1.23456789),
                         "1,235 s")
        self.assertEqual(ITALIAN.format_duration(1.23456789, length="long"),
                         "1,235 secondi")
        self.assertEqual(ITALIAN.format_duration(12.3456789),
                         "12,346 s")
        self.assertEqual(ITALIAN.format_duration(12.3456789, length="long"),
                         "12,346 secondi")
        self.assertEqual(ITALIAN.format_duration(123.456789),
                         "123,457 s")
        self.assertEqual(ITALIAN.format_duration(123.456789, length="long"),
                         "123,457 secondi")
        self.assertEqual(ITALIAN.format_duration(1234.56789),
                         "1.234,568 s")
        self.assertEqual(ITALIAN.format_duration(1234.56789, length="long"),
                         "1.234,568 secondi")
        self.assertEqual(ITALIAN.format_duration(12345.6789),
                         "12.345,679 s")
        self.assertEqual(ITALIAN.format_duration(12345.6789, length="long"),
                         "12.345,679 secondi")


class TestFormatSize(unittest.TestCase):

    def test_zero(self):
        # Corner case.
        self.assertEqual(ENGLISH.format_size(0),
                         "0 byte")

    def test_small_values(self):
        # Note that there is no singular/plural.
        self.assertEqual(ENGLISH.format_size(1),
                         "1 byte")
        self.assertEqual(ENGLISH.format_size(2),
                         "2 byte")

    def test_cutoff(self):
        # Cutoff is at 1000, not 1024, as we use kilo, mega, ... rather
        # than kibi, mebi, ...
        self.assertEqual(ENGLISH.format_size(999),
                         "999 byte")
        self.assertEqual(ENGLISH.format_size(1000),
                         "1.00 kB")
        self.assertEqual(ENGLISH.format_size(1024),
                         "1.02 kB")

    def test_large(self):
        # Ensure larger units are used for larger values, with rounding
        # to three significant digits, up to terabytes.
        self.assertEqual(ENGLISH.format_size(2.345 * 1000000),
                         "2.34 MB")
        self.assertEqual(ENGLISH.format_size(34.567 * 1000000000),
                         "34.6 GB")
        self.assertEqual(ENGLISH.format_size(456.789 * 1000000000000),
                         "457 TB")
        self.assertEqual(ENGLISH.format_size(5678.9 * 1000000000000),
                         "5,679 TB")

    # As above, localized (use French as it's sensibly different).

    def test_localized_zero(self):
        self.assertEqual(FRENCH.format_size(0),
                         "0 octet")

    def test_localized_small_values(self):
        self.assertEqual(FRENCH.format_size(1),
                         "1 octet")
        self.assertEqual(FRENCH.format_size(2),
                         "2 octet")

    def test_localized_cutoff(self):
        self.assertEqual(FRENCH.format_size(999),
                         "999 octet")
        self.assertEqual(FRENCH.format_size(1000),
                         "1,00 ko")
        self.assertEqual(FRENCH.format_size(1024),
                         "1,02 ko")

    def test_localized_large(self):
        self.assertEqual(FRENCH.format_size(2.345 * 1000000),
                         "2,34 Mo")
        self.assertEqual(FRENCH.format_size(34.567 * 1000000000),
                         "34,6 Go")
        self.assertEqual(FRENCH.format_size(456.789 * 1000000000000),
                         "457 To")
        self.assertEqual(FRENCH.format_size(5678.9123 * 1000000000000),
                         "5\N{NO-BREAK SPACE}679 To")


class TestFormatDecimal(unittest.TestCase):

    def test_integers(self):
        # Integers stay integers.
        self.assertEqual(ENGLISH.format_decimal(0),
                         "0")
        self.assertEqual(ENGLISH.format_decimal(1),
                         "1")
        self.assertEqual(ENGLISH.format_decimal(2),
                         "2")

    def test_thousands_separators(self):
        # Large integers get thousands separators.
        self.assertEqual(ENGLISH.format_decimal(1234),
                         "1,234")
        self.assertEqual(ENGLISH.format_decimal(1234567890),
                         "1,234,567,890")

    def test_fractional_digits_and_rounding(self):
        # Fractional digits are preserved and rounded.
        self.assertEqual(ENGLISH.format_decimal(1.23456789),
                         "1.235")

    def test_localized_decimal_and_thousands_separators(self):
        # Ensure correct decimal and thousands separators are used.
        self.assertEqual(ITALIAN.format_decimal(1234567890),
                         "1.234.567.890")
        self.assertEqual(ITALIAN.format_decimal(1.23456789),
                         "1,235")
        # Use Hindi as they have a peculiar separator rule.
        self.assertEqual(HINDI.format_decimal(1234567890),
                         "1,23,45,67,890")


if __name__ == "__main__":
    unittest.main()
