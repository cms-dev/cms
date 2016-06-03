#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2011-2016 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import curses
import logging
import os.path
import sys
import time
from traceback import format_tb

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


## ANSI utilities. See for reference:
# http://pueblo.sourceforge.net/doc/manual/ansi_color_codes.html
# http://en.wikipedia.org/wiki/ANSI_escape_code
#

ANSI_FG_COLORS = {'black': 30,
                  'red': 31,
                  'green': 32,
                  'yellow': 33,
                  'blue': 34,
                  'magenta': 35,
                  'cyan': 36,
                  'white': 37}

ANSI_BG_COLORS = {'black': 40,
                  'red': 41,
                  'green': 42,
                  'yellow': 43,
                  'blue': 44,
                  'magenta': 45,
                  'cyan': 46,
                  'white': 47}

ANSI_RESET_CMD = 0
ANSI_FG_DEFAULT_CMD = 39
ANSI_BG_DEFAULT_CMD = 49
ANSI_BOLD_ON_CMD = 1
ANSI_BOLD_OFF_CMD = 22
ANSI_FAINT_ON_CMD = 2
ANSI_FAINT_OFF_CMD = 22
ANSI_ITALICS_ON_CMD = 3
ANSI_ITALICS_OFF_CMD = 23
ANSI_UNDERLINE_ON_CMD = 4
ANSI_UNDERLINE_OFF_CMD = 24
ANSI_STRIKETHROUGH_ON_CMD = 9
ANSI_STRIKETHROUGH_OFF_CMD = 29
ANSI_INVERSE_ON_CMD = 7
ANSI_INVERSE_OFF_CMD = 27

# TODO missing:
# - distinction between single and double underline
# - "slow blink on", "rapid blink on" and "blink off"
# - "conceal on" and "conceal off" (also called reveal)


class CustomFormatter(logging.Formatter):
    """A custom Formatter for our logs.

    """
    def __init__(self, color=True, *args, **kwargs):
        """Initialize the formatter.

        Based on the 'color' parameter we set the tags for many
        elements of our formatted output.

        """
        logging.Formatter.__init__(self, *args, **kwargs)

        self.color = color

        self.time_prefix = self.ansi_command(ANSI_BOLD_ON_CMD)
        self.time_suffix = self.ansi_command(ANSI_BOLD_OFF_CMD)
        self.cri_prefix = self.ansi_command(ANSI_BOLD_ON_CMD,
                                            ANSI_FG_COLORS['white'],
                                            ANSI_BG_COLORS['red'])
        self.cri_suffix = self.ansi_command(ANSI_BOLD_OFF_CMD,
                                            ANSI_FG_DEFAULT_CMD,
                                            ANSI_BG_DEFAULT_CMD)
        self.err_prefix = self.ansi_command(ANSI_BOLD_ON_CMD,
                                            ANSI_FG_COLORS['red'])
        self.err_suffix = self.ansi_command(ANSI_BOLD_OFF_CMD,
                                            ANSI_FG_DEFAULT_CMD)
        self.wrn_prefix = self.ansi_command(ANSI_BOLD_ON_CMD,
                                            ANSI_FG_COLORS['yellow'])
        self.wrn_suffix = self.ansi_command(ANSI_BOLD_OFF_CMD,
                                            ANSI_FG_DEFAULT_CMD)
        self.inf_prefix = self.ansi_command(ANSI_BOLD_ON_CMD,
                                            ANSI_FG_COLORS['green'])
        self.inf_suffix = self.ansi_command(ANSI_BOLD_OFF_CMD,
                                            ANSI_FG_DEFAULT_CMD)
        self.dbg_prefix = self.ansi_command(ANSI_BOLD_ON_CMD,
                                            ANSI_FG_COLORS['blue'])
        self.dbg_suffix = self.ansi_command(ANSI_BOLD_OFF_CMD,
                                            ANSI_FG_DEFAULT_CMD)

    def ansi_command(self, *args):
        """Produce the escape string that corresponds to the given
        ANSI command.

        """
        return "\033[%sm" % ';'.join(["%s" % x
                                      for x in args]) if self.color else ''

    def formatException(self, exc_info):
        exc_type, exc_value, traceback = exc_info

        result = "%sException%s %s.%s%s%s:\n\n    %s\n\n" % \
            (self.ansi_command(ANSI_BOLD_ON_CMD),
             self.ansi_command(ANSI_BOLD_OFF_CMD),
             exc_type.__module__,
             self.ansi_command(ANSI_BOLD_ON_CMD),
             exc_type.__name__,
             self.ansi_command(ANSI_BOLD_OFF_CMD),
             exc_value)
        result += "%sTraceback (most recent call last):%s\n%s" % \
            (self.ansi_command(ANSI_FAINT_ON_CMD),
             self.ansi_command(ANSI_FAINT_OFF_CMD),
             '\n'.join(map(lambda a: self.ansi_command(ANSI_FAINT_ON_CMD) +
                           a + self.ansi_command(ANSI_FAINT_OFF_CMD),
                           ''.join(format_tb(traceback)).strip().split('\n'))))

        return result

    def format(self, record):
        """Do the actual formatting.

        Prepend a timestamp and an abbreviation of the logging level,
        followed by the message, the request_body (if present) and the
        exception details (if present).

        """
        result = '%s%s.%03d%s' % \
            (self.time_prefix,
             self.formatTime(record, '%Y-%m-%d %H:%M:%S'), record.msecs,
             self.time_suffix)

        if record.levelno == logging.CRITICAL:
            result += ' %s CRI %s ' % (self.cri_prefix, self.cri_suffix)
        elif record.levelno == logging.ERROR:
            result += ' %s ERR %s ' % (self.err_prefix, self.err_suffix)
        elif record.levelno == logging.WARNING:
            result += ' %s WRN %s ' % (self.wrn_prefix, self.wrn_suffix)
        elif record.levelno == logging.INFO:
            result += ' %s INF %s ' % (self.inf_prefix, self.inf_suffix)
        else:  # DEBUG
            result += ' %s DBG %s ' % (self.dbg_prefix, self.dbg_suffix)

        try:
            message = record.getMessage()
        except Exception, exc:
            message = 'Bad message (%r): %r' % (exc, record.__dict__)

        result += message.strip()

        if "location" in record.__dict__:
            result += "\n%s" % record.location.strip()

        if "details" in record.__dict__:
            result += "\n\n%s" % record.details.strip()

        if record.exc_info:
            result += "\n\n%s" % self.formatException(record.exc_info).strip()

        return result.replace("\n", "\n    ") + '\n'


# Create a global reference to the root logger.
root_logger = logging.getLogger()
# Catch all logging messages (we'll filter them on the handlers).
root_logger.setLevel(logging.DEBUG)

# Define the stream handler to output on stderr.
shell_handler = StreamHandler(sys.stdout)
shell_handler.setLevel(logging.INFO)
shell_handler.setFormatter(CustomFormatter(has_color_support(sys.stdout)))
root_logger.addHandler(shell_handler)


def add_file_handler(log_dir):
    """Install a handler that writes in files in the given directory.

    log_dir (str): a path to a directory.

    """
    log_filename = time.strftime("%Y-%m-%d-%H-%M-%S.log")
    file_handler = FileHandler(os.path.join(log_dir, log_filename),
                               mode='w', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(CustomFormatter(False))
    root_logger.addHandler(file_handler)
