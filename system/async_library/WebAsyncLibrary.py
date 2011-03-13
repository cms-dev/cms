#!/usr/bin/python

"""This file defines classes to create a Tornado server that is also
an asynchronous RPC service.

"""

import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.escape

from AsyncLibrary import Service, rpc_callback, encode_json, decode_json
from Utils import ServiceCoord, log


class RPCRequestHandler(tornado.web.RequestHandler):
    """This handler receives a request for a RPC method, interprets
    the request, and call the method.

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
        if service not in self.application.service.remote_services or \
               not self.application.service.remote_services[service].connected:
            self.render("rpc_answer.html",
                        response=encode_json({'status': 'unconnected'}))
            return

        self.application.service.__responses[rid] = "wait"
        self.application.service.remote_services[service].__getattr__(method)(\
            callback=WebService._default_callback,
            plus=rid,
            **arguments)
        self.render("rpc_answer.html",
                    response=encode_json({'status': 'wait'}))


class RPCAnswerHandler(tornado.web.RequestHandler):
    """This handler check if a previously requested request has
    finished and inform the client of the status of the request.

    """
    def get(self):
        rid = self.get_argument("__rid")
        responses = self.application.service.__responses
        if rid in responses:
            if responses[rid] == "wait":
                self.render("rpc_answer.html",
                            response=encode_json({'status': 'wait'}))
            else:
                self.render("rpc_answer.html",
                            response=encode_json({'status': 'ok',
                                                  'data': responses[rid][0],
                                                  'error': responses[rid][1]}))
                del responses[rid]
        else:
            self.render("rpc_answer.html",
                        response=encode_json({'status': 'fail'}))


class WebService(Service):
    """Example of a RPC service that is also a tornado webserver.

    """

    def __init__(self, shard, listen_port, handlers, parameters):
        log.debug("WebService.__init__")
        Service.__init__(self)

        self.__responses = {}
        # TODO: why are the following two lines needed?
        self._RPCRequestHandler__responses = self.__responses
        self._RPCAnswerHandler__responses = self.__responses
        handlers += [(r"/rpc_request/([a-zA-Z0-9_-]+)/" + \
                      "([0-9]+)/([a-zA-Z0-9_-]+)",
                      RPCRequestHandler),
                     (r"/rpc_answer", RPCAnswerHandler)]
        self.application = tornado.web.Application(handlers, **parameters)

        self.application.service = self
        http_server = tornado.httpserver.HTTPServer(self.application)
        http_server.listen(listen_port)
        self.instance = tornado.ioloop.IOLoop.instance()

    def run(self):
        """Starts the tornado server (hence the tornado and asyncore
        loops).

        """
        log.debug("WebService.run")
        try:
            self.instance.add_callback(self._webstep)
            self.instance.start()
        except KeyboardInterrupt:
            pass

    def _webstep(self):
        """Takes care of calling one step of the loop of asyncore, and
        to execute one (or more) step of the tornado loop.

        """
        log.debug("WebService._webstep")
        self._step()
        self.instance.add_callback(self._webstep)

    @rpc_callback
    def _default_callback(self, data, plus, error=None):
        """This is the callback for the RPC method called from a web
        page, that just collect the response.

        """
        log.debug("WebService._default_callback")
        self.__responses[plus] = (data, error)
