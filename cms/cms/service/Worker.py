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

import TaskType
import Submission

shutting_down = False


class JobException(Exception):
    def __init__(self, msg = ""):
        self.msg = msg
    def __str__(self):
        return repr(self.msg)


class Job(threading.Thread):
    def __init__(self, submission_id, worker):
        threading.Thread.__init__(self)
        logger.info("Initializing Job %s" % submission_id)
        self.es = xmlrpclib.ServerProxy("http://%s:%d"
                                        % Configuration.evaluation_server)
        self.submission_id = submission_id
        self.worker = worker

        self.submission = CouchObject.from_couch(submission_id)
        if self.submission == None:
            logger.error("Couldn't find submission %s con CouchDB"
                         % submission_id)
            raise Exception

        self.task_type = TaskType.get_task_type_class(self.submission)
        if self.task_type == None:
            logger.error("Task type `%s' not known for submission %s"
                         % (self.submission.task.task_type, submission_id))
            raise Exception


class CompileJob(Job):
    def __init__(self, submission_id, worker):
        Job.__init__(self, submission_id, worker)

    def run(self):
        try:
            success = self.task_type.compile()
        except Exception as e:
            logger.critical("Compilation failed with not caught exception `%s'"
                            % repr(e))
            success = False
        try:
            self.es.compilation_finished(success, self.submission_id)
            if success:
                logger.info("Reported successful operation")
            else:
                logger.info("Reported failed operation")
        except IOError:
            logger.info("Could not report finished operation, dropping it")
        finally:
            self.worker.working_thread = None


class EvaluateJob(Job):
    def __init__(self, submission_id, worker):
        Job.__init__(self, submission_id, worker)

    def run(self):
        try:
            success = self.task_type.execute()
        except Exception as e:
            logger.critical("Evaluation failed with not caught exception `%s'"
                            % repr(e))
            success = False
        try:
            self.es.evaluation_finished(success, self.submission_id)
            if success:
                logger.info("Reported successful operation")
            else:
                logger.info("Reported failed operation")
        except IOError:
            logger.info("Could not report finished operation, dropping it")
        finally:
            self.worker.working_thread = None


class Worker(Service):
    def __init__(self, shard):
        logger.initialize(ServiceCoord("Worker", shard))
        logger.debug("Worker.__init__")
        Service.__init__(self, shard)

    @rpc_method
    def compile(self, submission_id):
        logger.set_operation("compiling submission %s" % submission_id)
        logger.info("Request received")
        j = CompileJob(submission_id, self)
        self.working_thread = j
        j.start()
        return True

    @rpc_method
    def evaluate(self, submission_id):
        logger.set_operation("evaluating submission %s" % submission_id)
        logger.info("Request received")
        j = EvaluateJob(submission_id, self)
        self.working_thread = j
        j.start()
        return True

    @rpc_method
    def shut_down(self, reason):
        global shutting_down
        logger.unset_operation()
        logger.info("Shutting down the worker because of reason `%s'" % reason)
        shutting_down = True
        return True


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print sys.argv[0], "shard"
    else:
        Worker(shard=int(sys.argv[1])).run()
