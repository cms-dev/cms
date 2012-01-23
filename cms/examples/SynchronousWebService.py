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

"""Simple web service example.

"""

import os

import tornado.web

from cms.async.Utils import decode_json
from cms.async.AsyncLibrary import logger, rpc_callback
from cms.async.WebAsyncLibrary import WebService
from cms.async import ServiceCoord
from cms.db.Utils import default_argument_parser


class SynchronousRPCRequestHandler(tornado.web.RequestHandler):

    # Asynchronous request handler. Call self.finish() to end the request.
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
            callback=self._request_callback,
            plus=0,
            **arguments)

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


class WebServiceA(WebService):
    """Simple web service example.

    """

    def __init__(self, shard):
        logger.initialize(ServiceCoord("WebServiceA", shard))
        logger.debug("WebServiceA.__init__")
        WebService.__init__(self,
            9999,
            [(r"/", MainHandler),
            (r"/sync_rpc_request/([a-zA-Z0-9_-]+)/" \
             "([0-9]+)/([a-zA-Z0-9_-]+)",
             SynchronousRPCRequestHandler)],
            {"login_url": "/",
             "template_path": "./",
             "cookie_secret": "DsEwRxZER06etXcqgfowEJuM6rZjwk1JvknlbngmNck=",
             "static_path": os.path.join(os.path.dirname(__file__),
                                         "..", "cms", "async", "static"),
             "debug": "True",
             },
            shard=shard)
        self.ServiceB = self.connect_to(ServiceCoord("ServiceB", 1))


class MainHandler(tornado.web.RequestHandler):
    """Home page handler.

    """
    def get(self):
        self.render("synchronous.html")


if __name__ == "__main__":
    default_argument_parser("Example web service A for CMS.",
                            WebServiceA).run()
