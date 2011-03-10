#!/usr/bin/python

import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.escape
import asyncore


import os
import time

from AsyncLibrary import Service, rpc_callback, encode_json
from Util import ServiceCoord, log

class MainHandler(tornado.web.RequestHandler):
    """Home page handler.

    """
    def get(self):
        self.render("index.html")

class RPCRequestHandler(tornado.web.RequestHandler):
    """AJAX request handler.

    """
    def get(self, service, shard, method, arguments, rid):
        print "Service:  ", service
        print "Shard:    ", shard
        print "Method:   ", method
        print "Arguments:", arguments
        print "Rid:      ", rid
        service = ServiceCoord(service, int(shard))
        if not self.application.service.remote_services[service].connected:
            self.render("rpc_answer.html",
                        response=encode_json({'status': 'unconnected'}))
            return

        self.application.service.__responses[rid] = "wait"
        self.application.service.remote_services[service].__getattr__(method)(\
            string=arguments,
            callback=self.application.service.default_callback,
            plus=rid)
        self.render("rpc_answer.html",
                    response=encode_json({'status': 'wait'}))

class RPCAnswerHandler(tornado.web.RequestHandler):
    """AJAX request handler.

    """
    def get(self, rid):
        responses = self.application.service.__responses
        print responses
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

handlers = [
            (r"/", MainHandler),
            (r"/rpc_request/([a-zA-Z0-9_-]+)/([0-9_-]+)/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)", RPCRequestHandler),
            (r"/rpc_answer/([a-zA-Z0-9_-]+)", RPCAnswerHandler),
           ]

parameters = {
    "login_url": "/" ,
    "template_path": "./",
    "cookie_secret": "DsEwRxZER06etXcqgfowEJuM6rZjwk1JvknlbngmNck=",
    "static_path": os.path.join(os.path.dirname(__file__), "./"),
    "debug" : "True",
   }

application = tornado.web.Application(handlers, **parameters)

class WebServer(Service):
    """Example of a RPC service that is also a tornado webserver.

    """

    def __init__(self):
        log.debug("WebServer.__init__")
        Service.__init__(self)
        self.ServiceB_1 = self.connect_to(ServiceCoord("ServiceB", 1))

        self.__responses = {}
        self._RPCRequestHandler__responses = self.__responses
        self._RPCAnswerHandler__responses = self.__responses
        application.service = self
        http_server = tornado.httpserver.HTTPServer(application)
        http_server.listen(9999);
        try:
            self.instance = tornado.ioloop.IOLoop.instance()
            self.instance.add_callback(self._step_2)
            self.instance.start()
        except KeyboardInterrupt:
            pass

    def _step_2(self):
        self._step()
        self.instance.add_callback(self._step_2)

    @rpc_callback
    def default_callback(self, self2, data, plus, error=None):
        print "Self: ", self
        print "Data: ", data
        print "Plus: ", plus
        print "Error:", error
        self.__responses[plus] = (data, error)

if __name__ == "__main__":
    WebServer().run()


