#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2015 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013-2015 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""The service that actually compiles and executes code.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging
import time

import gevent.coros

from cms.io import Service, rpc_method
from cms.db import SessionGen, Contest
from cms.db.filecacher import FileCacher
from cms.grading import JobException
from cms.grading.tasktypes import get_task_type
from cms.grading.Job import Job


logger = logging.getLogger(__name__)


class Worker(Service):
    """This service implement the possibility to compile and evaluate
    submissions in a sandbox. The instructions to follow for the
    operations are in the TaskType classes, while the sandbox is in
    the Sandbox module.

    """

    JOB_TYPE_COMPILATION = "compile"
    JOB_TYPE_EVALUATION = "evaluate"

    def __init__(self, shard):
        Service.__init__(self, shard)
        self.file_cacher = FileCacher(self)

        self.work_lock = gevent.coros.RLock()
        self._last_end_time = None
        self._total_free_time = 0
        self._total_busy_time = 0
        self._number_execution = 0

    @rpc_method
    def precache_files(self, contest_id):
        """RPC to ask the worker to precache of files in the contest.

        contest_id (int): the id of the contest

        """
        # In order to avoid a long-living connection, first fetch the
        # complete list of files and then download the files; since
        # this is just pre-caching, possible race conditions are not
        # dangerous
        logger.info("Precaching files for contest %d.", contest_id)
        with SessionGen() as session:
            contest = Contest.get_from_id(contest_id, session)
            files = contest.enumerate_files(skip_submissions=True,
                                            skip_user_tests=True)
        for digest in files:
            try:
                self.file_cacher.load(digest, if_needed=True)
            except KeyError:
                # No problem (at this stage) if we cannot find the
                # file
                pass

        logger.info("Precaching finished.")

    @rpc_method
    def execute_job(self, job_dict):
        """Receive a group of jobs in a dict format and executes them
        one by one.

        job_dict (dict): a dictionary suitable to be imported from Job.

        """
        start_time = time.time()
        job = Job.import_from_dict_with_type(job_dict)

        if self.work_lock.acquire(False):

            try:
                logger.info("Starting job.",
                            extra={"operation": job.info})

                job.shard = self.shard

                task_type = get_task_type(job.task_type,
                                          job.task_type_parameters)
                task_type.execute_job(job, self.file_cacher)

                logger.info("Finished job.",
                            extra={"operation": job.info})

                return job.export_to_dict()

            except:
                err_msg = "Worker failed."
                logger.error(err_msg, exc_info=True)
                raise JobException(err_msg)

            finally:
                self._finalize(start_time)
                self.work_lock.release()

        else:
            err_msg = "Request received, but declined because of acquired " \
                "lock (Worker is busy executing another job, this should " \
                "not happen: check if there are more than one ES running, " \
                "or for bugs in ES."
            logger.warning(err_msg)
            self._finalize(start_time)
            raise JobException(err_msg)

    def _finalize(self, start_time):
        end_time = time.time()
        busy_time = end_time - start_time
        free_time = 0.0
        if self._last_end_time is not None:
            free_time = start_time - self._last_end_time
        self._last_end_time = end_time
        self._total_busy_time += busy_time
        self._total_free_time += free_time
        ratio = self._total_busy_time * 100.0 / \
            (self._total_busy_time + self._total_free_time)
        avg_free_time = 0.0
        if self._number_execution > 0:
            avg_free_time = self._total_free_time / self._number_execution
        avg_busy_time = 0.0
        if self._number_execution > 0:
            avg_busy_time = self._total_busy_time / self._number_execution
        self._number_execution += 1
        logger.info("Executed in %.3lf after free for %.3lf; "
                    "busyness is %.1lf%%; avg free time is %.3lf "
                    "avg busy time is %.3lf ",
                    busy_time, free_time, ratio, avg_free_time, avg_busy_time)
