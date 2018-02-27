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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *
from future.builtins import *

import hashlib
import io
import random
import unittest

from mock import Mock
from werkzeug.http import quote_header_value
from werkzeug.test import Client
from werkzeug.wrappers import Response

from cmscommon.binary import bin_to_hex
from cms.db.filecacher import TombstoneError
from cms.server.file_middleware import FileByDigestMiddleware


class TestFileByDigestMiddleware(unittest.TestCase):

    def setUp(self):
        # We need to wrap the generator in a list because of a
        # shortcoming of future's bytes implementation.
        self.content = bytes([random.getrandbits(8) for _ in range(1024)])
        hasher = hashlib.sha1()
        hasher.update(self.content)
        self.digest = bin_to_hex(hasher.digest())

        self.file_cacher = Mock()
        self.file_cacher.get_file = Mock(
            side_effect=lambda digest: io.BytesIO(self.content))
        self.file_cacher.get_size = Mock(return_value=len(self.content))

        self.wsgi_app = FileByDigestMiddleware(self.file_cacher)
        self.client = Client(self.wsgi_app, Response)

    def test_success(self):
        filename = "foobar.sh"
        # Use a MIME type that doesn't match the extension.
        mimetype = "image/jpeg"
        # Test with an uppercase digest.
        response = self.client.get("/%s/%s" % (self.digest.upper(), filename),
                                   query_string={"mimetype": mimetype})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, mimetype)
        self.assertEqual(
            response.headers.get("content-disposition"),
            "attachment; filename=%s" % quote_header_value(filename))
        self.assertTupleEqual(response.get_etag(), (self.digest, False))
        self.assertEqual(response.accept_ranges, "bytes")
        self.assertGreater(response.cache_control.max_age, 0)
        self.assertTrue(response.cache_control.public)
        self.assertEqual(response.data, self.content)

        self.file_cacher.get_file.assert_called_once_with(self.digest)

    def test_mimetype_guessing(self):
        filenames_and_mimetypes = [
            ("foobar.c", "text/x-csrc"),
            ("foobar.pdf", "application/pdf"),
            ("foobar.tar.gz", "application/x-compressed-tar"),
            ("foobar", "application/octet-stream")]

        for filename, mimetype in filenames_and_mimetypes:
            response = self.client.get("/%s/%s" % (self.digest, filename))

            self.assertEqual(response.mimetype, mimetype)

            self.file_cacher.get_file.assert_called_once_with(self.digest)
            self.file_cacher.get_file.reset_mock()

    def test_not_found(self):
        self.file_cacher.get_file.side_effect = KeyError()

        response = self.client.get("/%s/%s" % (self.digest, "foobar.py"))

        self.assertEqual(response.status_code, 404)

        self.file_cacher.get_file.assert_called_once_with(self.digest)

    def test_tombstone(self):
        self.file_cacher.get_file.side_effect = TombstoneError()

        response = self.client.get("/%s/%s" % (self.digest, "foobar.txt"))

        self.assertEqual(response.status_code, 503)

        self.file_cacher.get_file.assert_called_once_with(self.digest)

    def test_bad_path(self):
        response = self.client.get("/bad_path")
        self.assertEqual(response.status_code, 404)

        response = self.client.get("/bad_digest/foobar.exe")
        self.assertEqual(response.status_code, 404)

        response = self.client.get("/%s/path/with/slashes" % self.digest)
        self.assertEqual(response.status_code, 404)

        response = self.client.get("/%s/\N{NULL}" % self.digest)
        self.assertEqual(response.status_code, 404)

        response = self.client.get("/%s/\N{BELL}" % self.digest)
        self.assertEqual(response.status_code, 404)

        self.file_cacher.get_file.assert_not_called()

    def test_bad_method(self):
        response = self.client.post("/%s/%s" % (self.digest, "foobar.java"))
        self.assertEqual(response.status_code, 405)

        response = self.client.put("/%s/%s" % (self.digest, "foobar.doc"))
        self.assertEqual(response.status_code, 405)

        response = self.client.delete("/%s/%s" % (self.digest, "foobar.rar"))
        self.assertEqual(response.status_code, 405)

        self.file_cacher.get_file.assert_not_called()

    def test_invalid_mimetype(self):
        response = self.client.get("/%s/%s" % (self.digest, "foobar"),
                                   query_string={"mimetype": "not/a/mimetype"})
        self.assertEqual(response.status_code, 400)

        # Needs to call this anyways to make sure the file exists: if
        # it didn't it would have to return a 404 error.
        self.file_cacher.get_file.assert_called_once_with(self.digest)

    def test_conditional_request(self):
        # Test an etag that matches.
        response = self.client.get("/%s/%s" % (self.digest, "foobar"),
                                   headers=[("If-None-Match", self.digest)])
        self.assertEqual(response.status_code, 304)
        self.assertEqual(len(response.data), 0)

        # Test an etag that doesn't match.
        response = self.client.get("/%s/%s" % (self.digest, "foobar"),
                                   headers=[("If-None-Match", "not the etag")])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.content)

    def test_range_request(self):
        # Test a range that is strictly included.
        response = self.client.get("/%s/%s" % (self.digest, "foobar"),
                                   headers=[("Range", "bytes=256-767")])
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.content_range.units, "bytes")
        self.assertEqual(response.content_range.start, 256)
        self.assertEqual(response.content_range.stop, 768)
        self.assertEqual(response.content_range.length, 1024)
        self.assertEqual(response.data, self.content[256:768])

        # Test a range that ends after the end of the file.
        response = self.client.get("/%s/%s" % (self.digest, "foobar"),
                                   headers=[("Range", "bytes=256-2047")])
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.content_range.units, "bytes")
        self.assertEqual(response.content_range.start, 256)
        self.assertEqual(response.content_range.stop, 1024)
        self.assertEqual(response.content_range.length, 1024)
        self.assertEqual(response.data, self.content[256:])

        # Test a range that starts after the end of the file.
        response = self.client.get("/%s/%s" % (self.digest, "foobar"),
                                   headers=[("Range", "bytes=1536-")])
        self.assertEqual(response.status_code, 416)


if __name__ == "__main__":
    unittest.main()
