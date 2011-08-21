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

"""Logger service.

"""

import os
import time

import codecs
import base64

from cms.async.AsyncLibrary import Service, rpc_method, logger
from cms.async import ServiceCoord
from cms.util.Utils import ANSI_FG_COLORS

class LogService(Service):
    """Logger service.

    """

    def __init__(self, shard):
        logger.initialize(ServiceCoord("LogService", shard))
        Service.__init__(self, shard)

        self._log_file = codecs.open(os.path.join("logs", "%d.log" %
                                                  time.time()),
                                     "w", "utf-8")

    @rpc_method
    def Log(self, msg):
        """Log a message.

        msg (string): the message.
        returns (bool): True

        """

        print >> self._log_file, msg

        # FIXME - Bad hack to color the log
        time_severity, other = msg.split('[', 1)
        service, text = other.split(']', 1)
        operation = ""
        if service.find('/') != -1:
            service, operation = service.split('/', 1)
            operation = '/' + operation
        msg = '\033[1;31m' + time_severity + '\033[0m' + \
              '[' + self.color_hash(service) + \
              self.color_hash(operation) + ']' + text
        print msg

        return True

    def color_hash(self, s):
        """Enclose a string in a ANSI code giving it a color that
        depends on its content.

        s (string): the string to color
        return (string): s enclosed in an ANSI code

        """
        ansi_codes = ANSI_FG_COLORS.values()
        hash_number = sum([ord(x) for x in s]) % len(ansi_codes)
        return '\033[1;%dm%s\033[0m' % (ansi_codes[hash_number], s)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print sys.argv[0], "shard"
    else:
        LogService(int(sys.argv[1])).run()
