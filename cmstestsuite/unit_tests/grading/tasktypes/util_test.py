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

"""Tests for the utilities for task types."""

import unittest

from cms.grading import Language
from cms.grading.tasktypes import is_manager_for_compilation


class TestLanguage(Language):
    """Test language"""

    @property
    def name(self):
        return "TestLanguage"

    def get_evaluation_commands(
            self, executable_filename, main=None, args=None):
        pass

    def get_compilation_commands(
            self, source_filenames, executable_filename, for_evaluation=True):
        pass

    @property
    def source_extensions(self):
        return [".srcext1", ".srcext2"]

    @property
    def header_extensions(self):
        return [".headext1", ".headext2"]

    @property
    def object_extensions(self):
        return [".objext1", ".objext2"]


class TestIsManagerForCompilation(unittest.TestCase):
    """Test the function is_manager_for_compilation."""

    def setUp(self):
        super().setUp()
        # We will always use this language.
        self.lang = TestLanguage()

    def assertIsForCompilation(self, filename):
        self.assertTrue(is_manager_for_compilation(filename, self.lang))

    def assertIsNotForCompilation(self, filename):
        self.assertFalse(is_manager_for_compilation(filename, self.lang))

    def test_is_manager_for_compilation(self):
        # Any file with an extension defined in the language is interesting.
        self.assertIsForCompilation("test.srcext1")
        self.assertIsForCompilation("test.srcext2")
        self.assertIsForCompilation("test.headext1")
        self.assertIsForCompilation("test.headext2")
        self.assertIsForCompilation("test.objext1")
        self.assertIsForCompilation("test.objext2")

    def test_is_basename_empty(self):
        self.assertIsForCompilation(".srcext2")

    def test_is_not(self):
        # Some easy cases.
        self.assertIsNotForCompilation("test.c")
        self.assertIsNotForCompilation("test")
        self.assertIsNotForCompilation("")

    def test_is_not_extension_somewhere_else(self):
        # Extension is in file but not at the right place
        self.assertIsNotForCompilation("srcext1")
        self.assertIsNotForCompilation("test.srcext1.c")
        self.assertIsNotForCompilation("test.srcext1.")


if __name__ == "__main__":
    unittest.main()
