#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2011 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2011 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2011 Matteo Boscariol <boscarim@hotmail.com>
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

import time

import xmlrpclib
from SimpleXMLRPCServer import SimpleXMLRPCServer

import Configuration
import Utils

class RPCServer:
    def __init__(self, name, listen_address, listen_port,
                 functions, thread = None, start_now = True,
                 allow_none = False):
        # Store the LWS for later use
        self.lws = xmlrpclib.ServerProxy("http://%s:%d" % Configuration.logging_web_server)

        # Create server
        server = SimpleXMLRPCServer(("", listen_port), allow_none = allow_none, logRequests = False)
        server.register_introspection_functions()

        for function in functions:
            server.register_function(function)
        server.register_function(self.ping)

        if name != "LogServer":
            Utils.log("%s started..." % name)

        # Run the server's main loop
        if thread == None:
            if start_now:
                server.serve_forever()
        else:
            thread.run = server.serve_forever
            thread.daemon = True
            if start_now:
                thread.start()


    def ping(self, test_string):
        pass
