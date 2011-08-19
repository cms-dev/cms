#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2011 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2011 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2011 Matteo Boscariol <boscarim@hotmail.com>
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
import sys
import traceback

from cms.async import ServiceCoord
from cms.async.AsyncLibrary import logger, async_lock, Service, \
     rpc_method, rpc_threaded
from cms.service.TaskType import get_task_type_class
from cms.db.SQLAlchemyAll import Session, Submission, SessionGen
from cms.service import JobException

class Worker(Service):

    def __init__(self, shard):
        logger.initialize(ServiceCoord("Worker", shard))
        logger.debug("Worker.__init__")
        Service.__init__(self, shard)
        self.work_lock = threading.Lock()
        self.session = None

    def get_submission_data(self, submission_id):
        submission = Submission.get_from_id(submission_id, self.session)
        if submission is None:
            err_msg = "Couldn't find submission %d in the database" % (submission_id)
            logger.critical(msg_err)
            raise JobException(msg_err)

        task_type = get_task_type_class(submission, self.session, self)
        if task_type is None:
            err_msg = "Task type `%s' not known for submission %d" \
                % (self.submission.task.task_type, submission_id)
            logger.critical(err_msg)
            raise JobException(msg_err)

        return (submission, task_type)

    # FIXME - There is far too common code among compile() and
    # evaluate() that should be deduplicated

    @rpc_method
    @rpc_threaded
    def compile(self, submission_id):
        if self.work_lock.acquire(False):

            try:
                logger.operation = "compiling submission %s" % (submission_id)
                with async_lock:
                    logger.info("Request received")

                with SessionGen(commit=False) as self.session:

                    # Retrieve submission and task_type
                    (submission, task_type) = self.get_submission_data(submission_id)

                    # Do the actual work
                    try:
                        success = task_type.compile()
                    except Exception as e:
                        err_msg = "Compilation failed with not caught exception `%s' and traceback `%s'" % (repr(e), traceback.format_exc())
                        with async_lock:
                            logger.error(err_msg)
                        raise JobException(err_msg)

                    self.session.commit()
                    with async_lock:
                        logger.info("Request finished")
                    return success
            except Exception as e:
                err_msg = "Worker failed to compilation with exception `%s' and traceback `%s'" % (repr(e), traceback.format_exc())
                with async_lock:
                    logger.error(err_msg)
                raise JobException(err_msg)

            finally:
                self.session = None
                logger.operation = ""
                self.work_lock.release()

        else:
            with async_lock:
                logger.info("Request to compile submission %d received, but declined because of acquired lock" % (submission_id))
            return False

    @rpc_method
    @rpc_threaded
    def evaluate(self, submission_id):
        if self.work_lock.acquire(False):

            try:
                with async_lock:
                    logger.operation = "evaluating submission %s" % (submission_id)
                    logger.info("Request received")

                with SessionGen(commit=False) as self.session:

                    # Retrieve submission and task_type
                    (submission, task_type) = self.get_submission_data(submission_id)

                    # Do the actual work
                    try:
                        success = self.task_type.execute()
                    except Exception as e:
                        err_msg = "Evaluation failed with not caught exception `%s'" % (repr(e))
                        with async_lock:
                            logger.error(err_msg)
                        raise JobException(err_msg)

                    session.commit()
                    with async_lock:
                        logger.info("Request finished")
                    return success

            finally:
                self.session = None
                with async_lock:
                    logger.operation = ""
                self.work_lock.release()

        else:
            with async_lock:
                logger.info("Request to evaluate submission %d received, but declined because of acquired lock" % (submission_id))
            return False


    @rpc_method
    def shut_down(self, reason):
        #logger.operation = ""
        #logger.info("Shutting down the worker because of reason `%s'" % reason)
        raise NotImplementedError, "Worker.shut_down not implemented yet"


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print sys.argv[0], "shard"
    else:
        Worker(shard=int(sys.argv[1])).run()
