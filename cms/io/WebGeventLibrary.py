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

"""This file defines classes with common code to add Web server
capabilities to a RPC service.

"""

import logging

import tornado.web
import tornado.escape
import tornado.wsgi

from gevent.pywsgi import WSGIServer
from gevent.event import Event

from cms.io import ServiceCoord
from cms.io.GeventLibrary import Service, rpc_callback
from cms.io.Utils import decode_json


logger = logging.getLogger(__name__)


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
                not self.application.service.remote_services[service].\
                connected:
            self.write({'status': 'unconnected'})
            return

        self.application.service.__responses[rid] = "wait"
        self.application.service.remote_services[service].__getattr__(method)(
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
                # XXX - It is belived that this exception block was
                # added when we supported binary requests and it is
                # not needed anymore. Check it.
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
    def get(self, service, shard, method):
        arguments = self.request.arguments
        # Tornado gives for every key a list of arguments, we need
        # only one
        arguments = dict((k, decode_json(arguments[k][0])) for k in arguments)

        service = ServiceCoord(service, int(shard))
        if service not in self.application.service.remote_services or \
                not self.application.service.remote_services[service].\
                connected:
            self.write({'status': 'unconnected'})
            self.finish()
            return

        # TODO - So far we have no support for synchronous calls, so I
        # use an Event to delay the termination of this greenlet
        event = Event()
        event.clear()

        self.application.service.remote_services[service].__getattr__(method)(
            callback=self._request_callback, plus=event, **arguments)

        event.wait()

    @rpc_callback
    def _request_callback(self, caller, data, plus, error=None):
        event = plus
        try:
            self.write({'status': 'ok',
                        'data': data,
                        'error': error})
        except UnicodeDecodeError:
            self.write({'status': 'ok',
                        'data': '',
                        'error': 'Cannot call binary RPC methods.'})
        self.finish()
        event.set()


class WebService(Service):
    """RPC service with Web server capabilities.

    """

    def __init__(self, listen_port, handlers, parameters, shard=0,
                 listen_address=""):
        Service.__init__(self, shard)

        self.__responses = {}
        # TODO: why are the following two lines needed?
        self._RPCRequestHandler__responses = self.__responses
        self._RPCAnswerHandler__responses = self.__responses
        handlers += [(r"/rpc_request/([a-zA-Z0-9_-]+)/"
                      "([0-9]+)/([a-zA-Z0-9_-]+)",
                      RPCRequestHandler),
                     (r"/rpc_answer", RPCAnswerHandler),
                     (r"/sync_rpc_request/([a-zA-Z0-9_-]+)/"
                      "([0-9]+)/([a-zA-Z0-9_-]+)",
                      SyncRPCRequestHandler)]
        self.application = tornado.wsgi.WSGIApplication(handlers, **parameters)
        self.application.service = self

        # is_proxy_used=True means the content of the header X-Real-IP
        # is interpreted as the request IP. This means that if we're
        # behind a proxy, it can see the real IP the request is coming
        # from. But, to use it, we need to be sure we can trust it
        # (i.e., if we are not behind a proxy that sets that header,
        # we must not use it).
        real_application = self.application
        if parameters.get('is_proxy_used', False):
            real_application = WSGIXheadersMiddleware(real_application)

        self.web_server = WSGIServer((listen_address, listen_port),
                                     real_application)

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


class WSGIXheadersMiddleware(object):
    """WSGI middleware to detect X-Real-IP and X-Forwarded-For
    headers.

    environ['REMOTE_ADDR'] is set accordingly.

    """

    def __init__(self, app):
        """Build a wrapper around a WSGI application.

        app (WSGI application): the original application.

        """
        self.app = app

    def __call__(self, environ, start_response):
        """Handle WSGI call.

        Mangle environ['REMOTE_ADDR'] and forward the call to the
        original application.

        """
        # X-Forwarded-For: client_ip, proxy1_ip, proxy2_ip, ...
        if 'HTTP_X_FORWARDED_FOR' in environ:
            environ['REMOTE_ADDR'] = environ['HTTP_X_FORWARDED_FOR']. \
                split(',')[-1].strip()

        # X-Real-Ip: client_ip
        elif 'HTTP_X_REAL_IP' in environ:
            environ['REMOTE_ADDR'] = environ['HTTP_X_REAL_IP']

        else:
            logger.error("is_proxy_used=True, but no proxy headers detected; "
                         "probably no proxy is actually used, and this may "
                         "bring to security issues")

        return self.app(environ, start_response)
