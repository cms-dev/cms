#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2014-2016 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Priority queue used in triggered services.

This file implements a greenlet-safe priority queue to be used as the
operation queue for triggered services. External clients can use the
queue to store QueueItems (which should be subclassed). No duplicate
items can be stored in the queue

Since the queue provides the ability of changing priorities and
removing arbtrary items, the QueueItems must be hashable, as they are
used in a reverse lookup array.

The priority is given by two fields: priority, which is an integer
among the PRIORITY_classes defined in PriorityQueue, and timestamp,
which is supposed to be the timestamp in which the operation was
requested for the first time. Timestamp is only used to discern
between entries with the same priority.

The queue stores entries in the QueueEntry format, a class that stores
together the three data point: item, priority, and timestamp.

"""

from datetime import datetime
from functools import total_ordering
from typing import TypedDict
import typing

from gevent.event import Event

from cmscommon.datetime import make_datetime, make_timestamp


class QueueItem:

    """Payload of an item in the queue.

    Must be hashable.

    """

    def to_dict(self) -> dict:
        """Return a dict() representation of the object."""
        return self.__dict__


QueueItemT = typing.TypeVar("QueueItemT", bound=QueueItem)


@total_ordering
class QueueEntry(typing.Generic[QueueItemT]):

    """Type of the actual objects in the queue.

    """

    def __init__(
        self, item: QueueItemT, priority: int, timestamp: datetime, index: int
    ):
        """Create a QueueEntry object.

        item: the payload.
        priority: the priority.
        timestamp: the timestamp of first request.
        index: used to enforce strict ordering.

        """
        # TODO: item is not actually necessary, as we store the whole
        # item in the reverse lookup array.
        self.item = item
        self.priority = priority
        self.timestamp = timestamp
        self.index = index

    def __eq__(self, other):
        """Return whether self and other have the same priority."""
        return (self.priority, self.timestamp, self.index) \
               == (other.priority, other.timestamp, other.index)

    def __lt__(self, other):
        """Return whether self has higher priority than other."""
        return (self.priority, self.timestamp, self.index) \
               < (other.priority, other.timestamp, other.index)


class QueueEntryDict(TypedDict):
    """Serialized form of QueueEntry, for sending over RPC."""

    item: dict
    priority: int
    timestamp: float


class PriorityQueue(typing.Generic[QueueItemT]):

    """A priority queue.

    It is greenlet-safe, and offers the ability of changing priorities
    and removing arbitrary items.

    The queue is implemented as a custom min-heap. The priority is a
    mix of a discrete priority level and of the timestamp. The
    elements of the queue are QueueItems.

    """

    PRIORITY_EXTRA_HIGH = 0
    PRIORITY_HIGH = 1
    PRIORITY_MEDIUM = 2
    PRIORITY_LOW = 3
    PRIORITY_EXTRA_LOW = 4

    def __init__(self):
        """Create a priority queue."""
        # The queue: a min-heap whose elements are of the form
        # (priority, timestamp, item), where item is the actual data.
        self._queue: list[QueueEntry[QueueItemT]] = []

        # Reverse lookup for the items in the queue: a dictionary
        # associating the index in the queue to each item.
        self._reverse: dict[QueueItemT, int] = {}

        # Event to signal that there are items in the queue.
        self._event = Event()

        # Index of the next element that will be added to the queue.
        self._next_index = 0

    def __len__(self):
        return len(self._queue)

    def _verify(self) -> bool:
        """Make sure that the internal state of the queue is consistent.

        This is used only for testing.

        """
        if len(self._queue) != len(self._reverse):
            return False
        if len(self._queue) != self.length():
            return False
        if self.empty() != (self.length() == 0):
            return False
        if self._event.isSet() == self.empty():
            return False
        for item, idx in self._reverse.items():
            if self._queue[idx].item != item:
                return False
        return True

    def __contains__(self, item: QueueItemT) -> bool:
        """Implement the 'in' operator for an item in the queue.

        item: an item to search.

        return: True if item is in the queue.

        """
        return item in self._reverse

    def _swap(self, idx1: int, idx2: int):
        """Swap two elements in the queue, keeping their reverse
        indices up to date.

        idx1: the index of the first element.
        idx2: the index of the second element.

        """
        self._queue[idx1], self._queue[idx2] = \
            self._queue[idx2], self._queue[idx1]
        self._reverse[self._queue[idx1].item] = idx1
        self._reverse[self._queue[idx2].item] = idx2

    def _up_heap(self, idx: int) -> int:
        """Take the element in position idx up in the heap until its
        position is the right one.

        idx: the index of the element to lift.

        return: the new index of the element.

        """
        while idx > 0:
            parent = (idx - 1) // 2
            if self._queue[idx] < self._queue[parent]:
                self._swap(parent, idx)
                idx = parent
            else:
                break
        return idx

    def _down_heap(self, idx: int) -> int:
        """Take the element in position idx down in the heap until its
        position is the right one.

        idx: the index of the element to lower.

        return: the new index of the element.

        """
        last = len(self._queue) - 1
        while 2 * idx + 1 <= last:
            child = 2 * idx + 1
            if 2 * idx + 2 <= last and \
                    self._queue[2 * idx + 2] < self._queue[child]:
                child = 2 * idx + 2
            if self._queue[child] < self._queue[idx]:
                self._swap(child, idx)
                idx = child
            else:
                break
        return idx

    def _updown_heap(self, idx: int) -> int:
        """Perform both operations of up_heap and down_heap on an
        element.

        idx: the index of the element to lift.

        return: the new index of the element.

        """
        idx = self._up_heap(idx)
        return self._down_heap(idx)

    def push(
        self,
        item: QueueItemT,
        priority: int | None = None,
        timestamp: datetime | None = None,
    ) -> bool:
        """Push an item in the queue. If timestamp is not specified,
        uses the current time.

        item: the item to add to the queue.
        priority: the priority of the item, or None for
            medium priority.
        timestamp: the time of the submission, or None
            to use now.

        return: false if the element was already in the queue
            and was not pushed again, true otherwise.

        """
        if item in self._reverse:
            return False

        if priority is None:
            priority = PriorityQueue.PRIORITY_MEDIUM
        if timestamp is None:
            timestamp = make_datetime()

        index = self._next_index
        self._next_index += 1

        self._queue.append(QueueEntry(item, priority, timestamp, index))
        last = len(self._queue) - 1
        self._reverse[item] = last
        self._up_heap(last)

        # Signal to listener greenlets that there might be something.
        self._event.set()

        return True

    def top(self, wait: bool = False) -> QueueEntry[QueueItemT]:
        """Return the first element in the queue without extracting it.

        wait: if True, block until an element is present.

        return: first element in the queue.

        raise (LookupError): on empty queue if wait was false.

        """
        if not self.empty():
            return self._queue[0]
        else:
            if not wait:
                raise LookupError("Empty queue.")
            else:
                while True:
                    if self.empty():
                        self._event.wait()
                        continue
                    return self._queue[0]

    def pop(self, wait: bool = False) -> QueueEntry[QueueItemT]:
        """Extract (and return) the first element in the queue.

        wait: if True, block until an element is present.

        return: first element in the queue.

        raise (LookupError): on empty queue, if wait was false.

        """
        top = self.top(wait)
        last = len(self._queue) - 1
        self._swap(0, last)

        del self._reverse[top.item]
        del self._queue[last]

        # last is 0 when the queue becomes empty.
        if last > 0:
            self._down_heap(0)
        else:
            # Signal that there is nothing left for listeners.
            self._event.clear()
        return top

    def remove(self, item: QueueItemT) -> QueueEntry[QueueItemT]:
        """Remove an item from the queue. Raise a KeyError if not present.

        item: the item to remove.

        return: the complete entry removed.

        raise (KeyError): if item not present.

        """
        pos = self._reverse[item]
        entry = self._queue[pos]

        last = len(self._queue) - 1
        self._swap(pos, last)

        del self._reverse[item]
        del self._queue[last]
        if pos != last:
            self._updown_heap(pos)

        if self.empty():
            self._event.clear()

        return entry

    def set_priority(self, item: QueueItemT, priority: int):
        """Change the priority of an item inside the queue. Raises an
        exception if the item is not in the queue.

        item: the item whose priority needs to change.
        priority: the new priority.

        raise (LookupError): if item not present.

        """
        pos = self._reverse[item]
        self._queue[pos].priority = priority
        self._updown_heap(pos)

    def length(self) -> int:
        """Return the number of elements in the queue.

        return: length of the queue

        """
        return len(self._queue)

    def empty(self) -> bool:
        """Return if the queue is empty.

        return: is the queue empty?

        """
        return self.length() == 0

    def get_status(self) -> list[QueueEntryDict]:
        """Return the content of the queue. Note that the order may be not
        correct, but the first element is the one at the top.

        return: a list of entries containing the
            representation of the item, the priority and the
            timestamp.

        """
        return [{'item': entry.item.to_dict(),
                 'priority': entry.priority,
                 'timestamp': make_timestamp(entry.timestamp)}
                for entry in self._queue]


# Fake objects for testing follow.


class FakeQueueItem(QueueItem):
    """A fake queue item, defined by a single string."""
    def __init__(self, title):
        self._title = title

    def __eq__(self, other):
        return self._title == other._title

    def __hash__(self):
        return hash(self._title)

    def __str__(self):
        return self._title
