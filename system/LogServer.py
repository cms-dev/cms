#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright (C) 2010 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright (C) 2010 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright (C) 2010 Matteo Boscariol <boscarim@hotmail.com>
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

import datetime
import time
import os
from RPCServer import RPCServer

import Configuration
import Utils

class LogServer(RPCServer):
    def __init__(self, listen_address = None, listen_port = None):
        if listen_address == None:
            listen_address = Configuration.log_server[0]
        if listen_port == None:
            listen_port = Configuration.log_server[1]

        Utils.maybe_mkdir("logs")
        self.log_file = open(os.path.join("logs", "%d.log" % (time.time())), "w")

        RPCServer.__init__(self, "LogServer", listen_address, listen_port,
                           [self.log])

    def log(self, msg, service, operation = "",
            severity = Utils.Logger.SEVERITY_NORMAL,
            timestamp = None):
        if timestamp == None:
            timestamp = time.time()
        line = Utils.format_log(msg, service, operation, severity, timestamp)
        print line
        print >> self.log_file, line
        return True

if __name__ == "__main__":
    ls = LogServer()
