#!/usr/bin/env python3

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

"""Tests for printing functions.

"""

import unittest
from collections import namedtuple
from unittest.mock import Mock, patch

# Needs to be first to allow for monkey patching the DB connection string.
from cmstestsuite.unit_tests.databasemixin import DatabaseMixin

from cms import config
from cms.db import PrintJob
from cms.server.contest.printing import accept_print_job, \
    UnacceptablePrintJob, PrintingDisabled
from cmscommon.datetime import make_datetime
from cmscommon.digest import bytes_digest


MockHTTPFile = namedtuple("FakeHTTPFile", ["filename", "body"])


FILE_CONTENT = b"this is a pdf file"
FILE_DIGEST = bytes_digest(FILE_CONTENT)


@patch.object(config, "printer", "not none")
class TestAcceptPrintJob(DatabaseMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.file_cacher = Mock()
        self.file_cacher.put_file_content.return_value = FILE_DIGEST
        self.timestamp = make_datetime()
        self.contest = self.add_contest()
        self.user = self.add_user()
        self.participation = self.add_participation(
            contest=self.contest, user=self.user)

    def call(self, files):
        return accept_print_job(self.session, self.file_cacher,
                                self.participation, self.timestamp, files)

    def test_success(self):
        pj = self.call({"file": [MockHTTPFile("myfile.pdf", FILE_CONTENT)]})
        self.assertIsNotNone(pj)
        query = self.session.query(PrintJob) \
            .filter(PrintJob.filename == pj.filename)
        self.assertIs(query.first(), pj)
        self.file_cacher.put_file_content.assert_called_with(
            FILE_CONTENT, "Print job sent by %s at %s." % (self.user.username,
                                                           self.timestamp))

    def test_printing_not_allowed(self):
        with patch.object(config, "printer", None):
            with self.assertRaises(PrintingDisabled):
                self.call({"file": [MockHTTPFile("myfile.pdf", FILE_CONTENT)]})

    def test_bad_files(self):
        with self.assertRaises(UnacceptablePrintJob):
            self.call(dict())
        with self.assertRaises(UnacceptablePrintJob):
            self.call({"not file": [MockHTTPFile("foo.txt", "sth")]})
        with self.assertRaises(UnacceptablePrintJob):
            self.call({"file": [MockHTTPFile("myfile.pdf", "good content")],
                       "not file": [MockHTTPFile("foo.txt", "other content")]})
        with self.assertRaises(UnacceptablePrintJob):
            self.call({"file": []})
        with self.assertRaises(UnacceptablePrintJob):
            self.call({"file": [MockHTTPFile("myfile.pdf", "good content"),
                                MockHTTPFile("foo.txt", "other content")]})

    def test_storage_failure(self):
        self.file_cacher.put_file_content.side_effect = OSError("sth wrong")
        with self.assertRaises(UnacceptablePrintJob):
            self.call({"file": [MockHTTPFile("myfile.pdf", FILE_CONTENT)]})

    @patch.object(config, "max_print_length", len(FILE_CONTENT) - 1)
    def test_file_too_big(self):
        with self.assertRaises(UnacceptablePrintJob):
            self.call({"file": [MockHTTPFile("myfile.pdf", FILE_CONTENT)]})

    @patch.object(config, "max_jobs_per_user", 1)
    def test_too_many_print_jobs(self):
        self.call({"file": [MockHTTPFile("myfile.pdf", FILE_CONTENT)]})
        with self.assertRaises(UnacceptablePrintJob):
            self.call({"file": [MockHTTPFile("myfile.pdf", FILE_CONTENT)]})


if __name__ == "__main__":
    unittest.main()
