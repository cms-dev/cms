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

import xmlrpclib
import threading
from RPCServer import RPCServer

import Configuration
import Utils
import TaskType
import CouchObject

class JobException(Exception):
    def __init__(self, msg = ""):
        self.msg = msg
    def __str__(self):
        return repr(self.msg)

class Job(threading.Thread):
    def __init__(self, submission_id, worker):
        threading.Thread.__init__(self)
        print "Initializing Job", submission_id
        self.es = xmlrpclib.ServerProxy("http://%s:%d" % Configuration.evaluation_server)
        self.submission_id = submission_id
        self.worker = worker

        self.submission = CouchObject.from_couch(submission_id)
        if self.submission == None:
            Utils.log("Couldn't find submission %s con CouchDB" % (submission_id), Utils.Logger.SEVERITY_IMPORTANT)
            raise Exception

        self.task_type = TaskType.get_task_type_class(self.submission)
        if self.task_type == None:
            Utils.log("Task type `%s' not known for submission %s" % (self.submission.task.task_type, submission_id), Utils.Logger.SEVERITY_IMPORTANT)
            raise Exception

class CompileJob(Job):
    def __init__(self, submission_id, worker):
        Job.__init__(self, submission_id, worker)

    def run(self):
        try:
            success = self.task_type.compile()
        except:
            success = False
        try:
            self.es.compilation_finished(success, self.submission_id)
            if success:
                Utils.log("Reported successful operation")
            else:
                Utils.log("Reported failed operation")
        except IOError:
            Utils.log("Could not report finished operation, dropping it")
        finally:
            self.worker.working_thread = None

class EvaluateJob(Job):
    def __init__(self, submission_id, worker):
        Job.__init__(self, submission_id, worker)

    def run(self):
        try:
            success = self.task_type.execute()
        except:
            success = False
        try:
            self.es.evaluation_finished(success, self.submission_id)
            if success:
                Utils.log("Reported successful operation")
            else:
                Utils.log("Reported failed operation")
        except IOError:
            Utils.log("Could not report finished operation, dropping it")
        finally:
            self.worker.working_thread = None
 
class Worker(RPCServer):
    def __init__(self, listen_address, listen_port):
        RPCServer.__init__(self, "Worker", listen_address, listen_port,
                           [self.compile,
                            self.evaluate])
        self.working_thread = None

    def compile(self, submission_id):
        Utils.set_operation("compiling submission %s" % (submission_id))
        Utils.log("Request received")
        j = CompileJob(submission_id, self)
        self.working_thread = j
        j.start()
        return True

    def evaluate(self, submission_id):
        Utils.set_operation("evaluating submission %s" % (submission_id))
        Utils.log("Request received")
        j = EvaluateJob(submission_id, self)
        self.working_thread = j
        j.start()
        return True

if __name__ == "__main__":
    import sys
    try:
        worker_num = int(sys.argv[1])
        address, port = Configuration.workers[worker_num]
        Utils.set_service("worker %d (%s:%d)" % (worker_num, address, port))
    except ValueError:
        address, port = sys.argv[1:3]
        port = int(port)
        Utils.set_service("worker (%s:%d)" % (address, port))
    w = Worker(address, port)
