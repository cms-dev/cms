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


class LogFormatter(logging.Formatter):
    """A custom Formatter for our logs.

    """
    def __init__(self, color=True, *args, **kwargs):
        """Initialize the formatter.

        Based on the 'color' parameter we set the tags for many
        elements of our formatted output.

        """
        logging.Formatter.__init__(self, *args, **kwargs)
        self.time_prefix = '\033[1m' if color else ''
        self.time_suffix = '\033[22m' if color else ''
        self.cri_prefix = '\033[1;37;41m' if color else ''
        self.cri_suffix = '\033[22;39;49m' if color else ''
        self.err_prefix = '\033[1;31m' if color else ''
        self.err_suffix = '\033[22;39m' if color else ''
        self.wrn_prefix = '\033[1;33m' if color else ''
        self.wrn_suffix = '\033[22;39m' if color else ''
        self.inf_prefix = '\033[1;32m' if color else ''
        self.inf_suffix = '\033[22;39m' if color else ''
        self.dbg_prefix = '\033[1;34m' if color else ''
        self.dbg_suffix = '\033[22;39m' if color else ''

    def format(self, record):
        """Do the actual formatting.

        Prepend a timestamp and an abbreviation of the logging level,
        followed by the message, the request_body (if present) and the
        exception details (if present).

        """
        try:
            record.message = record.getMessage()
        except Exception, exc:
            record.message = 'Bad message (%r): %r' % (exc, record.__dict__)

        prefix = '%s%s.%03d%s' % (self.time_prefix,
            self.formatTime(record, '%Y-%m-%d %H:%M:%S'), record.msecs,
            self.time_suffix)

        if record.levelno == logging.CRITICAL:
            prefix += ' %s CRI %s ' % (self.cri_prefix, self.cri_suffix)
        elif record.levelno == logging.ERROR:
            prefix += ' %s ERR %s ' % (self.err_prefix, self.err_suffix)
        elif record.levelno == logging.WARNING:
            prefix += ' %s WRN %s ' % (self.wrn_prefix, self.wrn_suffix)
        elif record.levelno == logging.INFO:
            prefix += ' %s INF %s ' % (self.inf_prefix, self.inf_suffix)
        else:  # DEBUG
            prefix += ' %s DBG %s ' % (self.dbg_prefix, self.dbg_suffix)

        formatted = prefix + record.message.rstrip()

        if '\n' in formatted and not formatted[-1] == '\n':
            formatted += '\n'

        if 'request_body' in record.__dict__:
            formatted = "%s\n\n%s\n" % (formatted.rstrip(),
                                        record.request_body.rstrip())

        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            formatted = "%s\n\n%s\n" % (formatted.rstrip(),
                                        record.exc_text.rstrip())

        return formatted.replace("\n", "\n    ")


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
