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

"""Tests for the AddStatement script"""

import unittest

# Needs to be first to allow for monkey patching the DB connection string.
from cmstestsuite.unit_tests.databasemixin import DatabaseMixin

from cms.db import Statement
from cmscommon.digest import bytes_digest
from cmscontrib.AddStatement import add_statement
from cmstestsuite.unit_tests.filesystemmixin import FileSystemMixin


_CONTENT_1 = b"this is a pdf"
_CONTENT_2 = b"this is another pdf"
_DIGEST_1 = bytes_digest(_CONTENT_1)
_DIGEST_2 = bytes_digest(_CONTENT_2)


class TestAddStatement(DatabaseMixin, FileSystemMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()

        self.task = self.add_task()
        self.session.commit()

    def tearDown(self):
        self.delete_data()
        super().tearDown()

    def assertStatementInDb(self, language, digest):
        """Assert that the statement with the given data is in the DB."""
        db_statements = self.session.query(Statement)\
            .filter(Statement.task_id == self.task.id)\
            .filter(Statement.language == language).all()
        self.assertEqual(len(db_statements), 1)
        s = db_statements[0]
        self.assertEqual(s.digest, digest)

    def assertStatementNotInDb(self, language):
        """Assert that the statement with the given data is not in the DB."""
        db_statements = self.session.query(Statement)\
            .filter(Statement.task_id == self.task.id)\
            .filter(Statement.language == language).all()
        self.assertEqual(len(db_statements), 0)

    def test_success(self):
        path = self.write_file("statement.pdf", _CONTENT_1)
        self.assertTrue(add_statement(self.task.name, "en", path, False))
        self.assertStatementInDb("en", _DIGEST_1)

    def test_success_another_statement(self):
        path = self.write_file("statement.pdf", _CONTENT_1)
        self.assertTrue(add_statement(self.task.name, "en", path, False))

        path = self.write_file("statement2.pdf", _CONTENT_2)
        self.assertTrue(add_statement(self.task.name, "zh_TW", path, False))

        self.assertStatementInDb("en", _DIGEST_1)
        self.assertStatementInDb("zh_TW", _DIGEST_2)

    def test_no_file(self):
        path = self.get_path("statement.pdf")
        self.assertFalse(add_statement(self.task.name, "en", path, False))
        self.assertStatementNotInDb("en")

    def test_not_pdf(self):
        path = self.write_file("statement.txt", _CONTENT_1)
        self.assertFalse(add_statement(self.task.name, "en", path, False))
        self.assertStatementNotInDb("en")

    def test_dont_overwrite(self):
        path = self.write_file("statement.pdf", _CONTENT_1)
        self.assertTrue(add_statement(self.task.name, "en", path, False))
        self.assertStatementInDb("en", _DIGEST_1)

        # We try to overwrite, should fail and keep the previous digest.
        path = self.write_file("statement2.pdf", _CONTENT_2)
        self.assertFalse(add_statement(self.task.name, "en", path, False))
        self.assertStatementInDb("en", _DIGEST_1)

    def test_overwrite(self):
        path = self.write_file("statement.pdf", _CONTENT_1)
        self.assertTrue(add_statement(self.task.name, "en", path, False))
        self.assertStatementInDb("en", _DIGEST_1)

        # We try to overwrite and force it.
        path = self.write_file("statement2.pdf", _CONTENT_2)
        self.assertTrue(add_statement(self.task.name, "en", path, True))
        self.assertStatementInDb("en", _DIGEST_2)


if __name__ == "__main__":
    unittest.main()
