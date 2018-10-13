#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
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

"""Tests for common grading functions.

"""

import unittest

from cms.grading import format_status_text


class DummyTranslation:
    @staticmethod
    def gettext(s):
        if s == "":
            return "the headers of the po file"
        return s.replace("A", "E")


class TestFormatStatusText(unittest.TestCase):

    def setUp(self):
        self._tr = DummyTranslation()

    def test_success_no_placeholders(self):
        self.assertEqual(format_status_text([]), "N/A")
        self.assertEqual(format_status_text([""]), "")
        self.assertEqual(format_status_text(["ASD"]), "ASD")
        self.assertEqual(format_status_text(["你好"]), "你好")

    def test_success_with_placeholders(self):
        self.assertEqual(format_status_text(["%s", "ASD"]), "ASD")
        self.assertEqual(format_status_text(["ASD%s\n%s", "QWE", "123"]),
                         "ASDQWE\n123")

    def test_success_with_translator(self):
        self.assertEqual(format_status_text([""], self._tr), "")
        self.assertEqual(format_status_text(["ASD"], self._tr), "ESD")
        # Translation is applied before formatting.
        self.assertEqual(format_status_text(["A%s", "ASD"], self._tr), "EASD")
        self.assertEqual(
            format_status_text(["AAA %s\n%s", "AAA", "AE"], self._tr),
            "EEE AAA\nAE")

    def test_failure(self):
        # Not enough elements for the placeholders.
        self.assertEqual(format_status_text(["%s"]), "N/A")
        self.assertEqual(format_status_text(["%s"], self._tr), "N/E")
        # No elements at all.
        self.assertEqual(format_status_text([]), "N/A")
        self.assertEqual(format_status_text([], self._tr), "N/E")


if __name__ == "__main__":
    unittest.main()
