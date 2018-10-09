#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2016 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013-2015 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
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

"""Manager for the set of workers.

"""

import logging
import random
from datetime import timedelta

import gevent.lock
from gevent.event import Event

from cms.db import SessionGen
from cms.grading.Job import JobGroup
from cmscommon.datetime import make_datetime, make_timestamp


logger = logging.getLogger(__name__)


class WorkerPool:
    """This class keeps the state of the workers attached to ES, and
    allow the ES to get a usable worker when it needs it.

    """

    WORKER_INACTIVE = None
    WORKER_DISABLED = "disabled"

    # Seconds after which we declare a worker stale.
    WORKER_TIMEOUT = timedelta(seconds=600)

    def __init__(self, service):
        """service (Service): the EvaluationService using this
        WorkerPool.

        """
        self._service = service
        self._worker = {}
        # These dictionary stores data about the workers (identified
        # by their shard number). Schedule disabling to True means
        # that we are going to disable the worker as soon as possible
        # (when it finishes the current operations). The current
        # operations are also discarded because we already re-assigned
        # it. Ignore is true if the next results coming from the
        # worker should be discarded. Operations is the list of
        # operations currently executing. Operations to ignore is the
        # list of operations to ignore in the next batch of results.
        # Type: {int: [ESOperation]}
        self._operations = {}
        # Type: {int: [ESOperation]}
        self._operations_to_ignore = {}
        # Type: {int: Datetime|None}
        self._start_time = {}
        # Type: {int: bool}
        self._schedule_disabling = {}
        # Type: {int: bool}
        self._ignore = {}

        # TODO: given the number of pieces data associated to each
        # worker, this class could be simplified by creating a new
        # WorkerPoolItem class.

        # TODO: at the moment race conditions during the periodic
        # checks cannot be excluded. A refactoring of this class
        # should take that into account.

        # A reverse lookup dictionary mapping operations to shards.
        # Type: {ESOperation: int}
        self._operations_reverse = dict()

        # A lock to ensure that the reverse lookup stays in sync with
        # the operations lists.
        self._operation_lock = gevent.lock.RLock()

        # Event set when there are workers available to take jobs. It
        # is only guaranteed that if a worker is available, then this
        # event is set. In other words, the fact that this event is
        # set does not mean that there is a worker available.
        self._workers_available_event = Event()

    def __len__(self):
        return len(self._worker)

    def __contains__(self, operation):
        return operation in self._operations_reverse

    def _remove_operations(self, shard, new_operation):
        """Safely remove operations from a worker, assigning a new status.

        shard (int): the worker from which to remove operations.
        new_operations (unicode|None): the new operation, which can be
            INACTIVE or DISABLED.

        """
        with self._operation_lock:
            operations = self._operations[shard]
            self._operations[shard] = new_operation
            if isinstance(operations, list):
                for operation in operations:
                    del self._operations_reverse[operation]

    def _add_operations(self, shard, operations):
        """Assigns new operations to a currently inactive worker.

        shard (int): shard of the worker.
        operations ([ESOperation]) operations to assign to the worker.

        """
        if self._operations[shard] != WorkerPool.WORKER_INACTIVE:
            raise ValueError("Shard %s is already doing an operation.", shard)
        with self._operation_lock:
            self._operations[shard] = operations
            for operation in operations:
                self._operations_reverse[operation] = shard

    def wait_for_workers(self):
        """Wait until a worker might be available."""
        self._workers_available_event.wait()

    def add_worker(self, worker_coord):
        """Add a new worker to the worker pool.

        worker_coord (ServiceCoord): the coordinates of the worker.

        """
        shard = worker_coord.shard
        # Instruct GeventLibrary to connect ES to the Worker.
        self._worker[shard] = self._service.connect_to(
            worker_coord,
            on_connect=self.on_worker_connected)

        # And we fill all data.
        self._operations[shard] = WorkerPool.WORKER_INACTIVE
        self._operations_to_ignore[shard] = []
        self._start_time[shard] = None
        self._schedule_disabling[shard] = False
        self._ignore[shard] = False
        self._workers_available_event.set()
        logger.debug("Worker %s added.", shard)

    def on_worker_connected(self, worker_coord):
        """To be called when a worker comes alive after being
        offline. We use this callback to instruct the worker to
        precache all files concerning the contest.

        worker_coord (ServiceCoord): the coordinates of the worker
                                     that came online.

        """
        shard = worker_coord.shard
        logger.info("Worker %s online again.", shard)
        if self._service.contest_id is not None:
            self._worker[shard].precache_files(
                contest_id=self._service.contest_id
            )
        # We don't requeue the operation, because a connection lost
        # does not invalidate a potential result given by the worker
        # (as the problem was the connection and not the machine on
        # which the worker is). But the worker could have been idling,
        # so we wake up the consumers.
        self._workers_available_event.set()

    def acquire_worker(self, operations):
        """Tries to assign an operation to an available worker. If no workers
        are available then this returns None, otherwise this returns
        the chosen worker.

        operations ([ESOperation]): the operations to assign to a worker.

        return (int|None): None if no workers are available, the worker
            assigned to the operation otherwise.

        """
        # We look for an available worker.
        try:
            shard = self.find_worker(WorkerPool.WORKER_INACTIVE,
                                     require_connection=True,
                                     random_worker=True)
        except LookupError:
            self._workers_available_event.clear()
            return None

        # Then we fill the info for future memory.
        self._add_operations(shard, operations)

        logger.debug("Worker %s acquired.", shard)
        self._start_time[shard] = make_datetime()

        with SessionGen() as session:
            job_group_dict = \
                JobGroup.from_operations(operations, session).export_to_dict()

        logger.info("Asking worker %s to %s.", shard,
                    ", ".join("`%s'" % operation for operation in operations))

        self._worker[shard].execute_job_group(
            job_group_dict=job_group_dict,
            callback=self._service.action_finished,
            plus=shard)
        return shard

    def release_worker(self, shard):
        """To be called by ES when it receives a notification that an
        operation finished.

        Note: if the worker is scheduled to be disabled, then we
        disable it, and notify the ES to discard the outcome obtained
        by the worker.

        shard (int): the worker to release.

        return (bool|[ESOperation]): if boolean, whether the result is
            to be ignored; if a list, the list of operation for which
            the results should be ignored.

        """
        if self._operations[shard] == WorkerPool.WORKER_INACTIVE:
            err_msg = "Trying to release worker while it's inactive."
            logger.error(err_msg)
            raise ValueError(err_msg)

        # If the worker has already been disabled, ignore the result
        # and keep the worker disabled.
        if self._operations[shard] == WorkerPool.WORKER_DISABLED:
            return True

        ret = self._ignore[shard]
        with self._operation_lock:
            to_ignore = self._operations_to_ignore[shard]
            self._operations_to_ignore[shard] = []
        self._start_time[shard] = None
        self._ignore[shard] = False
        if self._schedule_disabling[shard]:
            self._remove_operations(shard, WorkerPool.WORKER_DISABLED)
            self._schedule_disabling[shard] = False
            logger.info("Worker %s released and disabled.", shard)
        else:
            self._remove_operations(shard, WorkerPool.WORKER_INACTIVE)
            self._workers_available_event.set()
            logger.debug("Worker %s released.", shard)
        if ret is False and to_ignore != []:
            return to_ignore
        else:
            return ret

    def find_worker(self, operation, require_connection=False,
                    random_worker=False):
        """Return a worker whose assigned operation is operation.

        Remember that there is a placeholder operation to signal that the
        worker is not doing anything (or disabled).

        operation (ESOperation|unicode|None): the operation we are
            looking for, or WorkerPool.WORKER_*.
        require_connection (bool): True if we want to find a worker
            doing the operation and that is actually connected to us
            (i.e., did not die).
        random_worker (bool): if True, choose uniformly amongst all
            workers doing the operation.

        returns (int): the shard of a worker working on operation.

        raise (LookupError): if nothing has been found.

        """
        pool = []
        for shard, worker_operation in self._operations.items():
            if worker_operation == operation:
                if not require_connection or self._worker[shard].connected:
                    pool.append(shard)
                    if not random_worker:
                        return shard
        if pool == []:
            raise LookupError("No such operation.")
        else:
            return random.choice(pool)

    def ignore_operation(self, operation):
        """Mark the operation to be ignored.

        operation (ESOperation): the operation to ignore.

        raise (LookupError): if operation is not found.

        """
        try:
            with self._operation_lock:
                shard = self._operations_reverse[operation]
                self._operations_to_ignore[shard].append(operation)
        except LookupError:
            logger.debug("Asked to ignore operation `%s' "
                         "that cannot be found.", operation)
            raise

    def get_status(self):
        """Returns a dict with info about the current status of all
        workers.

        return (dict): dict of info: current operation, starting time,
            number of errors, and additional data specified in the
            operation.

        """
        result = dict()
        for shard in self._worker.keys():
            s_time = self._start_time[shard]
            s_time = make_timestamp(s_time) if s_time is not None else None

            result["%d" % shard] = {
                'connected': self._worker[shard].connected,
                'operations': [operation.to_dict()
                               for operation in self._operations[shard]]
                if isinstance(self._operations[shard], list)
                else self._operations[shard],
                'start_time': s_time}
        return result

    def check_timeouts(self):
        """Check if some worker is not responding in too much time. If
        this is the case, the worker is scheduled for disabling, and
        we send it a message trying to shut it down.

        return ([ESOperation]): list of operations assigned to worker
            that timeout.

        """
        now = make_datetime()
        lost_operations = []
        for shard in self._worker:
            if self._start_time[shard] is not None:
                active_for = now - self._start_time[shard]

                if active_for > WorkerPool.WORKER_TIMEOUT:
                    # Here shard is a working worker with no sign of
                    # intelligent life for too much time.
                    logger.error("Disabling and shutting down "
                                 "worker %d because of no response "
                                 "in %s.", shard, active_for)
                    is_busy = (self._operations[shard] !=
                               WorkerPool.WORKER_INACTIVE and
                               self._operations[shard] !=
                               WorkerPool.WORKER_DISABLED)
                    assert is_busy

                    # We return the operation so ES can do what it needs.
                    if not self._ignore[shard] and \
                            isinstance(self._operations[shard], list):
                        for operation in self._operations[shard]:
                            if operation not in \
                                    self._operations_to_ignore[shard]:
                                lost_operations.append(operation)

                    # Also, we are not trusting it, so we are not
                    # assigning it new operations even if it comes back to
                    # life.
                    self._schedule_disabling[shard] = True
                    self._ignore[shard] = True
                    self.release_worker(shard)
                    self._worker[shard].quit(
                        reason="No response in %s." % active_for)

        return lost_operations

    def disable_worker(self, shard):
        """Disable a worker.

        shard (int): which worker to disable.

        return ([ESOperation]): list of non-ignored operations
            assigned to the worker.

        raise (ValueError): if worker is already disabled.

        """
        if self._operations[shard] == WorkerPool.WORKER_DISABLED:
            err_msg = \
                "Trying to disable already disabled worker %s." % shard
            logger.warning(err_msg)
            raise ValueError(err_msg)

        lost_operations = []
        if self._operations[shard] == WorkerPool.WORKER_INACTIVE:
            self._operations[shard] = WorkerPool.WORKER_DISABLED

        else:
            # We return all non-ignored operations so ES can do what
            # it needs.
            if not self._ignore[shard]:
                to_ignore = self._operations_to_ignore[shard]
                if isinstance(self._operations[shard], list):
                    for operation in self._operations[shard]:
                        if operation not in to_ignore:
                            lost_operations.append(operation)

            # And we mark the worker as disabled (until another action
            # is taken).
            self._schedule_disabling[shard] = True
            self._operations_to_ignore[shard] = []
            self._ignore[shard] = True
            self.release_worker(shard)

        logger.info("Worker %s disabled.", shard)
        return lost_operations

    def enable_worker(self, shard):
        """Enable a worker that previously was disabled.

        shard (int): which worker to enable.

        raise (ValueError): if worker is not disabled.

        """
        if self._operations[shard] != WorkerPool.WORKER_DISABLED:
            err_msg = \
                "Trying to enable worker %s which is not disabled." % shard
            logger.error(err_msg)
            raise ValueError(err_msg)

        self._operations[shard] = WorkerPool.WORKER_INACTIVE
        self._operations_to_ignore[shard] = []
        self._workers_available_event.set()
        logger.info("Worker %s enabled.", shard)

    def check_connections(self):
        """Check if a worker we assigned an operation to disconnects. In this
        case, requeue the operation.

        return ([ESOperation]): list of operations assigned to worker
            that disconnected.

        """
        lost_operations = []
        for shard in self._worker:
            if not self._worker[shard].connected and \
                    self._operations[shard] not in [
                        WorkerPool.WORKER_DISABLED,
                        WorkerPool.WORKER_INACTIVE]:
                if not self._ignore[shard]:
                    lost_operations += self._operations[shard]
                self.release_worker(shard)

        return lost_operations
