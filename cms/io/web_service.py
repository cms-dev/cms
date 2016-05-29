#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2015 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013-2016 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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
from __future__ import print_function
from __future__ import unicode_literals

import logging

import tornado.web
import tornado.escape
import tornado.wsgi

from gevent.pywsgi import WSGIServer

from werkzeug.wsgi import DispatcherMiddleware, SharedDataMiddleware
from werkzeug.contrib.fixers import ProxyFix

from .service import Service
from .web_rpc import RPCMiddleware


logger = logging.getLogger(__name__)


class WebService(Service):
    """RPC service with Web server capabilities.

    """

    def __init__(self, listen_port, handlers, parameters, shard=0,
                 listen_address=""):
        super(WebService, self).__init__(shard)

        static_files = parameters.pop('static_files', [])
        rpc_enabled = parameters.pop('rpc_enabled', False)
        rpc_auth = parameters.pop('rpc_auth', None)
        auth_middleware = parameters.pop('auth_middleware', None)
        is_proxy_used = parameters.pop('is_proxy_used', None)
        num_proxies_used = parameters.pop('num_proxies_used', None)

        self.wsgi_app = tornado.wsgi.WSGIApplication(handlers, **parameters)
        self.wsgi_app.service = self

        for entry in static_files:
            self.wsgi_app = SharedDataMiddleware(
                self.wsgi_app, {"/static": entry})

        if rpc_enabled:
            self.wsgi_app = DispatcherMiddleware(
                self.wsgi_app, {"/rpc": RPCMiddleware(self, rpc_auth)})

        # The authentication middleware needs to be applied before the
        # ProxyFix as otherwise the remote address it gets is the one
        # of the proxy.
        if auth_middleware is not None:
            self.wsgi_app = auth_middleware(self.wsgi_app)
            self.auth_handler = self.wsgi_app

        # If we are behind one or more proxies, we'll use the content
        # of the X-Forwarded-For HTTP header (if provided) to determine
        # the client IP address, ignoring the one the request came from.
        # This allows to use the IP lock behind a proxy. Activate it
        # only if all requests come from a trusted source (if clients
        # were allowed to directlty communicate with the server they
        # could fake their IP and compromise the security of IP lock).
        if num_proxies_used is None:
            if is_proxy_used:
                num_proxies_used = 1
            else:
                num_proxies_used = 0

        if num_proxies_used > 0:
            self.wsgi_app = ProxyFix(self.wsgi_app, num_proxies_used)

        self.web_server = WSGIServer((listen_address, listen_port),
                                     self.wsgi_app)

    def run(self):
        """Start the WebService.

        Both the WSGI server and the RPC server are started.

        """
        self.web_server.start()
        Service.run(self)
        self.web_server.stop()
