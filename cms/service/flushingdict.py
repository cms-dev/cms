#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2016 Stefano Maggiolo <s.maggiolo@gmail.com>
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

import gevent
import logging

try:
    from gevent.locks import RLock
except ImportError:
    from gevent.coros import RLock


logger = logging.getLogger(__name__)


class FlushingDict(object):
    """A dict that periodically flushes its content to a callback.

    The dict flushes after a specified time since the latest entry
    was added, or when it has reached its maximum size.

    This dict is thread safe. Keys must be hashable. New values for an
    existing keys will overwrite the previous values.

    """

    def __init__(self, size, flush_latency_seconds, callback):
        # Elements contained in the dict that force a flush.
        self.size = size

        # How much time we wait for other key-values before flushing.
        self.flush_latency_seconds = flush_latency_seconds

        # Function to flush the data to.
        self.callback = callback

        # This contains all the key-values received and not yet
        # flushed.
        self.d = dict()

        # The greenlet in which we schedule the flush. Whenever a new
        # key-value is added, the greenlet is killed and rescheduled.
        self.flush_greenlet = None

        # This lock ensures that if a key-value arrives while flush is
        # executing, it is not inserted in the dict until flush
        # terminates.
        self.d_lock = RLock()

        # This lock ensures that we do not change the flush greenlet
        # while it is executing.
        self.f_lock = RLock()

    def _deschedule(self):
        """Remove the scheduling of the flush."""
        with self.f_lock:
            if self.flush_greenlet is not None:
                self.flush_greenlet.kill()
                self.flush_greenlet = None

    def add(self, key, value):
        logger.info("Adding item %s", key)
        with self.d_lock:
            self.d[key] = value
        self._deschedule()
        if len(self.d) >= self.size:
            self.flush_greenlet = gevent.spawn(self.flush)
        else:
            self.flush_greenlet = gevent.spawn_later(
                self.flush_latency_seconds,
                self.flush)

    def flush(self):
        logger.info("Flushing items")
        with self.f_lock:
            with self.d_lock:
                to_send = self.d.items()
                self.d = dict()
            self.callback(to_send)

    def __contains__(self, key):
        return key in self.d
