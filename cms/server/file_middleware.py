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
from six import itervalues

import re
import string

import xdg.Mime
from werkzeug.exceptions import HTTPException, BadRequest, NotFound, \
    ServiceUnavailable

from werkzeug.routing import Map, Rule, BaseConverter
from werkzeug.wrappers import Response, Request
from werkzeug.wsgi import responder, wrap_file

from cms.db.filecacher import FileCacher, TombstoneError


SECONDS_IN_A_YEAR = 365 * 24 * 60 * 60


class DigestConverter(BaseConverter):
    def __init__(self, url_map):
        super(DigestConverter, self).__init__(url_map)
        self.regex = '[0-9A-Fa-f]{40}'

    def to_python(self, value):
        return value.lower()


class FilenameConverter(BaseConverter):
    def __init__(self, url_map):
        super(FilenameConverter, self).__init__(url_map)
        self.regex = '[%s]+' % re.escape(string.printable.replace('/', ''))


class FileByDigestMiddleware(object):
    def __init__(self, file_cacher):
        """Create an instance.

        file_cacher (FileCacher): the cacher to retrieve files from.

        """
        self.file_cacher = file_cacher
        self.url_map = Map([Rule("/<digest:digest>/<filename:filename>",
                                 methods=["GET"], endpoint="fetch")],
                           encoding_errors="strict",
                           converters={"digest": DigestConverter,
                                       "filename": FilenameConverter})
        xdg.Mime.update_cache()
        self.valid_mimetypes = set(str(t) for t in itervalues(xdg.Mime.types))

    def __call__(self, environ, start_response):
        """Execute this instance as a WSGI application.

        See the PEP for the meaning of parameters. The separation of
        __call__ and wsgi_app eases the insertion of middlewares.

        """
        return self.wsgi_app(environ, start_response)

    @responder
    def wsgi_app(self, environ, start_response):
        """Execute this instance as a WSGI application.

        See the PEP for the meaning of parameters. The separation of
        __call__ and wsgi_app eases the insertion of middlewares.

        """
        urls = self.url_map.bind_to_environ(environ)
        try:
            endpoint, args = urls.match()
        except HTTPException as exc:
            return exc

        assert endpoint == "fetch"

        digest = args["digest"]
        filename = args["filename"]

        try:
            fobj = self.file_cacher.get_file(digest)
            size = self.file_cacher.get_size(digest)
        except KeyError:
            return NotFound()
        except TombstoneError:
            return ServiceUnavailable()

        request = Request(environ)
        request.encoding_errors = "strict"

        # TODO maybe try to parse the beginning of the content as well?
        mimetype = request.args.get("mimetype")
        if mimetype is None:
            guessed_mimetype = xdg.Mime.get_type_by_name(filename)
            if guessed_mimetype is not None:
                mimetype = str(guessed_mimetype)
            else:
                mimetype = "application/octet-stream"
        elif mimetype not in self.valid_mimetypes:
            return BadRequest()

        response = Response()
        response.status_code = 200
        response.mimetype = mimetype
        response.headers.add(
            "Content-Disposition", "attachment", filename=filename)
        response.set_etag(digest)
        response.cache_control.max_age = SECONDS_IN_A_YEAR
        response.cache_control.public = True
        response.response = \
            wrap_file(environ, fobj, buffer_size=FileCacher.CHUNK_SIZE)
        response.direct_passthrough = True

        try:
            # This takes care of conditional and partial requests.
            response.make_conditional(
                request, accept_ranges=True, complete_length=size)
        except HTTPException as exc:
            return exc

        return response
