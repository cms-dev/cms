#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2011-2012 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

from cmsranking.Config import config

import logging
import os.path
import time

from traceback import format_tb as formatTraceback

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


class LogFormatter(logging.Formatter):
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
        return "\033[%sm" % ';'.join([str(x)
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
                       '\n'.join(
            map(lambda a: self.ansi_command(ANSI_FAINT_ON_CMD) +
                a + self.ansi_command(ANSI_FAINT_OFF_CMD),
                ''.join(formatTraceback(traceback)).strip().split('\n'))))

        return result

    def format(self, record):
        """Do the actual formatting.

        Prepend a timestamp and an abbreviation of the logging level,
        followed by the message, the request_body (if present) and the
        exception details (if present).

        """
        result = '%s%s.%03d%s' % (self.time_prefix,
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
logger = logging.getLogger()
# Catch all logging messages (we'll filter them on the handlers).
logger.setLevel(logging.DEBUG)

# Define the stream handler to output on stderr.
_stream_log = logging.StreamHandler()
_stream_log.setLevel(logging.WARNING)
_stream_log.setFormatter(LogFormatter(color=config.log_color))
logger.addHandler(_stream_log)

# Define the file handler to output on the specified log directory.
_file_log = logging.FileHandler(os.path.join(config.log_dir,
                                time.strftime("%Y-%m-%d-%H-%M-%S.log")))
_file_log.setLevel(logging.WARNING)
_file_log.setFormatter(LogFormatter(color=False))
logger.addHandler(_file_log)
