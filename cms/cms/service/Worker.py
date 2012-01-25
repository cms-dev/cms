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

from cms import default_argument_parser
from cms.async import ServiceCoord
from cms.async.AsyncLibrary import async_lock, Service, \
     rpc_method, rpc_threaded
from cms.db.SQLAlchemyAll import Submission, SessionGen, Contest
from cms.grading import JobException
from cms.grading.TaskType import TaskTypes
from cms.service.FileStorage import FileCacher
from cms.service.LogService import logger


class Worker(Service):
    """This service implement the possibility to compile and evaluate
    submissions in a sandbox. The instructions to follow for the
    operations are in the TaskType classes, while the sandbox is in
    the Sandbox module.

    """

    def __init__(self, shard):
        logger.initialize(ServiceCoord("Worker", shard))
        Service.__init__(self, shard, custom_logger=logger)
        self.FC = FileCacher(self)

        self.work_lock = threading.Lock()
        self.session = None

    def get_submission_data(self, submission_id):
        submission = Submission.get_from_id(submission_id, self.session)
        if submission is None:
            err_msg = "Couldn't find submission %s " \
                      "in the database" % submission_id
            logger.critical(err_msg)
            raise JobException(err_msg)

        try:
            task_type = TaskTypes.get_task_type(submission, self.FC)
        except KeyError:
            err_msg = "Task type `%s' not known for submission %s" \
                % (submission.task.task_type, submission_id)
            logger.critical(err_msg)
            raise JobException(err_msg)

        return (submission, task_type)

    # FIXME - There is far too common code among compile() and
    # evaluate() that should be deduplicated

    @rpc_method
    @rpc_threaded
    def compile(self, submission_id):
        """RPC to ask the worker to compile the submission.

        submission_id (int): the id of the submission to compile.

        """
        return self.action(submission_id, "compilation")

    @rpc_method
    @rpc_threaded
    def evaluate(self, submission_id):
        """RPC to ask the worker to evaluate the submission.

        submission_id (int): the id of the submission to evaluate.

        """
        return self.action(submission_id, "evaluation")

    # FIXME - rpc_threaded is disable because it makes the call fail:
    # we should investigate on this
    @rpc_method
    #@rpc_threaded
    def precache_files(self, contest_id):
        """RPC to ask the worker to precache of files in the contest.

        contest_id (int): the id of the contest

        """
        # TODO - Check for lock
        logger.info("Precaching files for contest %d" % contest_id)
        with SessionGen(commit=False) as session:
            contest = Contest.get_from_id(contest_id, session)
            for digest in contest.enumerate_files():
                self.FC.get_file(digest)
        logger.info("Precaching finished")

    def action(self, submission_id, job_type):
        """The actual work - that can be compilation or evaluation
        (the code is pretty much the same, the differencies are in
        what we ask TaskType to do).

        submission_id (string): the submission to which act on.
        job_type (string): "compilation" or "evaluation".

        """
        if self.work_lock.acquire(False):

            try:
                logger.operation = "%s of submission %s" % (job_type,
                                                            submission_id)
                with async_lock:
                    logger.info("Request received: %s of submission %s." %
                                (job_type, submission_id))

                with SessionGen(commit=False) as self.session:

                    # Retrieve submission and task_type
                    submission, task_type = \
                        self.get_submission_data(submission_id)

                    # Store in the task type the shard number
                    task_type.worker_shard = self.shard

                    # Do the actual work
                    success = False
                    task_type_action = task_type.evaluate
                    if job_type == "compilation":
                        task_type_action = task_type.compile

                    try:
                        success = task_type_action()
                    except Exception as error:
                        err_msg = "%s failed with not caught " \
                            "exception `%r' and traceback `%s'" % \
                            (job_type, error, traceback.format_exc())
                        with async_lock:
                            logger.error(err_msg)
                        raise JobException(err_msg)

                    if success:
                        self.session.commit()

                    with async_lock:
                        logger.info("Request finished")
                    return success
            except Exception as error:
                err_msg = "Worker failed the %s with exception " \
                    "`%r' and traceback `%s'" % \
                    (job_type, error, traceback.format_exc())
                with async_lock:
                    logger.error(err_msg)
                raise JobException(err_msg)

            finally:
                self.session = None
                logger.operation = ""
                self.work_lock.release()

        else:
            with async_lock:
                logger.info("Request of %s of submission %s received, "
                            "but declined because of acquired lock" %
                            (job_type, submission_id))
            return False


def main():
    """Parse arguments and launch service.

    """
    default_argument_parser("Safe command executer for CMS.", Worker).run()


if __name__ == "__main__":
    main()
