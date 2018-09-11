#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa
from six import iteritems

import logging
import random
from contextlib import contextmanager
from datetime import timedelta, datetime
from threading import Condition
from typing import Dict, Optional, ContextManager

from gevent import Greenlet, Timeout
from gevent.event import AsyncResult
from gevent.lock import RLock

from cms import ServiceCoord
from cms.grading.Job import JobGroup
from cms.io import RemoteServiceClient, RPCError
from cmscommon.datetime import make_datetime, make_timestamp


logger = logging.getLogger(__name__)


class AbortOperation(Exception):
    pass


class WorkerPoolItem(object):

    # Seconds after which we declare a worker stale.
    WORKER_TIMEOUT = timedelta(seconds=600)

    def __init__(self,
                 rpc_client: RemoteServiceClient,
                 pool_status: Condition,
                 contest_id: Optional[int]= None):
        if rpc_client.remote_service_coord.name != "Worker":
            raise ValueError("RPC client isn't for Worker")
        self.rpc_client: RemoteServiceClient = rpc_client

        self.rpc_client.add_on_connect_handler(self._on_connection)
        self.rpc_client.add_on_disconnect_handler(self._on_disconnection)

        self.active: bool = True
        self.connected: bool = self.rpc_client.connected
        self.greenlet: Optional[Greenlet] = None

        self.pool_status: Condition = pool_status

        self.job_group: Optional[JobGroup] = None
        self.start_time: Optional[datetime] = None

        self.contest_id: Optional[int] = contest_id

    @property
    def shard(self):
        return self.rpc_client.remote_service_coord.shard

    @property
    def ready(self):
        with self.pool_status:
            return self.active and self.connected and self.greenlet is None

    def activate(self):
        with self.pool_status:
            self.active = True
            self.pool_status.notify_all()

    def deactivate(self):
        with self.pool_status:
            self.active = False
            self.pool_status.notify_all()

    def _on_connection(self):
        with self.pool_status:
            self.connected = True
            self.pool_status.notify_all()
        self.rpc_client.precache_files(contest_id=self.contest_id)

    def _on_disconnection(self):
        with self.pool_status:
            self.connected = False
            self.pool_status.notify_all()

    def run(self, job_group: JobGroup) -> AsyncResult:
        result = AsyncResult()
        with self.pool_status:
            assert self.ready
            self.greenlet = Greenlet(self._runner, job_group, result)
            # To avoid race conditions, link must happen before spawn
            # (or else we might link a greenlet that is already dead).
            self.greenlet.link(self._on_finished_running)
            self.greenlet.spawn()
            self.pool_status.notify_all()
        return result

    def _on_finished_running(self, unused_greenlet):
        assert unused_greenlet is self.greenlet
        with self.pool_status:
            self.greenlet = None
            self.pool_status.notify_all()

    def abort(self):
        with self.pool_status:
            if self.greenlet is not None:
                self.greenlet.kill(AbortOperation, block=False)

    def _runner(self, job_group: JobGroup, result: AsyncResult):
        self.job_group = job_group
        self.start_time = make_datetime()
        try:
            response_dict = self.rpc_client\
                .execute_job_group(job_group_dict=job_group.export_to_dict())\
                .get(timeout=self.WORKER_TIMEOUT.total_seconds())
        except Timeout as e:
            logger.error("Disabling and shutting down worker %d "
                         "because of no response in %s.",
                         self.shard, self.WORKER_TIMEOUT)
            self.rpc_client.quit(
                reason="No response in %s." % self.WORKER_TIMEOUT)
            result.set_exception(e)
        except AbortOperation as e:
            logger.info("Aborting operation")
            self.rpc_client.quit(reason="Asked to abort.")
            result.set_exception(e)
        except RPCError as e:
            logger.error("Error while communicating")
            result.set_exception(e)
        else:
            try:
                response = JobGroup.import_from_dict(response_dict)
            except Exception as e:
                result.set_exception(e)
            else:
                result.set(response)
        finally:
            self.job_group = None
            self.start_time = None
        logger.debug("Worker %s released.", self.shard)

    def get_status(self):
        # Since this method is just for reporting we're not very worried
        # about race conditions and thus we don't acquire the condition.
        status = {
            'active': self.active,
            'connected': self.connected,
            'running': self.greenlet is not None}
        if self.job_group is not None:
            status['operations'] = [job.operation.to_dict()
                                    for job in self.job_group.jobs]
        if self.start_time is not None:
            status['start_time'] = make_timestamp(self.start_time)
        return status


class WorkerPool(object):

    def __init__(self, contest_id: Optional[int]=None):
        self.pool_status: Condition = Condition(RLock())
        self.workers: Dict[int, WorkerPoolItem] = dict()

        self.contest_id = contest_id

    def add_worker(self, rpc_client: RemoteServiceClient):
        worker = WorkerPoolItem(rpc_client, self.pool_status,
                                contest_id=self.contest_id)
        self.workers[worker.shard] = worker
        logger.debug("Worker %s added.", worker.shard)

    @contextmanager
    def acquire_worker(self) -> ContextManager[WorkerPoolItem]:
        with self.pool_status:
            while True:
                ready_items = list(item for item in self.workers if item.ready)
                if ready_items:
                    yield random.choice(ready_items)
                    break
                self.pool_status.wait()

    def get_status(self):
        status = dict()
        for shard, worker in iteritems(self.workers):
            status["%d" % shard] = worker.get_status()
        return status

    def disable_worker(self, shard):
        logger.info("Worker %s disabled.", shard)
        self.workers[shard].deactivate()

    def enable_worker(self, shard):
        logger.info("Worker %s enabled.", shard)
        self.workers[shard].activate()

    @property
    def num_workers(self):
        return len(self.workers)
