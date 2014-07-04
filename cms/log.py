#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
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

# Some code snippets have been taken and readapted from the logging
# package of Python 2.7. For such pieces this copyright applies:
#
# Copyright 2001-2013 by Vinay Sajip. All Rights Reserved.
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
# http://hg.python.org/cpython/file/69ee9b554eca/Lib/logging/__init__.py
# http://hg.python.org/cpython/file/69ee9b554eca/Lib/logging/handlers.py

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import curses
import logging
import sys

import gevent.coros


class StreamHandler(logging.StreamHandler):
    """Subclass to make gevent-aware.

    Use a gevent lock instead of a threading one to block only the
    current greenlet.

    """
    def createLock(self):
        """Set self.lock to a new gevent RLock.

        """
        self.lock = gevent.coros.RLock()


class FileHandler(logging.FileHandler):
    """Subclass to make gevent-aware.

    Use a gevent lock instead of a threading one to block only the
    current greenlet.

    """
    def createLock(self):
        """Set self.lock to a new gevent RLock.

        """
        self.lock = gevent.coros.RLock()


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
    def __init__(self, log_service):
        """Initialize the handler.

        Establish a connection to the given LogService.

        log_service (RemoteService): a handle for a remote LogService.

        """
        logging.Handler.__init__(self)
        self._log_service = log_service

    def createLock(self):
        """Set self.lock to a new gevent RLock.

        """
        self.lock = gevent.coros.RLock()

    # Taken from CPython, combining emit and makePickle, and adapted to
    # not pickle the dictionary and use its items as keyword parameters
    # for LogService.Log.
    def emit(self, record):
        try:
            ei = record.exc_info
            if ei:
                # just to get traceback text into record.exc_text ...
                self.format(record)
                record.exc_info = None  # to avoid Unpickleable error
            # See issue #14436: If msg or args are objects, they may not be
            # available on the receiving end. So we convert the msg % args
            # to a string, save it as msg and zap the args.
            d = dict(record.__dict__)
            d['msg'] = record.getMessage()
            d['args'] = None
            if ei:
                record.exc_info = ei  # for next handler
            self._log_service.Log(**d)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


def has_color_support(stream):
    """Try to determine if the given stream supports colored output.

    Return True only if the stream declares to be a TTY, if it has a
    file descriptor on which ncurses can initialize a terminal and if
    that terminal's entry in terminfo declares support for colors.

    stream (fileobj): a file-like object (that adheres to the API
        declared in the `io' package).

    return (bool): True if we're sure that colors are supported, False
        if they aren't or if we can't tell.

    """
    if stream.isatty():
        try:
            curses.setupterm(fd=stream.fileno())
            # See `man terminfo` for capabilities' names and meanings.
            if curses.tigetnum("colors") > 0:
                return True
        # fileno() can raise IOError or OSError (since Python 3.3).
        except Exception:
            pass
    return False


def get_color_hash(string):
    """Deterministically return a color based on the string's content.

    Determine one of curses.COLOR_* using only the data of the given
    string. The only condition is for the operation to give the same
    result when repeated.

    string (string): the string.

    return (int): a color, as a curses.COLOR_* constant..

    """
    # We get the default hash of the string and use it to pick a color.
    return [curses.COLOR_BLACK,
            curses.COLOR_RED,
            curses.COLOR_GREEN,
            curses.COLOR_YELLOW,
            curses.COLOR_BLUE,
            curses.COLOR_MAGENTA,
            curses.COLOR_CYAN,
            curses.COLOR_WHITE][hash(string) % 8]


def add_color_to_string(string, color):
    """Format the string to be printed with the given color.

    Insert formatting characters that, when printed on a terminal, will
    make the given string appear with the given foreground color.

    string (string): the string to color.
    color (int): the color as a curses constant, like
        curses.COLOR_BLACK.

    return (string): the formatted string.

    """
    # See `man terminfo` for capabilities' names and meanings.
    return "%s%s%s%s" % (curses.tparm(curses.tigetstr("setaf"), color),
                         curses.tparm(curses.tigetstr("bold")), string,
                         curses.tparm(curses.tigetstr("sgr0")))


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
    SEVERITY_COLORS = {logging.CRITICAL: curses.COLOR_RED,
                       logging.ERROR: curses.COLOR_RED,
                       logging.WARNING: curses.COLOR_YELLOW,
                       logging.INFO: curses.COLOR_GREEN,
                       logging.DEBUG: curses.COLOR_CYAN}

    def __init__(self, colors=False):
        """Initialize a formatter.

        colors (bool): whether to use colors in formatted output or
            not.

        """
        logging.Formatter.__init__(self, "", "%Y/%m/%d %H:%M:%S")
        self.colors = colors

    # Taken from CPython and adapted to remove assumptions that there
    # was a constant format string stored in _fmt. This meant removing
    # the call to usesTime() and substituing the _fmt % record.__dict__
    # expression with the more powerful do_format(record).
    def format(self, record):
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
            try:
                s = s + record.exc_text
            except UnicodeError:
                # Sometimes filenames have non-ASCII chars, which can lead
                # to errors when s is Unicode and record.exc_text is str
                # See issue 8924.
                # We also use replace for when there are multiple
                # encodings, e.g. UTF-8 for the filesystem and latin-1
                # for a script. See issue 13232.
                s = s + record.exc_text.decode(sys.getfilesystemencoding(),
                                               'replace')
        return s

    def do_format(self, record):
        """Produce a human-readable message from the given record.

        This is the "core" of the format method, but it has been split
        out to allow the code to focus only on formatting, rather than
        bookkeeping (putting args into their placeholders in msg and
        formatting time and exception).

        record (LogRecord): the data for the log message.

        return (string): the formatted log message.

        """
        # Determine the first part (time and severity) and its color.
        severity_str = record.asctime + " - " + record.levelname
        severity_col = self.SEVERITY_COLORS[record.levelno]

        # Determine the second part (service coords) and its color.
        if hasattr(record, "service_name") and \
                hasattr(record, "service_shard"):
            coord_str = "%s,%d" % (record.service_name, record.service_shard)
        else:
            coord_str = "None"
        coord_col = get_color_hash(coord_str)

        # Determine the third part (operation) and its color.
        if hasattr(record, "operation"):
            operation_str = record.operation
        else:
            operation_str = ""
        operation_col = get_color_hash(operation_str)

        # Colorize the strings.
        if self.colors:
            severity_str = add_color_to_string(severity_str, severity_col)
            coord_str = add_color_to_string(coord_str, coord_col)
            operation_str = add_color_to_string(operation_str, operation_col)

        # Put them all together.
        fmt = severity_str
        fmt += " [" + coord_str
        if hasattr(record, "operation"):
            fmt += "/" + operation_str
        fmt += "] " + record.message

        return fmt


class ServiceFilter(logging.Filter):
    """Add service coords to filtered log messages.

    The name is misleading: this class isn't there to filter messages
    (none of them will be dropped) but to add contextual data to them.
    We add the "service_name" and "service_shard" fields (if they are
    not already set) with the values given to the constructor.

    """
    def __init__(self, name, shard):
        """Initialize a filter for the given coords.

        name (string): the service name (its class).
        shard (int): its shard (the index of its entry in the config).

        """
        logging.Filter.__init__(self, "")
        self.name = name
        self.shard = shard

    def filter(self, record):
        """Add data to the given record.

        record (LogRecord): data for a log message, to analyze and (if
            needed) tamper with.

        return (bool): whether to keep the record or not (will always
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
    def __init__(self, logger, operation):
        """Initialize an adapter to set the given operation.

        operation (string): a human-readable description of what the
            code will be performing while it's logging messages to
            this object instead of to the wrapped logger.

        """
        logging.LoggerAdapter.__init__(self, logger, {"operation": operation})
        self.operation = operation

    def process(self, msg, kwargs):
        """Inject the data in the log message.

        msg (string): the message given to one of debug(), info(),
            warning(), etc. methods.
        kwargs (dict): the keyword arguments given to such method (not
            the positional ones!).

        """
        kwargs.setdefault("extra", {}).setdefault("operation", self.operation)
        return msg, kwargs


# Get the root logger.
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

# Install a shell handler.
shell_handler = StreamHandler(sys.stdout)
shell_handler.setLevel(logging.INFO)
shell_handler.setFormatter(CustomFormatter(has_color_support(sys.stdout)))
root_logger.addHandler(shell_handler)
