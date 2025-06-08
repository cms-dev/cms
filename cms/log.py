#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2021 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2015 Luca Versari <veluca93@gmail.com>
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

# Some code snippets have been taken and readapted from the logging
# package of Python 3. For such pieces this copyright applies:
#
# Copyright 2001-2016 by Vinay Sajip. All Rights Reserved.
#
# Permission to use, copy, modify, and distribute this software and its
# documentation for any purpose and without fee is hereby granted,
# provided that the above copyright notice appear in all copies and that
# both that copyright notice and this permission notice appear in
# supporting documentation, and that the name of Vinay Sajip
# not be used in advertising or publicity pertaining to distribution
# of the software without specific, written prior permission.
# VINAY SAJIP DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE, INCLUDING
# ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL
# VINAY SAJIP BE LIABLE FOR ANY SPECIAL, INDIRECT OR CONSEQUENTIAL DAMAGES OR
# ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER
# IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT
# OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
#
# You can find the original files at:
# https://hg.python.org/cpython/file/4243df51fe43/Lib/logging/__init__.py
# https://hg.python.org/cpython/file/4243df51fe43/Lib/logging/handlers.py

import logging
import sys
import typing

import gevent.lock

from cmscommon.terminal import colors, add_color_to_string, has_color_support
if typing.TYPE_CHECKING:
    from cms.io.rpc import RemoteServiceClient


class StreamHandler(logging.StreamHandler):
    """Subclass to make gevent-aware.

    Use a gevent lock instead of a threading one to block only the
    current greenlet.

    """
    def createLock(self):
        """Set self.lock to a new gevent RLock.

        """
        self.lock = gevent.lock.RLock()


class FileHandler(logging.FileHandler):
    """Subclass to make gevent-aware.

    Use a gevent lock instead of a threading one to block only the
    current greenlet.

    """
    def createLock(self):
        """Set self.lock to a new gevent RLock.

        """
        self.lock = gevent.lock.RLock()


class LogServiceHandler(logging.Handler):
    """Send log messages to a remote centralized LogService.

    Support log collection by sending messages over the RPC system to
    the LogService. We try to send LogRecords as accurately as possible
    to rebuild them on the remote end and re-inject them in the logging
    system. Unfortunately, since they'll have to be JSON-encoded when
    sent on the wire, some tweaks have to be made. In particular, we
    need to somehow "encode" objects that cannot be converted to JSON.
    These are the exception info (if any) and, possibly, the args.

    For exceptions, we simply format them locally and store the text in
    exc_text, dropping the exc_info. That same field is also used, by
    convention, by formatters to store a cache of the exception and
    will therefore picked up seamlessly.

    For args, we just format them into msg to produce the message. We
    then store the message as msg and drop args.

    """
    def __init__(self, log_service: "RemoteServiceClient"):
        """Initialize the handler.

        Establish a connection to the given LogService.

        log_service: a handle for a remote LogService.

        """
        logging.Handler.__init__(self)
        self._log_service = log_service

    def createLock(self):
        """Set self.lock to a new gevent RLock.

        """
        self.lock = gevent.lock.RLock()

    def emit(self, record):
        """Pickle and emit a record to LogService.

        Taken from CPython's SocketHandler (see link in the file header),
        combining emit and makePickle, and adapted to not pickle the dictionary
        and use its items as keyword parameters for LogService.Log.

        """
        try:
            ei = record.exc_info
            if ei:
                # just to get traceback text into record.exc_text ...
                self.format(record)
            # See issue #14436: If msg or args are objects, they may not be
            # available on the receiving end. So we convert the msg % args
            # to a string, save it as msg and zap the args.
            d = dict(record.__dict__)
            d['msg'] = record.getMessage()
            d['args'] = None
            d['exc_info'] = None
            # Issue #25685: delete 'message' if present: redundant with 'msg'
            d.pop('message', None)
            self._log_service.Log(**d)
        except Exception:
            self.handleError(record)


def get_color_hash(string: str) -> int:
    """Deterministically return a color based on the string's content.

    Determine one of colors.* using only the data of the given string.
    The only condition is for the operation to give the same result when
    repeated.

    string: the string.

    return: a color, as a colors.* constant.

    """
    # We get the default hash of the string and use it to pick a color.
    return [colors.BLACK,
            colors.RED,
            colors.GREEN,
            colors.YELLOW,
            colors.BLUE,
            colors.MAGENTA,
            colors.CYAN,
            colors.WHITE][hash(string) % 8]


class CustomFormatter(logging.Formatter):
    """Format log messages as we want them.

    A custom logging formatter to present the information that we want
    to see and show them in the way we want them to appear.
    The first such part only consists in adding the service coords and
    the operation to the displayed log message. This could almost be
    achieved by just using the standard formatter with a custom format
    string, but that wouldn't allow us to show the slash before the
    operation only if we actually have the operation data.
    The second part comprises selecting the fields we want to show,
    determining their order and their separators (all this can be done
    with the standard formatter) and coloring them if we're asked to
    (this cannot be done with the standard formatter!).

    """
    SEVERITY_COLORS = {logging.CRITICAL: colors.RED,
                       logging.ERROR: colors.RED,
                       logging.WARNING: colors.YELLOW,
                       logging.INFO: colors.GREEN,
                       logging.DEBUG: colors.CYAN}

    def __init__(self, colors: bool = False):
        """Initialize a formatter.

        colors: whether to use colors in formatted output or not.

        """
        logging.Formatter.__init__(self, "")
        self.colors = colors

    def format(self, record: logging.LogRecord) -> str:
        """Format the specified record as text.

        Taken from CPython (see link in the file header) and adapted to use our
        own do_format().

        """
        record.message = record.getMessage()
        record.asctime = self.formatTime(record, self.datefmt)
        s = self.do_format(record)
        if record.exc_info:
            # Cache the traceback text to avoid converting it multiple times
            # (it's constant anyway)
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            if s[-1:] != "\n":
                s = s + "\n"
            s = s + record.exc_text
        if record.stack_info:
            if s[-1:] != "\n":
                s = s + "\n"
            s = s + self.formatStack(record.stack_info)
        return s

    def do_format(self, record: logging.LogRecord) -> str:
        """Produce a human-readable message from the given record.

        This is the "core" of the format method, but it has been split
        out to allow the code to focus only on formatting, rather than
        bookkeeping (putting args into their placeholders in msg and
        formatting time and exception).

        record: the data for the log message.

        return: the formatted log message.

        """
        severity = self.get_severity(record)
        coordinates = self.get_coordinates(record)
        operation = self.get_operation(record)
        message = record.message
        if self.colors:
            severity_col = self.SEVERITY_COLORS[record.levelno]
            severity = add_color_to_string(severity, severity_col,
                                           bold=True, force=True)
            coordinates_col = get_color_hash(coordinates)
            if len(coordinates) > 0:
                coordinates = add_color_to_string(coordinates, coordinates_col,
                                                  bold=True, force=True)
            operation_col = get_color_hash(operation)
            if len(operation) > 0:
                operation = add_color_to_string(operation, operation_col,
                                                bold=True, force=True)

        fmt = severity
        if coordinates.strip() != "":
            fmt += " [%s]" % (coordinates.strip())
        if operation.strip() != "":
            fmt += " [%s]" % (operation.strip())
        fmt += " %s" % message
        return fmt

    def get_severity(self, record: logging.LogRecord) -> str:
        """Return the severity part of the log for the given record."""
        severity = record.asctime + " - " + record.levelname
        return severity

    def get_coordinates(self, record: logging.LogRecord) -> str:
        """Return the coordinates part of the log for the given record.

        It contains information on what originates the log. For the
        non detailed log, it only contains service coordinates.

        """
        if hasattr(record, "service_name") and \
                hasattr(record, "service_shard"):
            service = record.service_name\
                .replace("Service", "").replace("WebServer", "")
            coordinates = "%s,%d" % (service, record.service_shard)
        else:
            coordinates = "<unknown>"
        return coordinates

    def get_operation(self, record: logging.LogRecord) -> str:
        """Return the operation part of the log for the given record.

        The operation is a string explicitly passed in the logger call.

        """
        return record.operation if hasattr(record, "operation") else ""


class DetailedFormatter(CustomFormatter):
    """A version of custom formatter showing more information."""

    def get_coordinates(self, record: logging.LogRecord) -> str:
        """See CustomFormatter.get_coordinates

        The detailed log contains the service coordinate, the thread
        name, file and function name, in addition to the operation, if
        present.

        """
        coordinates = super().get_coordinates(record)

        # Thread name, trying to shorten it removing useless values.
        coordinates += " %s" % (
            record.threadName.replace("Thread", "").replace("Dummy-", ""))

        # File and function name.
        coordinates += " %s::%s" % (
            record.filename.replace(".py", ""), record.funcName)

        return coordinates


class ServiceFilter(logging.Filter):
    """Add service coords to filtered log messages.

    The name is misleading: this class isn't there to filter messages
    (none of them will be dropped) but to add contextual data to them.
    We add the "service_name" and "service_shard" fields (if they are
    not already set) with the values given to the constructor.

    """
    def __init__(self, name: str, shard: int):
        """Initialize a filter for the given coords.

        name: the service name (its class).
        shard: its shard (the index of its entry in the config).

        """
        logging.Filter.__init__(self, "")
        self.name = name
        self.shard = shard

    def filter(self, record: logging.LogRecord) -> bool:
        """Add data to the given record.

        record: data for a log message, to analyze and (if
            needed) tamper with.

        return: whether to keep the record or not (will always
            be True).

        """
        if not hasattr(record, "service_name") or \
                not hasattr(record, "service_shard"):
            record.service_name = self.name
            record.service_shard = self.shard
        return True


class OperationAdapter(logging.LoggerAdapter):
    """Helper to attach operation to messages.

    Wraps a logger and adds the operation given to the constructor to
    the "operation" field of the "extra" argument of all messages
    logged with this adapter. If "extra" doesn't exists it is created.
    If "operation" is already set it isn't altered.

    """
    def __init__(self, logger, operation: str):
        """Initialize an adapter to set the given operation.

        operation: a human-readable description of what the
            code will be performing while it's logging messages to
            this object instead of to the wrapped logger.

        """
        logging.LoggerAdapter.__init__(self, logger, {"operation": operation})
        self.operation = operation

    def process(self, msg: str, kwargs: dict):
        """Inject the data in the log message.

        msg: the message given to one of debug(), info(),
            warning(), etc. methods.
        kwargs: the keyword arguments given to such method (not
            the positional ones!).

        """
        kwargs.setdefault("extra", {}).setdefault("operation", self.operation)
        return msg, kwargs


# Get the root logger.
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)


# Install a shell handler.
shell_handler = StreamHandler(sys.stderr)
shell_handler.setLevel(logging.INFO)
shell_handler.setFormatter(CustomFormatter(has_color_support(sys.stderr)))
root_logger.addHandler(shell_handler)


def set_detailed_logs(detailed: bool):
    """Set or unset the shell logs to detailed."""
    global shell_handler
    color = has_color_support(sys.stderr)
    formatter = DetailedFormatter(color) \
        if detailed else CustomFormatter(color)
    shell_handler.setFormatter(formatter)
