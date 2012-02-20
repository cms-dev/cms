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
import datetime

from cms import config, default_argument_parser
from cms.async import ServiceCoord
from cms.async.AsyncLibrary import Service, RemoteService, rpc_method
from cms.util.Utils import mkdir


## ANSI utilities. See for reference:
# http://pueblo.sourceforge.net/doc/manual/ansi_color_codes.html

ANSI_FG_COLORS = {'black':   30,
                  'red':     31,
                  'green':   32,
                  'yellow':  33,
                  'blue':    34,
                  'magenta': 35,
                  'cyan':    36,
                  'white':   37}

ANSI_BG_COLORS = {'black':   40,
                  'red':     41,
                  'green':   42,
                  'yellow':  43,
                  'blue':    44,
                  'magenta': 45,
                  'cyan':    46,
                  'white':   47}

ANSI_RESET_CMD = 0
ANSI_FG_DEFAULT_CMD = 39
ANSI_BG_DEFAULT_CMD = 49
ANSI_BOLD_ON_CMD = 1
ANSI_BOLD_OFF_CMD = 22
ANSI_ITALICS_ON_CMD = 3
ANSI_ITALICS_OFF_CMD = 23
ANSI_UNDERLINE_ON_CMD = 4
ANSI_UNDERLINE_OFF_CMD = 24
ANSI_STRIKETHROUGH_ON_CMD = 9
ANSI_STRIKETHROUGH_OFF_CMD = 29
ANSI_INVERT_CMD = 7


def ansi_command(*args):
    """Produce the escape string that corresponds to the given ANSI
    command.

    """
    return '\033[%sm' % (";".join((str(x) for x in args)))


def ansi_color_hash(string):
    """Enclose a string in a ANSI code giving it a color that
    depends on its content.

    string (string): the string to color
    return (string): string enclosed in an ANSI code

    """
    # Magic number: 30 is the lowest of ANSI_FG_COLORS
    return 30 + (sum((ord(x) for x in string)) % len(ANSI_FG_COLORS))


def ansi_color_string(string, col):
    """Enclose a string in a ANSI code giving it the specified color.

    string (string): the string to color
    col (int): the color ANSI code
    return (string): s enclosed in an ANSI code

    """
    return ansi_command(col, ANSI_BOLD_ON_CMD) + \
        string + ansi_command(ANSI_RESET_CMD)


## Logging utilities ##

SEV_CRITICAL, SEV_ERROR, SEV_WARNING, SEV_INFO, SEV_DEBUG = \
              "CRITICAL", \
              "ERROR   ", \
              "WARNING ", \
              "INFO    ", \
              "DEBUG   "

SEVERITY_COLORS = {SEV_CRITICAL: 'red',
                   SEV_ERROR:    'red',
                   SEV_WARNING:  'yellow',
                   SEV_INFO:     'green',
                   SEV_DEBUG:    'cyan'}


def format_log(msg, coord, operation, severity, timestamp, colors=False):
    """Format a log message in a common way (for local and remote
    logging).

    msg (string): the message to log.
    coord (ServiceCoord): coordinate of the originating service.
    operation (string): a high-level description of the long-term
                        operation that is going on in the service.
    severity (string): a constant defined in Logger.
    timestamp (float): seconds from epoch.
    colors (bool): whether to use ANSI color commands (for the logs
                   directed to a shell).

    returns (string): the formatted log.

    """
    _datetime = datetime.datetime.fromtimestamp(timestamp)
    if coord is None:
        coord = ""

    if colors:
        severity_color = ANSI_FG_COLORS[SEVERITY_COLORS[severity]]
        coord_color = ansi_color_hash(coord)
        if operation == "":
            format_string = "%s [%s] %%s" % \
                (ansi_color_string("%s - %s", severity_color),
                 ansi_color_string("%s", coord_color))
        else:
            operation_color = ansi_color_hash(operation)
            format_string = "%s [%s/%s] %%s" % \
                (ansi_color_string("%s - %s", severity_color),
                 ansi_color_string("%s", coord_color),
                 ansi_color_string("%s", operation_color))
    else:
        if operation == "":
            format_string = "%s - %s [%s] %s"
        else:
            format_string = "%s - %s [%s/%s] %s"

    if operation == "":
        return format_string % ('{0:%Y/%m/%d %H:%M:%S}'.format(_datetime),
                                severity, coord, msg)
    else:
        return format_string % ('{0:%Y/%m/%d %H:%M:%S}'.format(_datetime),
                                severity, coord, operation, msg)


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


class Logger(object):
    """Utility class to connect to the remote log service and to
    store/display locally and remotely log messages.

    """
    TO_STORE = [
        SEV_CRITICAL,
        SEV_ERROR,
        SEV_WARNING,
        SEV_INFO,
        SEV_DEBUG,
        ]
    TO_DISPLAY = [
        SEV_CRITICAL,
        SEV_ERROR,
        SEV_WARNING,
        SEV_INFO
        ]
    # FIXME - SEV_DEBUG cannot be added to TO_SEND, otherwise we enter
    # an infinite loop
    TO_SEND = [
        SEV_CRITICAL,
        SEV_ERROR,
        SEV_WARNING,
        SEV_INFO
        ]

    # We use a singleton approach here. The following is the only
    # instance around.
    _instance = None

    def __new__(cls, *args, **kwargs):
        """Creation method to ensure there is only one logger around.

        """
        if not cls._instance:
            cls._instance = super(Logger, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        self._log_service = RemoteService(None,
                                          ServiceCoord("LogService", 0))
        self.operation = ""

    def initialize(self, service):
        """To be set by the service we are currently running.

        service (ServiceCoord): the service that we are running

        """
        self._my_coord = service

        # Warn if the service, shard is not supposed to be there.
        if self._my_coord not in config.async.core_services and \
           self._my_coord not in config.async.other_services:
            raise ValueError("Service not present in configuration.")

        log_dir = os.path.join(config.log_dir,
                               "%s-%d" % (service.name, service.shard))
        mkdir(config.log_dir)
        mkdir(log_dir)
        log_filename = "%d.log" % int(time.time())
        self._log_file = codecs.open(
            os.path.join(log_dir, log_filename),
            "w", "utf-8")
        try:
            os.remove(os.path.join(log_dir, "last.log"))
        except OSError:
            pass
        os.symlink(log_filename,
                   os.path.join(log_dir, "last.log"))
        self.info("%s %d up and running!" % service)

    def log(self, msg, operation=None, severity=None, timestamp=None):
        """Record locally a log message and tries to send it to the
        log service.

        msg (string): the message to log
        operation (string): a high-level description of the long-term
                            operation that is going on in the service
        severity (string): a constant defined in Logger
        timestamp (float): seconds from epoch

        """
        if severity is None:
            severity = SEV_INFO
        if timestamp is None:
            timestamp = time.time()
        if operation is None:
            operation = self.operation
        coord = repr(self._my_coord)

        if severity in Logger.TO_DISPLAY:
            print format_log(msg, coord, operation, severity, timestamp,
                             colors=config.color_shell_log)
        if severity in Logger.TO_STORE:
            print >> self._log_file, format_log(msg, coord, operation,
                                                severity, timestamp,
                                                colors=config.color_file_log)
        if severity in Logger.TO_SEND:
            self._log_service.Log(msg=msg, coord=coord, operation=operation,
                                  severity=severity, timestamp=timestamp)

    def __getattr__(self, method):
        """Syntactic sugar to allow, e.g., logger.debug(...).

        """
        severities = {
            "debug": SEV_DEBUG,
            "info": SEV_INFO,
            "warning": SEV_WARNING,
            "error": SEV_ERROR,
            "critical": SEV_CRITICAL
            }
        if method in severities:
            def new_method(msg, operation=None, timestamp=None):
                """Syntactic sugar around log().

                """
                return self.log(msg, operation, severities[method], timestamp)
            return new_method


# Create a (unique) logger object.
logger = Logger()


def main():
    """Parse arguments and launch service.

    """
    default_argument_parser("Logger for CMS.", LogService).run()


if __name__ == "__main__":
    main()
