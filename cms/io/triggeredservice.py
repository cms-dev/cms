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

"""This file defines a base class for a category of services relying
on notifications and sweeper loops.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging

import gevent
from gevent.event import Event

from cms.io import PriorityQueue, Service, rpc_method
from cmscommon.datetime import monotonic_time


logger = logging.getLogger(__name__)


class Executor(object):  # pylint: disable=R0921

    """A class taking care of executing operations.

    The class can be configured to receive one operation at a time, or
    all available operations in one go.

    In the first case, subclasses must implement an execute() method
    that takes an operation as input and should perform it. In the
    second case, execute() takes a list of operations as input.

    """

    def __init__(self, batch_executions=False):
        """Create an executor.

        batch_executions (bool): if True, the executor will receive a
            list of operations in the queue instead of one operation
            at a time.

        """
        super(Executor, self).__init__()

        self._batch_executions = batch_executions
        self._operation_queue = PriorityQueue()

    def __contains__(self, item):
        """Return whether the item is in the queue.

        item (QueueItem): the item to look for.

        return (bool): whether operation is in the queue.

        """
        return item in self._operation_queue

    def get_status(self):
        """Return a the status of the queues.

        More precisely, a list of entries in the executor's queue. The
        first item is the top item, the others are not in order.

        return ([QueueEntry]): the list with the queued elements.

        """
        return self._operation_queue.get_status()

    def enqueue(self, item, priority=None, timestamp=None):
        """Add an item to the queue.

        item (QueueItem): the item to add.
        priority (int|None) the priority, or None to use default.
        timestamp (datetime|None) the timestamp of the first request
            for the operation, or None to use now.

        return (bool): True if successfully enqueued.

        """
        return self._operation_queue.push(item, priority, timestamp)

    def dequeue(self, item):
        """Remove an item from the queue.

        item (QueueItem): the item to remove.

        """
        self._operation_queue.remove(item)

    def run(self):
        """Monitor the queue, and dispatch operations when available.

        This is an infinite loop that, at each iteration, blocks until
        there is at least an element in the queue, and then extracts
        the operation(s) and dispatch them to the executor. Any error
        during the operation is sent to the logger and then
        suppressed, because the loop must go on.

        """
        while True:
            # Wait for the queue to be non-empty.
            to_execute = [self._operation_queue.pop(wait=True)]
            if self._batch_executions:
                # TODO: shall we yield to other greenlets? I think
                # that it is going to be extremely unlikely to have
                # more than one operations.
                while not self._operation_queue.empty():
                    to_execute.append(self._operation_queue.pop())

            assert len(to_execute) > 0, "Expected at least one element."
            if self._batch_executions:
                try:
                    logger.info("Executing operations `%s' and %d more.",
                                to_execute[0].item, len(to_execute) - 1)
                    self.execute(to_execute)
                    logger.info("Operations `%s' and %d more concluded "
                                "successfully.", to_execute[0].item,
                                len(to_execute) - 1)
                except Exception:
                    logger.error(
                        "Unexpected error when executing operation "
                        "`%s' (and %d more operations).", to_execute[0].item,
                        len(to_execute) - 1, exc_info=True)

            else:
                try:
                    logger.info("Executing operation `%s'.",
                                to_execute[0].item)
                    self.execute(to_execute[0])
                    logger.info("Operation `%s' concluded successfully",
                                to_execute[0].item)
                except Exception:
                    logger.error(
                        "Unexpected error when executing operation `%s'.",
                        to_execute[0].item, exc_info=True)

    def execute(self, entry):
        """Perform a single operation.

        Must be implemented if batch_execution is false.

        entry (QueueEntry|[QueueEntry]): the top element of the queue,
            in case batch_executions is false, or the list of all
            currently available elements, in case it is true - in any
            case, each element contains both the operations and the
            info on priority and timestamp, in case we need to
            re-enqueue the item.

        """
        raise NotImplementedError("Please use a subclass.")


class TriggeredService(Service):

    """A service receiving notifications to perform an operation.

    This is a base class implementing a common pattern in CMS: a
    service performing operations when certain conditions are met.

    Often, the operation is "do something on object x" and the
    condition is a condition on the fields of object x, but this
    pattern is not included in this class, the operation have no need
    to be in that form.

    The pattern is implemented through the following blocks.
    - The method enqueue, which schedules a new operation. This can be
      used by subclasses when they receive a notification that an
      operations is needed, or in any other contexts.
    - A sweeper greenlet that asks subclasses to search and enqueue
      operations that were missed by the previous step.
    - A list of executors (each running in its own greenlet), each of
      which takes care of performing all operations.

    Note that if there are multiple executors, each operation will be
    executed by all of them. Indeed, having multiple executors is
    required when we need to execute slightly different versions of
    the same operation depending on local variables in the
    executors. For example, sending data to different machines.

    If required, subclasses can override enqueue() to change this
    behavior, for example to dispatch different operations to
    different executors.

    """

    def __init__(self, shard):
        """Initialize the sweeper loop.

        shard (int): which service shard to run.

        """
        Service.__init__(self, shard)

        self._executors = []

        self._sweeper_start = None
        self._sweeper_event = Event()
        self._sweeper_started = False
        self._sweeper_timeout = None

    def add_executor(self, executor):
        """Add an executor for the service.

        """
        # Set up and spawn the executors.
        #
        # TODO: link to greenlet and react to deaths.
        self._executors.append(executor)
        gevent.spawn(executor.run)

    def get_executor(self):
        """Return the first executor (without checking it is unique).

        return (Executor): the first executor.

        """
        return self._executors[0]

    def enqueue(self, operation, priority=None, timestamp=None):
        """Add an operation to the queue of each executor.

        operation (QueueItem): the operation to enqueue.
        priority (int|None) the priority, or None to use default.
        timestamp (datetime|None) the timestamp of the first request
            for the operation, or None to use now.

        return (int): the number of executors that successfully added
            the operation to their queue.

        """
        ret = 0
        for executor in self._executors:
            if executor.enqueue(operation, priority, timestamp):
                ret += 1
        return ret

    def dequeue(self, operation):
        """Remove an operation from the queue of each executor.

        operation (QueueItem): the operation to dequeue.

        """
        for executor in self._executors:
            executor.dequeue(operation)

    def start_sweeper(self, timeout):
        """Start sweeper loop with given timeout.

        timeout (float): timeout in seconds.

        """
        if not self._sweeper_started:
            self._sweeper_started = True
            self._sweeper_timeout = timeout

            # TODO: link to greenlet and react to its death.
            gevent.spawn(self._sweeper_loop)
        else:
            logger.warning("Service tried to start the sweeper loop twice.")

    def _sweeper_loop(self):
        """Regularly check for missed operations.

        Run the sweep once every _sweeper_timeout seconds but make
        sure that no two sweeps run simultaneously. That is, start a
        new sweep _sweeper_timeout seconds after the previous one
        started or when the previous one finished, whatever comes
        last.

        The search_operations_not_done RPC method can interfere with
        this regularity, as it tries to run a sweeper as soon as
        possible: immediately, if no sweeper is running, or as soon as
        the current one terminates.

        Any error during the sweep is sent to the logger and then
        suppressed, because the loop must go on.

        """
        while True:
            self._sweeper_start = monotonic_time()
            self._sweeper_event.clear()

            try:
                self._sweep()
            except Exception:
                logger.error("Unexpected error when searching for missed "
                             "operations.", exc_info=True)

            self._sweeper_event.wait(max(self._sweeper_start +
                                         self._sweeper_timeout -
                                         monotonic_time(), 0))

    def _sweep(self):
        """Check for missed operations."""
        counter = self._missing_operations()
        logger.info("Found %d missed operation(s).", counter)

    def _missing_operations(self):
        """Enqueue missed operations, and return their number.

        The service is suppose to enqueue all operations that needs to
        be done, and return the number of operations enqueued.

        return (int): the number of operations enqueued.

        """
        return 0

    @rpc_method
    def search_operations_not_done(self):
        """Make the sweeper loop fire the sweeper as soon as possible."""
        self._sweeper_event.set()

    @rpc_method
    def queue_status(self):
        """Return the status of the queues.

        More precisely, a list indexed by each executor, whose
        elements are the list of entries in the executor's queue. The
        first item is the top item, the others are not in order.

        return ([[QueueEntry]]): the list with the queued elements.

        """
        return [executor.get_status() for executor in self._executors]
