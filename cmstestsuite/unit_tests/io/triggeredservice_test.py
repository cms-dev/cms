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

"""Tests for the triggered service system.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import gevent
import unittest

from mock import patch

from cms import Address
from cms.io import Executor, FakeQueueItem, TriggeredService


class Notifier(object):
    def __init__(self):
        self._notifications = 0

    def notify(self):
        self._notifications += 1

    def get_notifications(self):
        return self._notifications


class FakeExecutor(Executor):
    def __init__(self, notifier, batch_executions=False):
        super(FakeExecutor, self).__init__(batch_executions)
        self._notifier = notifier

    def execute(self, operation):
        self._notifier.notify()


class FakeSlowExecutor(FakeExecutor):
    def __init__(self, notifier, slowness):
        super(FakeSlowExecutor, self).__init__(notifier)
        self._slowness = slowness

    def execute(self, operation):
        gevent.sleep(self._slowness)
        super(FakeSlowExecutor, self).execute(operation)


class FakeBatchExecutor(FakeExecutor):
    def __init__(self, notifier):
        super(FakeBatchExecutor, self).__init__(notifier,
                                                batch_executions=True)

    def execute(self, operations):
        # Notifying only once per call, not once per operation.
        super(FakeBatchExecutor, self).execute(operations[0])


class FakeTriggeredService(TriggeredService):
    def __init__(self, shard, timeout):
        super(FakeTriggeredService, self).__init__(shard)
        self._timeout = timeout

        # Operations scheduled to be returned at the next
        # missing_operations().
        self._operations = []

    def add_missing_operation(self, operation):
        self._operations.append(operation)

    def _missing_operations(self):
        counter = 0
        while self._operations != []:
            counter += 1
            self.enqueue(self._operations[0])
            del self._operations[0]
        return counter


class TestTriggeredService(unittest.TestCase):

    def setUp(self):
        patcher = patch("cms.io.service.get_service_address")
        self.get_service_address = patcher.start()
        self.addCleanup(patcher.stop)

        self.notifiers = [Notifier(), Notifier()]

    def setUpService(self, timeout=None, batch=False):
        self.get_service_address.return_value = Address('127.0.0.1', '12345')
        # By default, do not rely on the periodic job to trigger
        # operations.
        self.service = FakeTriggeredService(0, timeout)
        for notifier in self.notifiers:
            self.service.add_executor(FakeExecutor(notifier))
        self.service.start_sweeper(timeout)

    def test_success(self):
        """Test a simple success case."""
        self.setUpService()
        self.service.enqueue(FakeQueueItem('op 0'))
        self.service.enqueue(FakeQueueItem('op 1'))
        # Same element should not trigger new operations.
        self.service.enqueue(FakeQueueItem('op 1'))
        gevent.sleep(0.01)
        for notifier in self.notifiers:
            self.assertEqual(notifier.get_notifications(), 2)

    def test_sweeper(self):
        """Test the sweeper.

        Test that operations added with _missing_operations are
        executed.

        """
        self.setUpService(0.1)
        self.service.add_missing_operation(FakeQueueItem('op 0'))
        self.service.add_missing_operation(FakeQueueItem('op 1'))
        gevent.sleep(0.2)
        for notifier in self.notifiers:
            self.assertEqual(notifier.get_notifications(), 2)

    def test_bad_executor(self):
        """Test that a slow executor does not block the others."""
        self.setUpService()
        # Adding an executor that takes 0.1s to perform anything.
        slow_notifier = Notifier()
        self.service.add_executor(FakeSlowExecutor(slow_notifier, 0.1))

        # First round of operations.
        self.service.enqueue(FakeQueueItem('op 0'))
        gevent.sleep(0.01)
        for notifier in self.notifiers:
            self.assertEqual(notifier.get_notifications(), 1)
        self.assertEqual(slow_notifier.get_notifications(), 0)

        # Second round.
        self.service.enqueue(FakeQueueItem('op 1'))
        gevent.sleep(0.01)
        for notifier in self.notifiers:
            self.assertEqual(notifier.get_notifications(), 2)
        self.assertEqual(slow_notifier.get_notifications(), 0)

        # After 0.1 * #operations, the slow one picked up.
        gevent.sleep(0.25)
        self.assertEqual(slow_notifier.get_notifications(), 2)

    def test_batch(self):
        """Test a batch executor."""
        self.setUpService()
        batch_notifier = Notifier()
        self.service.add_executor(FakeBatchExecutor(batch_notifier))
        self.service.enqueue(FakeQueueItem('op 0'))
        self.service.enqueue(FakeQueueItem('op 1'))
        gevent.sleep(0.01)
        for notifier in self.notifiers:
            self.assertEqual(notifier.get_notifications(), 2)
        # Just one call to the batch executor.
        self.assertEqual(batch_notifier.get_notifications(), 1)


if __name__ == "__main__":
    unittest.main()
