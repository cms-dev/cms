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

"""Tests for parameter types."""

import unittest

try:
    from tornado4.web import MissingArgumentError
except ImportError:
    from tornado.web import MissingArgumentError

from cms.grading.ParameterTypes import ParameterTypeString, \
    ParameterTypeInt, ParameterTypeChoice, ParameterTypeCollection


class FakeHandler:
    """Fake handler with a static set of arguments."""

    def __init__(self, arguments):
        self.arguments = arguments

    def get_argument(self, name):
        if name in self.arguments:
            return self.arguments[name]
        raise MissingArgumentError(name)


class TestParameterTypeString(unittest.TestCase):
    """Test the class ParameterTypeString."""

    def setUp(self):
        super().setUp()
        self.p = ParameterTypeString("name", "shortname", "description")

    def test_validate_success(self):
        self.p.validate("asd")
        self.p.validate("中文")

    def test_validate_failure(self):
        with self.assertRaises(ValueError):
            self.p.validate(1)
        with self.assertRaises(ValueError):
            self.p.validate(["asd"])

    def test_validate_failure_bytes(self):
        with self.assertRaises(ValueError):
            self.p.validate(b"asd")

    def test_parse_string(self):
        self.assertEqual(self.p.parse_string("asd"), "asd")
        self.assertEqual(self.p.parse_string("中文"), "中文")

    def test_parse_handler(self):
        h = FakeHandler({
            "prefix_shortname": "correct prefix",
            "prefix_name": "incorrect",
            "shortname": "correct no prefix",
            "name": "incorrect",
        })
        self.assertEqual(self.p.parse_handler(h, "prefix_"), "correct prefix")
        self.assertEqual(self.p.parse_handler(h, ""), "correct no prefix")
        with self.assertRaises(MissingArgumentError):
            self.p.parse_handler(h, "wrong prefix")


class TestParameterTypeInt(unittest.TestCase):
    """Test the class ParameterTypeInt."""

    def setUp(self):
        super().setUp()
        self.p = ParameterTypeInt("name", "shortname", "description")

    def test_validate_success(self):
        self.p.validate(1)
        self.p.validate(-1)
        self.p.validate(0)
        self.p.validate(2**34)

    def test_validate_failure_wrong_type(self):
        with self.assertRaises(ValueError):
            self.p.validate("1")
        with self.assertRaises(ValueError):
            self.p.validate(1.0)
        with self.assertRaises(ValueError):
            self.p.validate(1j)
        with self.assertRaises(ValueError):
            self.p.validate([1])

    def test_parse_string(self):
        self.assertEqual(self.p.parse_string("123"), 123)
        self.assertEqual(self.p.parse_string("-123"), -123)

    def test_parse_handler(self):
        h = FakeHandler({
            "ok_shortname": "-45",
            "fail_shortname": "not an int",
        })
        self.assertEqual(self.p.parse_handler(h, "ok_"), -45)
        with self.assertRaises(ValueError):
            self.p.parse_handler(h, "fail_")
        with self.assertRaises(MissingArgumentError):
            self.p.parse_handler(h, "missing_")


class TestParameterTypeChoice(unittest.TestCase):
    """Test the class ParameterTypeChoice."""

    def setUp(self):
        super().setUp()
        self.p = ParameterTypeChoice("name", "shortname", "description", {
            "c1": "First choice",
            "c2": "Second choice",
        })

    def test_validate_success(self):
        self.p.validate("c1")
        self.p.validate("c2")

    def test_validate_failure_wrong_type(self):
        with self.assertRaises(ValueError):
            self.p.validate("c3")
        with self.assertRaises(ValueError):
            self.p.validate(["c1"])

    def test_parse_string(self):
        self.assertEqual(self.p.parse_string("c1"), "c1")
        with self.assertRaises(ValueError):
            self.p.parse_string("c3")

    def test_parse_handler(self):
        h = FakeHandler({
            "ok_shortname": "c2",
            "fail_shortname": "c3",
        })
        self.assertEqual(self.p.parse_handler(h, "ok_"), "c2")
        with self.assertRaises(ValueError):
            self.p.parse_handler(h, "fail_")
        with self.assertRaises(MissingArgumentError):
            self.p.parse_handler(h, "missing_")


class TestParameterTypeCollection(unittest.TestCase):
    """Test the class ParameterTypeCollection."""

    def setUp(self):
        super().setUp()
        self.p = ParameterTypeCollection("name", "shortname", "description", [
            ParameterTypeInt("name0", "shortname0", "desc0"),
            ParameterTypeString("name1", "shortname1", "desc1"),
            ParameterTypeChoice("name2", "shortname2", "desc2", {
                "c1": "First choice",
                "c2": "Second choice",
            })])

    def test_validate_success(self):
        self.p.validate([1, "2", "c1"])
        self.p.validate([-1, "asd", "c1"])

    def test_validate_failure_wrong_type(self):
        with self.assertRaises(ValueError):
            self.p.validate((1, "2", "c1"))
        with self.assertRaises(ValueError):
            self.p.validate(["1", "2", "c1"])

    def test_parse_handler(self):
        h = FakeHandler({
            "ok_shortname_0_shortname0": "1",
            "ok_shortname_1_shortname1": "1",
            "ok_shortname_2_shortname2": "c1",
            "missing_shortname_0_shortname0": "1",
            "wrong_shortname_0_shortname0": "1",
            "wrong_shortname_1_shortname1": "1",
            "wrong_shortname_2_shortname2": "c3",
        })
        self.assertEqual(self.p.parse_handler(h, "ok_"), [1, "1", "c1"])
        with self.assertRaises(ValueError):
            self.p.parse_handler(h, "wrong_")
        with self.assertRaises(MissingArgumentError):
            self.p.parse_handler(h, "missing_")


if __name__ == "__main__":
    unittest.main()
