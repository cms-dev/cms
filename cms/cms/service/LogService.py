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

"""Logger service.

"""

import os
import time
import codecs

from cms import config, default_argument_parser, mkdir, \
     logger, format_log, \
     SEV_CRITICAL, SEV_ERROR, SEV_WARNING
from cms.async import ServiceCoord
from cms.async.AsyncLibrary import Service, rpc_method


class LogService(Service):
    """Logger service.

    """

    def __init__(self, shard):
        logger.initialize(ServiceCoord("LogService", shard))
        Service.__init__(self, shard, custom_logger=logger)

        log_dir = os.path.join(config.log_dir, "cms")
        if not mkdir(config.log_dir) or \
               not mkdir(log_dir):
            logger.error("Cannot create necessary directories.")
            self.exit()
            return

        log_filename = "%d.log" % int(time.time())
        self._log_file = codecs.open(os.path.join(log_dir, log_filename),
                                     "w", "utf-8")
        try:
            os.remove(os.path.join(log_dir, "last.log"))
        except OSError:
            pass
        os.symlink(log_filename,
                   os.path.join(log_dir, "last.log"))

        self._last_messages = []

    @rpc_method
    def Log(self, msg, coord, operation, severity, timestamp):
        """Log a message.

        msg (string): the message to log
        operation (string): a high-level description of the long-term
                            operation that is going on in the service
        severity (string): a constant defined in Logger
        timestamp (float): seconds from epoch
        returns (bool): True

        """
        # To avoid possible mistakes.
        msg = str(msg)
        operation = str(operation)

        if severity in  [SEV_CRITICAL, SEV_ERROR, SEV_WARNING]:
            self._last_messages.append({"message": msg,
                                        "coord": coord,
                                        "operation": operation,
                                        "severity": severity,
                                        "timestamp": timestamp})
            if len(self._last_messages) > 100:
                del self._last_messages[0]

        print >> self._log_file, format_log(
            msg, coord, operation, severity, timestamp,
            colors=config.color_remote_file_log)
        print format_log(msg, coord, operation, severity, timestamp,
                         colors=config.color_remote_shell_log)

    @rpc_method
    def last_messages(self):
        return self._last_messages


def main():
    """Parse arguments and launch service.

    """
    default_argument_parser("Logger for CMS.", LogService).run()


if __name__ == "__main__":
    main()
