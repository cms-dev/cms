#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2021 Manuel Gundlach <manuel.gundlach@gmail.com>
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

from werkzeug.exceptions import HTTPException, NotFound, ServiceUnavailable
from werkzeug.wrappers import Response, Request
from werkzeug.wsgi import responder, wrap_file

from cms.db.filecacher import FileCacher, TombstoneError


class FileServerMiddleware:
    """Intercept requests wanting to serve files and serve those files.

    Tornado's WSGI adapter contravenes the specification by buffering
    the entire output produced by a handler rather than streaming it
    down as soon as it's available (even when an explicit flush is
    issued). This is especially problematic when serving files, as it
    causes them to be entirely loaded into memory, providing a vector
    for a denial-of-service attack.

    This class is one half of a two-part solution to this problem. When
    a Tornado handler wants to serve a file it instead serves an empty
    response with custom headers. This middleware looks out for
    responses of that form and, when it encounters one, it fetches and
    streams back the file that was requested, using a proper compliant
    way.

    """

    DIGEST_HEADER = "X-CMS-File-Digest"
    FILENAME_HEADER = "X-CMS-File-Filename"

    def __init__(self, file_cacher, app):
        """Create an instance.

        file_cacher (FileCacher): the cacher to retrieve files from.
        app (function): the WSGI application to wrap.

        """
        self.file_cacher = file_cacher
        self.wrapped_app = app

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
        original_response = Response.from_app(self.wrapped_app, environ)
        # We send relative locations to play nice with reverse proxies
        # but Werkzeug by default turns them into absolute ones.
        original_response.autocorrect_location_header = False

        if self.DIGEST_HEADER not in original_response.headers:
            return original_response

        digest = original_response.headers.pop(self.DIGEST_HEADER)
        filename = original_response.headers.pop(self.FILENAME_HEADER, None)
        mimetype = original_response.mimetype

        try:
            fobj = self.file_cacher.get_file(digest)
            size = self.file_cacher.get_size(digest)
        except KeyError:
            return NotFound()
        except TombstoneError:
            return ServiceUnavailable()

        request = Request(environ)
        request.encoding_errors = "strict"

        response = Response()
        response.status_code = 200
        response.mimetype = mimetype
        if filename is not None:
            response.headers.add(
                "Content-Disposition", "attachment", filename=filename)
        response.set_etag(digest)
        response.cache_control.no_cache = True
        response.cache_control.private = True
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
