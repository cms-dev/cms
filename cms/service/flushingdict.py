#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2016 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2016 Luca Versari <veluca93@gmail.com>
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

import logging

import gevent
from gevent.lock import RLock

from cmscommon.datetime import monotonic_time


logger = logging.getLogger(__name__)


class FlushingDict:
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

        # This contains all the key-values that are currently being flushed
        self.fd = dict()

        # The greenlet that checks if the dict should be flushed or not
        # TODO: do something if the FlushingDict is deleted
        self.flush_greenlet = gevent.spawn(self._check_flush)

        # This lock ensures that if a key-value arrives while flush is
        # executing, it is not inserted in the dict until flush
        # terminates.
        self.d_lock = RLock()

        # Time when an item was last inserted in the dict
        self.last_insert = monotonic_time()

    def add(self, key, value):
        logger.debug("Adding item %s", key)
        with self.d_lock:
            self.d[key] = value
            self.last_insert = monotonic_time()

    def flush(self):
        logger.debug("Flushing items")
        with self.d_lock:
            self.fd = self.d
            self.d = dict()
        self.callback(list(self.fd.items()))
        self.fd = dict()

    def __contains__(self, key):
        with self.d_lock:
            return key in self.d or key in self.fd

    def _check_flush(self):
        while True:
            while True:
                with self.d_lock:
                    since_last_insert = monotonic_time() - self.last_insert
                    if self.d and (len(self.d) >= self.size
                                   or (since_last_insert
                                       > self.flush_latency_seconds)):
                        break
                gevent.sleep(0.05)
            self.flush()
