#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2013 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

import gevent.coros

from cms.io import Service, rpc_method
from cms.db import SessionGen, Contest
from cms.db.filecacher import FileCacher
from cms.grading import JobException
from cms.grading.tasktypes import get_task_type
from cms.grading.Job import JobGroup


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
        self._ignore_job = False

    @rpc_method
    def ignore_job(self):
        """RPC that inform the worker that its result for the current
        action will be discarded. The worker will try to return as
        soon as possible even if this means that the result are
        inconsistent.

        """
        # We remember to quit as soon as possible.
        logger.info("Trying to interrupt job as requested.")
        self._ignore_job = True

    @rpc_method
    def precache_files(self, contest_id):
        """RPC to ask the worker to precache of files in the contest.

        contest_id (int): the id of the contest

        """
        # Lock is not needed if the admins correctly placed cache and
        # temp directories in the same filesystem. This is what
        # usually happens since they are children of the same,
        # cms-created, directory.
        logger.info("Precaching files for contest %d." % contest_id)
        with SessionGen() as session:
            contest = Contest.get_from_id(contest_id, session)
            for digest in contest.enumerate_files(skip_submissions=True,
                                                  skip_user_tests=True):
                self.file_cacher.load(digest)
        logger.info("Precaching finished.")

    @rpc_method
    def execute_job_group(self, job_group_dict):
        """Receive a group of jobs in a dict format and executes them
        one by one.

        job_group_dict (dict): a dictionary suitable to be imported
            from JobGroup.

        """
        job_group = JobGroup.import_from_dict(job_group_dict)

        if self.work_lock.acquire(False):

            try:
                self._ignore_job = False

                for k, job in job_group.jobs.iteritems():
                    logger.info("Starting job.",
                                extra={"operation": job.info})

                    job.shard = self.shard

                    # FIXME This is actually kind of a workaround...
                    # The only TaskType that needs it is OutputOnly.
                    job._key = k

                    # FIXME We're creating a new TaskType for each Job
                    # even if, at the moment, a JobGroup always uses
                    # the same TaskType and the same parameters. Yet,
                    # this could change in the future, so the best
                    # solution is to keep a cache of TaskTypes objects
                    # (like ScoringService does with ScoreTypes, except
                    # that we cannot index by Dataset ID here...).
                    task_type = get_task_type(job.task_type,
                                              job.task_type_parameters)
                    task_type.execute_job(job, self.file_cacher)

                    logger.info("Finished job.",
                                extra={"operation": job.info})

                    if not job.success or self._ignore_job:
                        job_group.success = False
                        break
                else:
                    job_group.success = True

                return job_group.export_to_dict()

            except:
                err_msg = "Worker failed."
                logger.error(err_msg, exc_info=True)
                raise JobException(err_msg)

            finally:
                self.work_lock.release()

        else:
            err_msg = "Request received, but declined because of acquired " \
                "lock (Worker is busy executing another job group, this " \
                "should not happen: check if there are more than one ES " \
                "running, or for bugs in ES."
            logger.warning(err_msg)
            raise JobException(err_msg)
