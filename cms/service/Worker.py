#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
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

import threading
import traceback

from cms import default_argument_parser, logger
from cms.async import ServiceCoord
from cms.async.AsyncLibrary import Service, rpc_method, rpc_threaded
from cms.db.FileCacher import FileCacher
from cms.db.SQLAlchemyAll import SessionGen, Contest
from cms.grading import JobException
from cms.grading.tasktypes import get_task_type
from cms.grading.Job import Job


class Worker(Service):
    """This service implement the possibility to compile and evaluate
    submissions in a sandbox. The instructions to follow for the
    operations are in the TaskType classes, while the sandbox is in
    the Sandbox module.

    """

    JOB_TYPE_COMPILATION = "compile"
    JOB_TYPE_EVALUATION = "evaluate"

    def __init__(self, shard):
        logger.initialize(ServiceCoord("Worker", shard))
        Service.__init__(self, shard, custom_logger=logger)
        self.file_cacher = FileCacher(self)

        self.task_type = None
        self.work_lock = threading.Lock()
        self.session = None

    @rpc_method
    def ignore_job(self):
        """RPC that inform the worker that its result for the current
        action will be discarded. The worker will try to return as
        soon as possible even if this means that the result are
        inconsistent.

        """
        # We inform the task_type to quit as soon as possible.
        logger.info("Trying to interrupt job as requested.")
        try:
            self.task_type.ignore_job = True
        except AttributeError:
            pass  # Job concluded right under our nose, that's ok too.

    # FIXME - rpc_threaded is disable because it makes the call fail:
    # we should investigate on this
    @rpc_method
    @rpc_threaded
    def precache_files(self, contest_id):
        """RPC to ask the worker to precache of files in the contest.

        contest_id (int): the id of the contest

        """
        # Lock is not needed if the admins correctly placed cache and
        # temp directories in the same filesystem. This is what
        # usually happens since they are children of the same,
        # cms-created, directory.
        logger.info("Precaching files for contest %d." % contest_id)
        with SessionGen(commit=False) as session:
            contest = Contest.get_from_id(contest_id, session)
            for digest in contest.enumerate_files(skip_submissions=True):
                self.file_cacher.get_file(digest)
        logger.info("Precaching finished.")

    @rpc_method
    @rpc_threaded
    def execute_job(self, job_dict):
        job = Job.import_from_dict_with_type(job_dict)

        if self.work_lock.acquire(False):

            try:
                logger.operation = "job '%s'" % (job.info)
                logger.info("Request received")
                job.shard = self.shard

                self.task_type = get_task_type(job, self.file_cacher)
                self.task_type.execute_job()
                logger.info("Request finished.")

                return job.export_to_dict()

            except:
                err_msg = "Worker failed on operation `%s'" % logger.operation
                logger.error("%s\n%s" % (err_msg, traceback.format_exc()))
                raise JobException(err_msg)

            finally:
                self.task_type = None
                self.session = None
                logger.operation = ""
                self.work_lock.release()

        else:
            err_msg = "Request '%s' received, " \
                "but declined because of acquired lock" % \
                (job.info)
            logger.warning(err_msg)
            raise JobException(err_msg)


def main():
    """Parse arguments and launch service.

    """
    default_argument_parser("Safe command executer for CMS.", Worker).run()


if __name__ == "__main__":
    main()
