#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

from werkzeug.wsgi import DispatcherMiddleware
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

        self.wsgi_app = tornado.wsgi.WSGIApplication(handlers, **parameters)
        self.wsgi_app.service = self

        if parameters.get('rpc_enabled', False):
            self.wsgi_app = DispatcherMiddleware(
                self.wsgi_app, {"/rpc": RPCMiddleware(self)})

        # If is_proxy_used is set to True we'll use the content of the
        # X-Forwarded-For HTTP header (if provided) to determine the
        # client IP address, ignoring the one the request came from.
        # This allows to use the IP lock behind a proxy. Activate it
        # only if all requests come from a trusted source (if clients
        # were allowed to directlty communicate with the server they
        # could fake their IP and compromise the security of IP lock).
        if parameters.get('is_proxy_used', False):
            self.wsgi_app = ProxyFix(self.wsgi_app)

        self.web_server = WSGIServer((listen_address, listen_port),
                                     self.wsgi_app)

    def run(self):
        """Start the WebService.

        Both the WSGI server and the RPC server are started.

        """
        self.web_server.start()
        Service.run(self)
        self.web_server.stop()
