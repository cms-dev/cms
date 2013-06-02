#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
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

"""This file defines classes to create a Tornado server that is also
an asynchronous RPC service.

"""

import tornado.web
import tornado.escape
import tornado.wsgi

from gevent.pywsgi import WSGIServer

from cms.async.GeventLibrary import Service, rpc_callback
from cms.async.WebAsyncLibrary import RPCRequestHandler, \
    RPCAnswerHandler, SyncRPCRequestHandler


# Our logger. We cannot simply import from AsyncLibrary because at
# loading it is not yet defined.
logger = None


class WebService(Service):
    """Example of a RPC service that is also a tornado webserver.

    """

    def __init__(self, listen_port, handlers, parameters, shard=0,
                 custom_logger=None, listen_address=""):
        Service.__init__(self, shard, custom_logger)

        global logger
        from cms.async.GeventLibrary import logger as _logger
        logger = _logger

        # This ensures that when the server autoreloads because its source is
        # modified, the socket is closed correctly.
        # In the development branch of Tornado, you can add a hook before
        # the server reloads.
        # TODO - Verify this in the new setup (in particularly, does
        # the server still reload itself?)
        #try:
        #    if parameters["debug"]:
        #        fcntl.fcntl(self.server.socket,
        #                    fcntl.F_SETFD, fcntl.FD_CLOEXEC)
        #except KeyError:
        #    pass

        self.__responses = {}
        # TODO: why are the following two lines needed?
        self._RPCRequestHandler__responses = self.__responses
        self._RPCAnswerHandler__responses = self.__responses
        handlers += [(r"/rpc_request/([a-zA-Z0-9_-]+)/" \
                      "([0-9]+)/([a-zA-Z0-9_-]+)",
                      RPCRequestHandler),
                     (r"/rpc_answer", RPCAnswerHandler),
                     (r"/sync_rpc_request/([a-zA-Z0-9_-]+)/" \
                      "([0-9]+)/([a-zA-Z0-9_-]+)",
                      SyncRPCRequestHandler)]
        self.application = tornado.wsgi.WSGIApplication(handlers, **parameters)

        # xheaders=True means that Tornado uses the content of the
        # header X-Real-IP as the request IP. This means that if it is
        # behind a proxy, it can see the real IP the request is coming
        # from. But, to use it, we need to be sure we can trust it
        # (i.e., if we are not behind a proxy that sets that header,
        # we must not use it).
        # TODO - This was broken while switching to
        # gevent.pywsgi.WSGIServer
        self.application.service = self
        self.web_server = WSGIServer((listen_address, listen_port),
                                     self.application)

    def run(self):
        """Start the WebService.

        Both the WSGI server and the RPC server are started.

        """
        self.web_server.start()
        Service.run(self)
        self.web_server.stop()

    @rpc_callback
    def _default_callback(self, data, plus, error=None):
        """This is the callback for the RPC method called from a web
        page, that just collect the response.

        """
        self.__responses[plus] = (data, error)
