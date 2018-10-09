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

import io
import random
import unittest
from unittest.mock import Mock

from werkzeug.http import quote_header_value
from werkzeug.test import Client, EnvironBuilder
from werkzeug.wrappers import Response
from werkzeug.wsgi import responder

from cms.db.filecacher import TombstoneError
from cms.server.file_middleware import FileServerMiddleware
from cmscommon.digest import bytes_digest


class TestFileByDigestMiddleware(unittest.TestCase):

    def setUp(self):
        # Choose a size that is larger than FileCacher.CHUNK_SIZE.
        self.content = \
            bytes(random.getrandbits(8) for _ in range(17 * 1024))
        self.digest = bytes_digest(self.content)

        self.filename = "foobar.pdf"
        self.mimetype = "image/jpeg"

        self.file_cacher = Mock()
        self.file_cacher.get_file = Mock(
            side_effect=lambda digest: io.BytesIO(self.content))
        self.file_cacher.get_size = Mock(return_value=len(self.content))

        self.serve_file = True
        self.provide_filename = True

        self.wsgi_app = \
            FileServerMiddleware(self.file_cacher,self.wrapped_wsgi_app)
        self.environ_builder = EnvironBuilder("/some/url")
        self.client = Client(self.wsgi_app, Response)

    @responder
    def wrapped_wsgi_app(self, environ, start_response):
        self.assertEqual(environ, self.environ)
        if self.serve_file:
            headers = {FileServerMiddleware.DIGEST_HEADER: self.digest}
            if self.provide_filename:
                headers[FileServerMiddleware.FILENAME_HEADER] = self.filename
            return Response(headers=headers, mimetype=self.mimetype)
        else:
            return Response(b"some other content", mimetype="text/plain")

    def request(self, headers=None):
        if headers is not None:
            for key, value in headers:
                self.environ_builder.headers.add(key, value)
        self.environ = self.environ_builder.get_environ()
        return self.client.open(self.environ)

    def test_success(self):
        response = self.request()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, self.mimetype)
        self.assertEqual(
            response.headers.get("content-disposition"),
            "attachment; filename=%s" % quote_header_value(self.filename))
        self.assertTupleEqual(response.get_etag(), (self.digest, False))
        self.assertEqual(response.accept_ranges, "bytes")
        self.assertGreater(response.cache_control.max_age, 0)
        self.assertTrue(response.cache_control.private)
        self.assertFalse(response.cache_control.public)
        self.assertEqual(response.get_data(), self.content)

        self.file_cacher.get_file.assert_called_once_with(self.digest)

    def test_not_a_file(self):
        self.serve_file = False

        response = self.request()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/plain")
        self.assertEqual(response.get_data(), b"some other content")

    def test_no_filename(self):
        self.provide_filename = False

        response = self.request()

        self.assertNotIn("content-disposition", response.headers)

    def test_not_found(self):
        self.file_cacher.get_file.side_effect = KeyError()

        response = self.request()

        self.assertEqual(response.status_code, 404)
        self.file_cacher.get_file.assert_called_once_with(self.digest)

    def test_tombstone(self):
        self.file_cacher.get_file.side_effect = TombstoneError()

        response = self.request()

        self.assertEqual(response.status_code, 503)
        self.file_cacher.get_file.assert_called_once_with(self.digest)

    def test_conditional_request(self):
        # Test an etag that matches.
        response = self.request(headers=[("If-None-Match", self.digest)])
        self.assertEqual(response.status_code, 304)
        self.assertEqual(len(response.get_data()), 0)

    def test_conditional_request_no_match(self):
        # Test an etag that doesn't match.
        response = self.request(headers=[("If-None-Match", "not the etag")])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(), self.content)

    def test_range_request(self):
        # Test a range that is strictly included.
        response = self.request(headers=[("Range", "bytes=256-767")])
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.content_range.units, "bytes")
        self.assertEqual(response.content_range.start, 256)
        self.assertEqual(response.content_range.stop, 768)
        self.assertEqual(response.content_range.length, 1024)
        self.assertEqual(response.get_data(), self.content[256:768])

    def test_range_request_end_overflows(self):
        # Test a range that ends after the end of the file.
        response = self.request(headers=[("Range", "bytes=256-2047")])
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.content_range.units, "bytes")
        self.assertEqual(response.content_range.start, 256)
        self.assertEqual(response.content_range.stop, 1024)
        self.assertEqual(response.content_range.length, 1024)
        self.assertEqual(response.get_data(), self.content[256:])

    def test_range_request_start_overflows(self):
        # Test a range that starts after the end of the file.
        response = self.request(headers=[("Range", "bytes=1536-")])
        self.assertEqual(response.status_code, 416)


if __name__ == "__main__":
    unittest.main()
