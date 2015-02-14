#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2014 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Tests for the priority queue.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import gevent
import gevent.socket
import gevent.event

from cms.io import FakeQueueItem, PriorityQueue
from cmscommon.datetime import make_datetime


class TestPriorityQueue(unittest.TestCase):

    def setUp(self):
        # Some items to play with.
        self.item_a = FakeQueueItem("a")
        self.item_b = FakeQueueItem("b")
        self.item_c = FakeQueueItem("c")
        self.item_d = FakeQueueItem("d")
        self.item_e = FakeQueueItem("e")

        # And an empty priority queue.
        self.queue = PriorityQueue()

    def tearDown(self):
        self.queue = PriorityQueue()
        pass

    def test_success(self):
        """Verify a simple success case.

        Push three items in the wrong order, and recover them.

        """
        self.assertTrue(self.queue._verify())

        self.queue.push(self.item_a, PriorityQueue.PRIORITY_LOW)
        self.queue.push(self.item_b, PriorityQueue.PRIORITY_MEDIUM,
                        timestamp=make_datetime(10))
        self.queue.push(self.item_c, PriorityQueue.PRIORITY_MEDIUM,
                        timestamp=make_datetime(5))
        self.assertTrue(self.queue._verify())

        self.assertEqual(self.queue.top().item, self.item_c)
        top = self.queue.pop()
        self.assertEqual(top.item, self.item_c)
        top = self.queue.pop()
        self.assertEqual(top.item, self.item_b)
        top = self.queue.pop()
        self.assertEqual(top.item, self.item_a)
        self.assertTrue(self.queue._verify())

        with self.assertRaises(LookupError):
            self.queue.pop()

    def test_set_priority(self):
        """Test that priority get changed and item moved."""
        self.queue.push(self.item_a, PriorityQueue.PRIORITY_LOW)
        self.queue.push(self.item_b, PriorityQueue.PRIORITY_MEDIUM,
                        timestamp=make_datetime(10))
        self.queue.push(self.item_c, PriorityQueue.PRIORITY_MEDIUM,
                        timestamp=make_datetime(5))

        self.queue.set_priority(self.item_a, PriorityQueue.PRIORITY_HIGH)
        self.assertTrue(self.queue._verify())
        self.assertEqual(self.queue.top().item, self.item_a)

    def test_pop_waiting(self):
        """Test that pop with waiting works.

        Spawn a greenlet waiting for the queue to become non-empty,
        and make sure that it wakes up when a new item arrives. Twice,
        to be sure.

        """
        def waiting():
            obj_read = self.queue.pop(wait=True)
            self.assertEqual(obj_read.item, self.item_a)
            obj_read = self.queue.pop(wait=True)
            self.assertEqual(obj_read.item, self.item_b)

        greenlet = gevent.spawn(waiting)
        gevent.sleep(0.01)
        self.assertTrue(self.queue._verify())

        self.queue.push(self.item_a)
        self.assertTrue(self.queue._verify())
        gevent.sleep(0.01)
        self.assertTrue(self.queue._verify())

        # The second time we push on top of the queue, but the first
        # item should have already been collected.
        self.queue.push(self.item_b, priority=PriorityQueue.PRIORITY_HIGH)
        gevent.sleep(0.01)
        self.assertTrue(self.queue._verify())
        self.assertTrue(greenlet.successful())

    def test_pop_multiple_waiting(self):
        """Test that pop with waiting works, even with several consumers.

        Spawn three greenlets waiting for the queue to become
        non-empty, and make sure that they get fed eventually.

        """
        def waiting():
            obj_read = self.queue.pop(wait=True)
            self.assertEqual(obj_read.item, self.item_a)

        greenlets = [gevent.spawn(waiting),
                     gevent.spawn(waiting),
                     gevent.spawn(waiting)]

        gevent.sleep(0.01)
        self.queue.push(self.item_a)
        self.assertTrue(self.queue._verify())
        gevent.sleep(0.01)
        self.assertTrue(self.queue._verify())

        # Now exactly one greenlet should have terminated.
        terminated = sum(1 for greenlet in greenlets if greenlet.ready())
        successful = sum(1 for greenlet in greenlets if greenlet.successful())
        self.assertEqual(terminated, 1)
        self.assertEqual(successful, 1)

        self.queue.push(self.item_a)
        self.assertTrue(self.queue._verify())
        gevent.sleep(0.01)
        self.assertTrue(self.queue._verify())
        # Now two.
        terminated = sum(1 for greenlet in greenlets if greenlet.ready())
        successful = sum(1 for greenlet in greenlets if greenlet.successful())
        self.assertEqual(terminated, 2)
        self.assertEqual(successful, 2)

        self.queue.push(self.item_a)
        gevent.sleep(0.01)
        # And three.
        terminated = sum(1 for greenlet in greenlets if greenlet.ready())
        successful = sum(1 for greenlet in greenlets if greenlet.successful())
        self.assertEqual(terminated, 3)
        self.assertEqual(successful, 3)

    def test_remove(self):
        """Test that items get removed."""
        self.queue.push(self.item_a, PriorityQueue.PRIORITY_LOW)
        self.assertFalse(self.item_b in self.queue)

        self.queue.push(self.item_b, PriorityQueue.PRIORITY_MEDIUM,
                        timestamp=make_datetime(10))
        self.queue.push(self.item_c, PriorityQueue.PRIORITY_MEDIUM,
                        timestamp=make_datetime(5))

        self.assertTrue(self.item_b in self.queue)
        self.queue.remove(self.item_b)
        self.assertFalse(self.item_b in self.queue)
        self.queue._verify()


if __name__ == "__main__":
    unittest.main()
