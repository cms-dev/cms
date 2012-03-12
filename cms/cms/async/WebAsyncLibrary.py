#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
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

import time
import fcntl

import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.escape

from cms.async import ServiceCoord
from cms.async.AsyncLibrary import Service, rpc_callback
from cms.async.Utils import decode_json


# Our logger. We cannot simply import from AsyncLibrary because at
# loading it is not yet defined.
logger = None


class RPCRequestHandler(tornado.web.RequestHandler):
    """This handler receives a request for a RPC method, interprets
    the request, and calls the method.

    """
    def get(self, service, shard, method):
        # TODO: still lacking configurable arguments - some of these
        # should be GET arguments.
        rid = self.get_argument("__rid")
        arguments = self.request.arguments
        del arguments["__rid"]

        # Tornado gives for every key a list of arguments, we need
        # only one
        arguments = dict((k, decode_json(arguments[k][0])) for k in arguments)

        service = ServiceCoord(service, int(shard))

        authorized = self.application.service.authorized_rpc(service,
                                                             method,
                                                             arguments)
        if not authorized:
            self.write({'status': 'not authorized'})
            return

        if service not in self.application.service.remote_services or \
               not self.application.service.remote_services[service].connected:
            self.write({'status': 'unconnected'})
            return

        self.application.service.__responses[rid] = "wait"
        self.application.service.remote_services[service].__getattr__(method)(\
            callback=WebService._default_callback,
            plus=rid,
            **arguments)
        self.write({'status': 'wait'})


class RPCAnswerHandler(tornado.web.RequestHandler):
    """This handler check if a previously requested request has
    finished and inform the client of the status of the request.

    """
    def get(self):
        rid = self.get_argument("__rid")
        responses = self.application.service.__responses
        if rid in responses:
            if responses[rid] == "wait":
                self.write({'status': 'wait'})
            else:
                try:
                    self.write({'status': 'ok',
                                'data': responses[rid][0],
                                'error': responses[rid][1]})
                except UnicodeDecodeError:
                    self.write({'status': 'ok',
                                'data': '',
                                'error': 'Cannot call binary RPC methods.'})
                del responses[rid]
        else:
            self.write({'status': 'fail'})


class SyncRPCRequestHandler(tornado.web.RequestHandler):
    """Using the decorator tornado.web.asynchronous, the request stays
    alive until we decide to end it (with self.finish). We use this to
    let the browser wait until we have the response for the rpc/

    """
    @tornado.web.asynchronous
    def get(self, service, shard, method):
        arguments = self.request.arguments
        # Tornado gives for every key a list of arguments, we need
        # only one
        arguments = dict((k, decode_json(arguments[k][0])) for k in arguments)

        service = ServiceCoord(service, int(shard))
        if service not in self.application.service.remote_services or \
            not self.application.service.remote_services[service].connected:
            self.write({'status': 'unconnected'})
            self.finish()
            return

        self.application.service.remote_services[service].__getattr__(method)(
            callback=self._request_callback, plus=0, **arguments)

    @rpc_callback
    def _request_callback(self, caller, data, plus, error=None):
        try:
            self.write({'status': 'ok',
                        'data': data,
                        'error': error})
        except UnicodeDecodeError:
            self.write({'status': 'ok',
                        'data': '',
                        'error': 'Cannot call binary RPC methods.'})
        self.finish()


class WebService(Service):
    """Example of a RPC service that is also a tornado webserver.

    """

    def __init__(self, listen_port, handlers, parameters, shard=0,
                 custom_logger=None, listen_address=""):
        Service.__init__(self, shard, custom_logger)

        global logger
        from cms.async.AsyncLibrary import logger as _logger
        logger = _logger

        # This ensures that when the server autoreloads because its source is
        # modified, the socket is closed correctly.
        # In the development branch of Tornado, you can add a hook before
        # the server reloads.

        try:
            if parameters["debug"]:
                fcntl.fcntl(self.server.socket,
                            fcntl.F_SETFD, fcntl.FD_CLOEXEC)
        except KeyError:
            pass

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
        self.application = tornado.web.Application(handlers, **parameters)

        # xheaders=True means that Tornado uses the content of the
        # header X-Real-IP as the request IP. This means that if it is
        # behind a proxy, it can see the real IP the request is coming
        # from. But, to use it, we need to be sure we can trust it
        # (i.e., if we are not behind a proxy that sets that header,
        # we must not use it).
        self.application.service = self
        http_server = tornado.httpserver.HTTPServer(
            self.application, xheaders=parameters.get("is_proxy_used", True))
        http_server.listen(listen_port, address=listen_address)
        self.instance = tornado.ioloop.IOLoop.instance()

    def exit(self):
        """Terminate the service at the next step.

        """
        self.instance.stop()
        self._exit = True
        logger.warning("%s %d dying in 3, 2, 1..." % self._my_coord)

    def run(self):
        """Starts the tornado server (hence the tornado and asyncore
        loops).

        """
        try:
            # TODO: to have a less hacky collaboration between tornado
            # and asyncore, we may use a solution similar to the one
            # in https://gist.github.com/338680
            self.instance.add_callback(self._webstep)
            self.instance.start()
        except KeyboardInterrupt:
            pass

    def _webstep(self):
        """Takes care of calling one step of the loop of asyncore, and
        to execute one (or more) step of the tornado loop.

        """
        self._step(maximum=0.02)
        self.instance.add_timeout(time.time() + 0.01, self._webstep)

    @rpc_callback
    def _default_callback(self, data, plus, error=None):
        """This is the callback for the RPC method called from a web
        page, that just collect the response.

        """
        self.__responses[plus] = (data, error)
