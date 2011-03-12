#!/usr/bin/python

"""Simple web service example.

"""

import os

import tornado.web

from WebAsyncLibrary import WebService
from Util import log, ServiceCoord


class WebServiceA(WebService):
    """Simple web service example.

    """

    def __init__(self, shard):
        log.debug("WebServiceA.__init__")
        WebService.__init__(self, shard,
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
    import sys
    if len(sys.argv) != 2:
        print sys.argv[0], "shard"
    else:
        WebServiceA(int(sys.argv[1])).run()
