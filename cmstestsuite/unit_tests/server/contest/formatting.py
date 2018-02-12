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

import pytz

from cms.locale import Translation
from cms.server.contest.formatting import format_datetime, format_time, \
    format_datetime_smart, format_timedelta, format_duration, format_size, \
    format_decimal


UTC = pytz.utc
ROME = pytz.timezone("Europe/Rome")

FRENCH = Translation("fr")
HINDI = Translation("hi")
ITALIAN = Translation("it")
NORWEGIAN = Translation("no")


class TestCWSFormatting(unittest.TestCase):

    def test_format_datetime(self):
        # UTC, in English
        self.assertEqual(format_datetime(datetime(2018, 1, 1, 12, 34, 56),
                                         timezone=UTC),
                         "Jan 1, 2018, 12:34:56 PM")

        # Other timezone, at different DST offsets.
        self.assertEqual(format_datetime(datetime(2018, 1, 1, 12, 34, 56),
                                         timezone=ROME),
                         "Jan 1, 2018, 1:34:56 PM")
        self.assertEqual(format_datetime(datetime(2018, 7, 1, 12, 34, 56),
                                         timezone=ROME),
                         "Jul 1, 2018, 2:34:56 PM")

        # As above, localized.
        self.assertEqual(format_datetime(datetime(2018, 1, 1, 12, 34, 56),
                                         timezone=UTC, translation=ITALIAN),
                         "01 gen 2018, 12:34:56")
        self.assertEqual(format_datetime(datetime(2018, 1, 1, 12, 34, 56),
                                         timezone=ROME, translation=ITALIAN),
                         "01 gen 2018, 13:34:56")
        self.assertEqual(format_datetime(datetime(2018, 7, 1, 12, 34, 56),
                                         timezone=ROME, translation=ITALIAN),
                         "01 lug 2018, 14:34:56")

    def test_format_time(self):
        # UTC, in English
        self.assertEqual(format_time(datetime(2018, 1, 1, 12, 34, 56),
                                     timezone=UTC),
                         "12:34:56 PM")

        # Other timezone, at different DST offsets.
        self.assertEqual(format_time(datetime(2018, 1, 1, 12, 34, 56),
                                     timezone=ROME),
                         "1:34:56 PM")
        self.assertEqual(format_time(datetime(2018, 7, 1, 12, 34, 56),
                                     timezone=ROME),
                         "2:34:56 PM")

        # As above, localized.
        self.assertEqual(format_time(datetime(2018, 1, 1, 12, 34, 56),
                                     timezone=UTC, translation=NORWEGIAN),
                         "12.34.56")
        self.assertEqual(format_time(datetime(2018, 1, 1, 12, 34, 56),
                                     timezone=ROME, translation=NORWEGIAN),
                         "13.34.56")
        self.assertEqual(format_time(datetime(2018, 7, 1, 12, 34, 56),
                                     timezone=ROME, translation=NORWEGIAN),
                         "14.34.56")

    def test_format_datetime_smart(self):
        # UTC, in English
        self.assertEqual(
            format_datetime_smart(datetime(2018, 1, 1, 12, 34, 56),
                                  datetime(2018, 1, 1, 23, 30),
                                  timezone=UTC),
            "12:34:56 PM")
        self.assertEqual(
            format_datetime_smart(datetime(2018, 1, 1, 12, 34, 56),
                                  datetime(2018, 1, 2, 0, 30),
                                  timezone=UTC),
            "Jan 1, 2018, 12:34:56 PM")
        self.assertEqual(
            format_datetime_smart(datetime(2018, 1, 1, 12, 34, 56),
                                  datetime(2017, 12, 31, 23, 30),
                                  timezone=UTC),
            "Jan 1, 2018, 12:34:56 PM")

        # Other timezone, at different DST offsets.
        self.assertEqual(
            format_datetime_smart(datetime(2018, 1, 1, 12, 34, 56),
                                  datetime(2018, 1, 1, 22, 30),
                                  timezone=ROME),
            "1:34:56 PM")
        self.assertEqual(
            format_datetime_smart(datetime(2018, 1, 1, 12, 34, 56),
                                  datetime(2018, 1, 1, 23, 30),
                                  timezone=ROME),
            "Jan 1, 2018, 1:34:56 PM")
        self.assertEqual(
            format_datetime_smart(datetime(2018, 1, 1, 12, 34, 56),
                                  datetime(2017, 12, 31, 22, 30),
                                  timezone=ROME),
            "Jan 1, 2018, 1:34:56 PM")
        self.assertEqual(
            format_datetime_smart(datetime(2018, 7, 1, 12, 34, 56),
                                  datetime(2018, 7, 1, 21, 30),
                                  timezone=ROME),
            "2:34:56 PM")
        self.assertEqual(
            format_datetime_smart(datetime(2018, 7, 1, 12, 34, 56),
                                  datetime(2018, 7, 1, 22, 30),
                                  timezone=ROME),
            "Jul 1, 2018, 2:34:56 PM")
        self.assertEqual(
            format_datetime_smart(datetime(2018, 7, 1, 12, 34, 56),
                                  datetime(2018, 6, 30, 21, 30),
                                  timezone=ROME),
            "Jul 1, 2018, 2:34:56 PM")

        # As above, localized.
        self.assertEqual(
            format_datetime_smart(datetime(2018, 1, 1, 12, 34, 56),
                                  datetime(2018, 1, 1, 23, 30),
                                  timezone=UTC, translation=ITALIAN),
            "12:34:56")
        self.assertEqual(
            format_datetime_smart(datetime(2018, 1, 1, 12, 34, 56),
                                  datetime(2018, 1, 2, 0, 30),
                                  timezone=UTC, translation=ITALIAN),
            "01 gen 2018, 12:34:56")
        self.assertEqual(
            format_datetime_smart(datetime(2018, 1, 1, 12, 34, 56),
                                  datetime(2017, 12, 31, 23, 30),
                                  timezone=UTC, translation=ITALIAN),
            "01 gen 2018, 12:34:56")
        self.assertEqual(
            format_datetime_smart(datetime(2018, 1, 1, 12, 34, 56),
                                  datetime(2018, 1, 1, 22, 30),
                                  timezone=ROME, translation=ITALIAN),
            "13:34:56")
        self.assertEqual(
            format_datetime_smart(datetime(2018, 1, 1, 12, 34, 56),
                                  datetime(2018, 1, 1, 23, 30),
                                  timezone=ROME, translation=ITALIAN),
            "01 gen 2018, 13:34:56")
        self.assertEqual(
            format_datetime_smart(datetime(2018, 1, 1, 12, 34, 56),
                                  datetime(2017, 12, 31, 22, 30),
                                  timezone=ROME, translation=ITALIAN),
            "01 gen 2018, 13:34:56")
        self.assertEqual(
            format_datetime_smart(datetime(2018, 7, 1, 12, 34, 56),
                                  datetime(2018, 7, 1, 21, 30),
                                  timezone=ROME, translation=ITALIAN),
            "14:34:56")
        self.assertEqual(
            format_datetime_smart(datetime(2018, 7, 1, 12, 34, 56),
                                  datetime(2018, 7, 1, 22, 30),
                                  timezone=ROME, translation=ITALIAN),
            "01 lug 2018, 14:34:56")
        self.assertEqual(
            format_datetime_smart(datetime(2018, 7, 1, 12, 34, 56),
                                  datetime(2018, 6, 30, 21, 30),
                                  timezone=ROME, translation=ITALIAN),
            "01 lug 2018, 14:34:56")

    def test_format_timedelta(self):
        # Trivial case.
        self.assertEqual(format_timedelta(timedelta()),
                         "0 seconds")
        # Unsupported cases.
        self.assertEqual(format_timedelta(timedelta(milliseconds=123)),
                         "0 seconds")
        self.assertEqual(format_timedelta(timedelta(seconds=-1)),
                         "1 second")
        # Different units.
        self.assertEqual(format_timedelta(timedelta(seconds=2)),
                         "2 seconds")
        self.assertEqual(format_timedelta(timedelta(minutes=3)),
                         "3 minutes")
        self.assertEqual(format_timedelta(timedelta(hours=4)),
                         "4 hours")
        self.assertEqual(format_timedelta(timedelta(days=5)),
                         "5 days")
        # Cap at days.
        self.assertEqual(format_timedelta(timedelta(weeks=6)),
                         "42 days")
        # Combine units.
        self.assertEqual(format_timedelta(timedelta(days=1, hours=1,
                                                    minutes=1, seconds=1)),
                         "1 day, 1 hour, 1 minute, and 1 second")

        # As above, localized.
        self.assertEqual(format_timedelta(timedelta(),
                                          translation=ITALIAN),
                         "0 secondi")
        self.assertEqual(format_timedelta(timedelta(milliseconds=123),
                                          translation=ITALIAN),
                         "0 secondi")
        self.assertEqual(format_timedelta(timedelta(seconds=-1),
                                          translation=ITALIAN),
                         "1 secondo")
        self.assertEqual(format_timedelta(timedelta(seconds=2),
                                          translation=ITALIAN),
                         "2 secondi")
        self.assertEqual(format_timedelta(timedelta(minutes=3),
                                          translation=ITALIAN),
                         "3 minuti")
        self.assertEqual(format_timedelta(timedelta(hours=4),
                                          translation=ITALIAN),
                         "4 ore")
        self.assertEqual(format_timedelta(timedelta(days=5),
                                          translation=ITALIAN),
                         "5 giorni")
        self.assertEqual(format_timedelta(timedelta(weeks=6),
                                          translation=ITALIAN),
                         "42 giorni")
        self.assertEqual(format_timedelta(timedelta(days=1, hours=1,
                                                    minutes=1, seconds=1),
                                          translation=ITALIAN),
                         "1 giorno, 1 ora, 1 minuto e 1 secondo")

    def test_format_duration(self):
        # Corner case.
        self.assertEqual(format_duration(0),
                         "0 sec")
        self.assertEqual(format_duration(0, length="long"),
                         "0 seconds")

        # Singular is used for a value of 1.
        self.assertEqual(format_duration(1),
                         "1 sec")
        self.assertEqual(format_duration(1, length="long"),
                         "1 second")
        self.assertEqual(format_duration(2),
                         "2 sec")
        self.assertEqual(format_duration(2, length="long"),
                         "2 seconds")
        # Fractional digits are shown.
        # Values are rounded to four significant digits.
        self.assertEqual(format_duration(1.2345),
                         "1.234 sec")
        self.assertEqual(format_duration(1.2345, length="long"),
                         "1.234 seconds")
        # Large values are *not* cast to minutes (or higher).
        self.assertEqual(format_duration(12345.6789),
                         "12350 sec")
        self.assertEqual(format_duration(12345.6789, length="long"),
                         "12350 seconds")

        # As above, localized.
        self.assertEqual(format_duration(1,
                                         translation=ITALIAN),
                         "1 s")
        self.assertEqual(format_duration(1, length="long",
                                         translation=ITALIAN),
                         "1 secondo")
        self.assertEqual(format_duration(1.2345,
                                         translation=ITALIAN),
                         "1,234 s")
        self.assertEqual(format_duration(1.2345, length="long",
                                         translation=ITALIAN),
                         "1,234 secondi")
        self.assertEqual(format_duration(12345.6789,
                                         translation=ITALIAN),
                         "12350 s")
        self.assertEqual(format_duration(12345.6789, length="long",
                                         translation=ITALIAN),
                         "12350 secondi")

    def test_format_size(self):
        # Corner case.
        self.assertEqual(format_size(0),
                         "0 byte")
        self.assertEqual(format_size(1),
                         "1 byte")
        # Cutoff is at 1000, not 1024, as we use kilo, mega, ... rather
        # than kibi, mebi, ...
        self.assertEqual(format_size(999),
                         "999 byte")
        self.assertEqual(format_size(1000),
                         "1 kB")
        self.assertEqual(format_size(1024),
                         "1.02 kB")
        # Ensure larger units are used for larger values, with rounding
        # to three significant digits, up to terabytes.
        self.assertEqual(format_size(2.345 * 1000 * 1000),
                         "2.34 MB")
        self.assertEqual(format_size(34.567 * 1000 * 1000 * 1000),
                         "34.6 GB")
        self.assertEqual(format_size(456.789 * 1000 * 1000 * 1000 * 1000),
                         "457 TB")
        self.assertEqual(format_size(5678.9 * 1000 * 1000 * 1000 * 1000),
                         "5680 TB")

        # As above, localized (use French as it's sensibly different).
        self.assertEqual(format_size(0,
                                     translation=FRENCH),
                         "0 octet")
        self.assertEqual(format_size(1,
                                     translation=FRENCH),
                         "1 octet")
        self.assertEqual(format_size(999,
                                     translation=FRENCH),
                         "999 octet")
        self.assertEqual(format_size(1000,
                                     translation=FRENCH),
                         "1 ko")
        self.assertEqual(format_size(1024,
                                     translation=FRENCH),
                         "1,02 ko")
        self.assertEqual(format_size(2.345 * 1000 * 1000,
                                     translation=FRENCH),
                         "2,34 Mo")
        self.assertEqual(format_size(34.567 * 1000 * 1000 * 1000,
                                     translation=FRENCH),
                         "34,6 Go")
        self.assertEqual(format_size(456.789 * 1000 * 1000 * 1000 * 1000,
                                     translation=FRENCH),
                         "457 To")
        self.assertEqual(format_size(5678.9 * 1000 * 1000 * 1000 * 1000,
                                     translation=FRENCH),
                         "5680 To")

    def test_format_decimal(self):
        # Integers stay integers.
        self.assertEqual(format_decimal(0),
                         "0")
        self.assertEqual(format_decimal(1),
                         "1")
        self.assertEqual(format_decimal(2),
                         "2")
        # Large integers get thousands separators.
        self.assertEqual(format_decimal(1234),
                         "1,234")
        self.assertEqual(format_decimal(1234567890),
                         "1,234,567,890")
        # Fractional digits are preserved and rounded.
        self.assertEqual(format_decimal(1.23456789),
                         "1.235")

        # Ensure correct decimal and thousands separators are used.
        self.assertEqual(format_decimal(1234567890, translation=ITALIAN),
                         "1.234.567.890")
        self.assertEqual(format_decimal(1.23456789, translation=ITALIAN),
                         "1,235")
        self.assertEqual(format_decimal(1234567890, translation=HINDI),
                         "1,23,45,67,890")


if __name__ == "__main__":
    unittest.main()
