#!/usr/bin/python

"""Simple web service example.

"""

import os

import tornado.web

from AsyncLibrary import logger
from WebAsyncLibrary import WebService
from Utils import ServiceCoord


class WebServiceA(WebService):
    """Simple web service example.

    """

    def __init__(self):
        logger.initialize(ServiceCoord("WebServiceA", 0))
        logger.debug("WebServiceA.__init__")
        WebService.__init__(self,
            9999,
            [(r"/", MainHandler)],
            {
                "login_url": "/",
                "template_path": "./",
                "cookie_secret": "DsEwRxZER06etXcqgfowEJuM6rZjwk1JvknlbngmNck=",
                "static_path": os.path.join(os.path.dirname(__file__), "./"),
                "debug": "True",
            })
        self.ServiceB = self.connect_to(ServiceCoord("ServiceB", 1))


class MainHandler(tornado.web.RequestHandler):
    """Home page handler.

    """
    def get(self):
        self.render("index.html")


if __name__ == "__main__":
    WebServiceA().run()
