#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""Tests for CWS formatting functions.

"""

import os.path
import unittest
from datetime import datetime, timedelta
from io import BytesIO

import babel.dates
from babel.messages import Catalog
from babel.messages.mofile import write_mo

from cms.locale import Translation, DEFAULT_TRANSLATION, filter_language_codes, \
    choose_language_code


UTC = babel.dates.UTC
ROME = babel.dates.get_timezone("Europe/Rome")

FRENCH_CATALOG = Catalog(locale="fr")
FRENCH_CATALOG.add("%s KiB", "%s Kio")
FRENCH_CATALOG.add("%s MiB", "%s Mio")
FRENCH_CATALOG.add("%s GiB", "%s Gio")
FRENCH_CATALOG.add("%s TiB", "%s Tio")
FRENCH_CATALOG_BUF = BytesIO()
write_mo(FRENCH_CATALOG_BUF, FRENCH_CATALOG)
FRENCH_CATALOG_BUF.seek(0)

ENGLISH = DEFAULT_TRANSLATION
BRITISH_ENGLISH = Translation("en_GB")
FRENCH = Translation("fr", mofile=FRENCH_CATALOG_BUF)
HINDI = Translation("hi")
ITALIAN = Translation("it")
DANISH = Translation("da")
CHINESE = Translation("zh_CN")


class TestIdentifier(unittest.TestCase):

    def test_language_only(self):
        self.assertEqual(ENGLISH.identifier, "en")
        self.assertEqual(ITALIAN.identifier, "it")

    def test_language_and_country(self):
        self.assertEqual(BRITISH_ENGLISH.identifier, "en-GB")

    def test_language_country_and_inferred_script(self):
        self.assertEqual(CHINESE.identifier, "zh-Hans-CN")


class TestName(unittest.TestCase):

    def test_own_name_language_only(self):
        self.assertEqual(ENGLISH.name, "English")
        self.assertEqual(ITALIAN.name, "italiano")

    def test_own_name_language_and_country(self):
        self.assertEqual(BRITISH_ENGLISH.name, "English (United Kingdom)")

    def test_own_name_language_country_and_inferred_script(self):
        self.assertEqual(CHINESE.name, "中文 (简体, 中国)")

    def test_other_name_language_only(self):
        self.assertEqual(ENGLISH.format_locale("it"), "Italian")
        self.assertEqual(ITALIAN.format_locale("en"), "inglese")

    def test_other_name_language_and_country(self):
        self.assertEqual(ITALIAN.format_locale("en_GB"),
                         "inglese (Regno Unito)")
        self.assertEqual(FRENCH.format_locale("fr_CA"), "français (Canada)")

    def test_other_name_language_country_and_inferred_script(self):
        self.assertEqual(ENGLISH.format_locale("zh_CN"),
                         "Chinese (Simplified, China)")
        self.assertEqual(ITALIAN.format_locale("zh_CN"),
                         "cinese (semplificato, Cina)")


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
            "1 gen 2018, 12:34:56")

    def test_localized_other_timezone_winter(self):
        self.assertEqual(
            ITALIAN.format_datetime(datetime(2018, 1, 1, 12, 34, 56),
                                    timezone=ROME),
            "1 gen 2018, 13:34:56")

    def test_localized_other_timezone_summer(self):
        self.assertEqual(
            ITALIAN.format_datetime(datetime(2018, 7, 1, 12, 34, 56),
                                    timezone=ROME),
            "1 lug 2018, 14:34:56")


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

    # As above, localized (use Danish as they use periods rather
    # than colons and have a 24h clock).

    def test_localized_utc(self):
        self.assertEqual(DANISH.format_time(datetime(2018, 1, 1, 12, 34, 56),
                                            timezone=UTC),
                         "12.34.56")

    def test_localized_other_timezone_winter(self):
        self.assertEqual(DANISH.format_time(datetime(2018, 1, 1, 12, 34, 56),
                                            timezone=ROME),
                         "13.34.56")

    def test_localized_other_timezone_summer(self):
        self.assertEqual(DANISH.format_time(datetime(2018, 7, 1, 12, 34, 56),
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
            "1 gen 2018, 12:34:56")
        self.assertEqual(
            ITALIAN.format_datetime_smart(datetime(2018, 1, 1, 12, 34, 56),
                                          datetime(2017, 12, 31, 23, 30),
                                          timezone=UTC),
            "1 gen 2018, 12:34:56")

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
            "1 gen 2018, 13:34:56")
        self.assertEqual(
            ITALIAN.format_datetime_smart(datetime(2018, 1, 1, 12, 34, 56),
                                          datetime(2017, 12, 31, 22, 30),
                                          timezone=ROME),
            "1 gen 2018, 13:34:56")

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
            "1 lug 2018, 14:34:56")
        self.assertEqual(
            ITALIAN.format_datetime_smart(datetime(2018, 7, 1, 12, 34, 56),
                                          datetime(2018, 6, 30, 21, 30),
                                          timezone=ROME),
            "1 lug 2018, 14:34:56")


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
        self.assertEqual(ENGLISH.format_duration(0.123_456_789),
                         "0.123 sec")
        self.assertEqual(ENGLISH.format_duration(0.123_456_789, length="long"),
                         "0.123 seconds")
        self.assertEqual(ENGLISH.format_duration(1.234_567_89),
                         "1.235 sec")
        self.assertEqual(ENGLISH.format_duration(1.234_567_89, length="long"),
                         "1.235 seconds")
        self.assertEqual(ENGLISH.format_duration(12.345_678_9),
                         "12.346 sec")
        self.assertEqual(ENGLISH.format_duration(12.345_678_9, length="long"),
                         "12.346 seconds")
        self.assertEqual(ENGLISH.format_duration(123.456_789),
                         "123.457 sec")
        self.assertEqual(ENGLISH.format_duration(123.456_789, length="long"),
                         "123.457 seconds")
        self.assertEqual(ENGLISH.format_duration(1234.567_89),
                         "1,234.568 sec")
        self.assertEqual(ENGLISH.format_duration(1234.567_89, length="long"),
                         "1,234.568 seconds")
        self.assertEqual(ENGLISH.format_duration(12_345.678_9),
                         "12,345.679 sec")
        self.assertEqual(ENGLISH.format_duration(12_345.678_9, length="long"),
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
        self.assertEqual(ITALIAN.format_duration(0.123_456_789),
                         "0,123 s")
        self.assertEqual(ITALIAN.format_duration(0.123_456_789, length="long"),
                         "0,123 secondi")
        self.assertEqual(ITALIAN.format_duration(1.234_567_89),
                         "1,235 s")
        self.assertEqual(ITALIAN.format_duration(1.234_567_89, length="long"),
                         "1,235 secondi")
        self.assertEqual(ITALIAN.format_duration(12.345_678_9),
                         "12,346 s")
        self.assertEqual(ITALIAN.format_duration(12.345_678_9, length="long"),
                         "12,346 secondi")
        self.assertEqual(ITALIAN.format_duration(123.456_789),
                         "123,457 s")
        self.assertEqual(ITALIAN.format_duration(123.456_789, length="long"),
                         "123,457 secondi")
        self.assertEqual(ITALIAN.format_duration(1234.567_89),
                         "1.234,568 s")
        self.assertEqual(ITALIAN.format_duration(1234.567_89, length="long"),
                         "1.234,568 secondi")
        self.assertEqual(ITALIAN.format_duration(12_345.678_9),
                         "12.345,679 s")
        self.assertEqual(ITALIAN.format_duration(12_345.678_9, length="long"),
                         "12.345,679 secondi")


class TestFormatSize(unittest.TestCase):

    def test_zero(self):
        # Corner case.
        self.assertEqual(ENGLISH.format_size(0),
                         "0 bytes")

    def test_small_values(self):
        # Note that there is no singular/plural.
        self.assertEqual(ENGLISH.format_size(1),
                         "1 byte")
        self.assertEqual(ENGLISH.format_size(2),
                         "2 bytes")

    def test_cutoff_kib(self):
        self.assertEqual(ENGLISH.format_size(999),
                         "999 bytes")
        self.assertEqual(ENGLISH.format_size(1000),
                         "1,000 bytes")
        self.assertEqual(ENGLISH.format_size(1001),
                         "1,001 bytes")
        self.assertEqual(ENGLISH.format_size(1023),
                         "1,023 bytes")
        self.assertEqual(ENGLISH.format_size(1024),
                         "1.00 KiB")
        self.assertEqual(ENGLISH.format_size(1025),
                         "1.00 KiB")

    def test_cutoff_mib(self):
        self.assertEqual(ENGLISH.format_size(999 * 1024),
                         "999 KiB")
        self.assertEqual(ENGLISH.format_size(1000 * 1024),
                         "1,000 KiB")
        self.assertEqual(ENGLISH.format_size(1001 * 1024),
                         "1,001 KiB")
        self.assertEqual(ENGLISH.format_size(1023 * 1024),
                         "1,023 KiB")
        self.assertEqual(ENGLISH.format_size(1024 * 1024),
                         "1.00 MiB")
        self.assertEqual(ENGLISH.format_size(1025 * 1024),
                         "1.00 MiB")

    def test_large(self):
        # Ensure larger units are used for larger values, with rounding
        # to three significant digits, up to terabytes.
        self.assertEqual(ENGLISH.format_size(2_345_000),
                         "2.24 MiB")
        self.assertEqual(ENGLISH.format_size(34_567_000_000),
                         "32.2 GiB")
        self.assertEqual(ENGLISH.format_size(456_789_000_000_000),
                         "415 TiB")
        self.assertEqual(ENGLISH.format_size(5_678_900_000_000_000),
                         "5,165 TiB")

    # As above, localized (use French as it's sensibly different).

    def test_localized_zero(self):
        self.assertEqual(FRENCH.format_size(0),
                         "0 octet")

    def test_localized_small_values(self):
        self.assertEqual(FRENCH.format_size(1),
                         "1 octet")
        self.assertEqual(FRENCH.format_size(2),
                         "2 octets")

    def test_localized_cutoff_kib(self):
        self.assertEqual(FRENCH.format_size(999),
                         "999 octets")
        self.assertEqual(FRENCH.format_size(1000),
                         "1\N{NO-BREAK SPACE}000 octets")
        self.assertEqual(FRENCH.format_size(1001),
                         "1\N{NO-BREAK SPACE}001 octets")
        self.assertEqual(FRENCH.format_size(1023),
                         "1\N{NO-BREAK SPACE}023 octets")
        self.assertEqual(FRENCH.format_size(1024),
                         "1,00 Kio")
        self.assertEqual(FRENCH.format_size(1025),
                         "1,00 Kio")

    def test_localized_cutoff_mib(self):
        self.assertEqual(FRENCH.format_size(999 * 1024),
                         "999 Kio")
        self.assertEqual(FRENCH.format_size(1000 * 1024),
                         "1\N{NO-BREAK SPACE}000 Kio")
        self.assertEqual(FRENCH.format_size(1001 * 1024),
                         "1\N{NO-BREAK SPACE}001 Kio")
        self.assertEqual(FRENCH.format_size(1023 * 1024),
                         "1\N{NO-BREAK SPACE}023 Kio")
        self.assertEqual(FRENCH.format_size(1024 * 1024),
                         "1,00 Mio")
        self.assertEqual(FRENCH.format_size(1025 * 1024),
                         "1,00 Mio")


    def test_localized_large(self):
        self.assertEqual(FRENCH.format_size(2_345_000),
                         "2,24 Mio")
        self.assertEqual(FRENCH.format_size(34_567_000_000),
                         "32,2 Gio")
        self.assertEqual(FRENCH.format_size(456_789_000_000_000),
                         "415 Tio")
        self.assertEqual(FRENCH.format_size(5_678_912_300_000_000),
                         "5\N{NO-BREAK SPACE}165 Tio")


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
        self.assertEqual(ENGLISH.format_decimal(1_234_567_890),
                         "1,234,567,890")

    def test_fractional_digits_and_rounding(self):
        # Fractional digits are preserved and rounded.
        self.assertEqual(ENGLISH.format_decimal(1.234_567_89),
                         "1.235")

    def test_localized_decimal_and_thousands_separators(self):
        # Ensure correct decimal and thousands separators are used.
        self.assertEqual(ITALIAN.format_decimal(1_234_567_890),
                         "1.234.567.890")
        self.assertEqual(ITALIAN.format_decimal(1.234_567_89),
                         "1,235")
        # Use Hindi as they have a peculiar separator rule.
        self.assertEqual(HINDI.format_decimal(1_234_567_890),
                         "1,23,45,67,890")


class TestTranslateMimetype(unittest.TestCase):

    @unittest.skipIf(not os.path.isfile(
        "/usr/share/locale/it/LC_MESSAGES/shared-mime-info.mo"),
                     reason="need Italian shared-mime-info translation")
    def test_translate_mimetype(self):
        self.assertEqual(ENGLISH.translate_mimetype("PDF document"),
                         "PDF document")
        self.assertEqual(ITALIAN.translate_mimetype("PDF document"),
                         "Documento PDF")

    def test_graceful_failure(self):
        self.assertEqual(ENGLISH.translate_mimetype("Not a MIME type"),
                         "Not a MIME type")
        self.assertEqual(ITALIAN.translate_mimetype("Not a MIME type"),
                         "Not a MIME type")


class TestFilterLanguageCodes(unittest.TestCase):

    def test_exact_match(self):
        self.assertListEqual(filter_language_codes(["en-US", "fr-FR", "it-IT"],
                                                   ["en-US", "it-IT", "de-DE"]),
                             ["en-US", "it-IT"])

    def test_prefix_match(self):
        self.assertListEqual(filter_language_codes(["en-US", "fr-FR", "it-IT"],
                                                   ["en", "it", "de"]),
                             ["en-US", "it-IT"])

    def test_no_match(self):
        self.assertListEqual(filter_language_codes(["it-IT"], ["fr"]), ["en"])
        self.assertListEqual(filter_language_codes([], ["fr"]), ["en"])
        self.assertListEqual(filter_language_codes(["it-IT"], []), ["en"])

    def test_invalid_locale(self):
        self.assertListEqual(filter_language_codes(["it", "froobar", "fr-FR"],
                                                   ["fr"]),
                             ["fr-FR"])

    def test_invalid_prefix(self):
        self.assertListEqual(filter_language_codes(["it", "fr-FR"],
                                                   ["de", "froobar", "fr"]),
                             ["fr-FR"])


class TestChooseLanguageCode(unittest.TestCase):

    def test_exact_match(self):
        self.assertEqual(
            choose_language_code(["it-IT", "fr-FR"], ["fr-FR", "en-US"]),
            "fr-FR")

    def test_prefix_match(self):
        self.assertEqual(
            choose_language_code(["it", "fr"], ["fr-FR", "en-US"]), "fr-FR")
        self.assertEqual(
            choose_language_code(["fr-FR", "en-US"], ["fr", "en"]), "fr")

    def test_no_match(self):
        self.assertEqual(
            choose_language_code(["fr", "en"], ["it", "de"]), None)
        self.assertEqual(choose_language_code(["fr", "en"], []), None)
        self.assertEqual(choose_language_code([], ["it", "de"]), None)

    def test_invalid_locale(self):
        self.assertEqual(
            choose_language_code(["it", "froobar", "fr-FR"], ["fr"]), "fr")
        self.assertEqual(
            choose_language_code(["it", "fr-FR"], ["de", "froobar", "fr"]),
            "fr")


if __name__ == "__main__":
    unittest.main()
