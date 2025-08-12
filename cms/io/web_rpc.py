#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2013-2016 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2015 Stefano Maggiolo <s.maggiolo@gmail.com>
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

import json
import logging
from typing import Callable

from werkzeug.exceptions import HTTPException, BadRequest, Forbidden, \
    NotFound, NotAcceptable, UnsupportedMediaType, ServiceUnavailable
from werkzeug.routing import Map, Rule
from werkzeug.wrappers import Request, Response
from werkzeug.wsgi import responder

from cms import ServiceCoord
from cms.io.service import Service


logger = logging.getLogger(__name__)


class RPCMiddleware:
    """An HTTP interface to the internal RPC communications.

    This WSGI application provides a synchronous and unfiltered access,
    over an HTTP transport, to all remote services and all their RPC
    methods. Each of them can be called by making a POST request to the
    URL "/<service>/<shard>/<method>" where "<service>" is the name of
    the remote service (i.e. the name of the class), "<shard>" is the
    shard of the instance and "<method>" is the name of the method.

    POST has been used because it's neither a safe nor an idempotent
    method (see HTTP spec.) and is therefore less restricted in what
    clients expect it to do than a GET.

    Arguments for the RPC should be given as JSON-encoded object in the
    request body (should always be present, even if empty).

    A standard error code will be returned for all client-to-WSGI-app
    errors (mostly communication errors: the client didn't declare it
    produces and consumes JSON or the JSON was invalid). A 404 will be
    returned if the requested remote service isn't found in the list of
    remote services that the service we're proxying for knows about. A
    503 status code means that, at the moment, there's no connection to
    the remote service.

    As soon as the RPC has been sent, the HTTP request is considered
    successful (i.e. status code 200). The response body will contain
    a JSON object with two fields: data and error (possibly null). The
    first contains the JSON-encoded result of the RPC, the second a
    string describing the error that occured (if any).

    """
    def __init__(
        self, service: Service, auth: Callable[[str, int, str], bool] | None = None
    ):
        """Create an HTTP-to-RPC proxy for the given service.

        service: the service this application is running for.
            Will usually be the AdminWebServer.
        auth: a function taking the environ of a request
            and returning whether the request is allowed. If not present,
            all requests are allowed.

        """
        self._service = service
        self._auth = auth
        self._url_map = Map([Rule("/<service>/<int:shard>/<method>",
                                  methods=["POST"], endpoint="rpc")],
                            encoding_errors="strict")

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
        urls = self._url_map.bind_to_environ(environ)
        try:
            endpoint, args = urls.match()
        except HTTPException as exc:
            return exc

        assert endpoint == "rpc"

        remote_service = ServiceCoord(args['service'], args['shard'])

        if remote_service not in self._service.remote_services:
            return NotFound()

        if self._auth is not None and not self._auth(
                args['service'], args['shard'], args['method']):
            return Forbidden()

        request = Request(environ)
        request.encoding_errors = "strict"

        # TODO Check content_encoding and content_md5.

        if request.mimetype != "application/json":
            return UnsupportedMediaType()

        if request.accept_mimetypes.quality("application/json") <= 0:
            return NotAcceptable()

        try:
            data = json.load(request.stream)
        except ValueError:
            return BadRequest()

        if not self._service.remote_services[remote_service].connected:
            return ServiceUnavailable()

        result = self._service.remote_services[remote_service].execute_rpc(
            args['method'], data)

        result.wait(timeout=60)

        response = Response()

        response.status_code = 200
        response.mimetype = "application/json"
        response.data = json.dumps({
            "data": result.value,
            "error": None if result.successful() else "%s" % result.exception})

        return response
