#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2013 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import os
import time
import logging
from collections import deque

from cms import config, mkdir
from cms.log import root_logger, shell_handler, FileHandler, CustomFormatter
from cms.io import Service, rpc_method


logger = logging.getLogger(__name__)


class LogService(Service):
    """Logger service.

    """

    LAST_MESSAGES_COUNT = 100

    def __init__(self, shard):
        Service.__init__(self, shard)

        # Determine location of log file, and make directories.
        log_dir = os.path.join(config.log_dir, "cms")
        if not mkdir(config.log_dir) or \
                not mkdir(log_dir):
            logger.error("Cannot create necessary directories.")
            self.exit()
            return
        log_filename = "%d.log" % int(time.time())

        # Install a global file handler.
        self.file_handler = FileHandler(os.path.join(log_dir, log_filename),
                                        mode='w', encoding='utf-8')
        self.file_handler.setLevel(logging.DEBUG)
        self.file_handler.setFormatter(CustomFormatter(False))
        root_logger.addHandler(self.file_handler)

        # Provide a symlink to the latest log file.
        try:
            os.remove(os.path.join(log_dir, "last.log"))
        except OSError:
            pass
        os.symlink(log_filename,
                   os.path.join(log_dir, "last.log"))

        self._last_messages = deque(maxlen=self.LAST_MESSAGES_COUNT)

    @rpc_method
    def Log(self, **kwargs):
        """Log a message.

        Receive the attributes of a LogRecord, rebuild and handle it.
        The given keyword arguments will contain:
        msg (string): the message to log.
        levelname (string): the name of the level, one of "DEBUG",
            "INFO", "WARNING", "ERROR" and "CRITICAL".
        levelno (int): a numeric value denoting the level, one of the
            constants defined by the logging module. In fact, `levelno
            == getattr(logging, levelname)` (yes, it is redundant).
        created (float): when the log message was emitted (as an UNIX
            timestamp, seconds from epoch).

        And they may contain:
        service_name (string) and service_shard (int): the coords of
            the service where this message was generated.
        operation (string): a high-level description of the long-term
            operation that is going on in the service.
        exc_text (string): the text of the logged exception.

        """
        record = logging.makeLogRecord(kwargs)

        # Show in stdout, together with the messages we produce
        # ourselves.
        shell_handler.handle(record)
        # Write on the global log file.
        self.file_handler.handle(record)

        if record.levelno >= logging.WARNING:
            if hasattr(record, "service_name") and \
                    hasattr(record, "service_shard"):
                coord = "%s,%s" % (record.service_name, record.service_shard)
            else:
                coord = ""
            self._last_messages.append({
                "message": record.msg,
                "coord": coord,
                "operation": getattr(record, "operation", ""),
                "severity": record.levelname,
                "timestamp": record.created,
                "exc_text": getattr(record, "exc_text", None)})

    @rpc_method
    def last_messages(self):
        return list(self._last_messages)
