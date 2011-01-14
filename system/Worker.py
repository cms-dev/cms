#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright (C) 2010 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright (C) 2010 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright (C) 2010 Matteo Boscariol <boscarim@hotmail.com>
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

class JobException(Exception):
    def __init__(self, msg = ""):
        self.msg = msg
    def __str__(self):
        return repr(self.msg)

class Job(threading.Thread):
    def __init__(self, submission_id):
        threading.Thread.__init__(self)
        print "Initializing Job", submission_id
        self.es = xmlrpclib.ServerProxy("http://%s:%d" % Configuration.evaluation_server)
        self.submission_id = submission_id

        self.submission = CouchObject.from_couch(submission_id)
        if self.submission == None:
            Utils.log("Couldn't find submission %s con CouchDB" % (submission_id), Utils.Logger.SEVERITY_IMPORTANT)
            raise Exception

        self.task_type = TaskType.get_task_type_class(self.submission)
        if self.task_type == None:
            Utils.log("Task type `%s' not known for submission %s" % (self.submission.task.task_type, submission_id), Utils.Logger.SEVERITY_IMPORTANT)
            raise Exception

class CompileJob(Job):
    def __init__(self, submission_id):
        Job.__init__(self, submission_id)

    def run(self):
        try:
            success = self.task_type.compile()
        except JobException:
            success = False
        try:
            self.es.compilation_finished(success, self.submission_id)
            if success:
                Utils.log("Reported successful operation")
            else:
                Utils.log("Reported failed operation")
        except IOError:
            Utils.log("Could not report finished operation, dropping it")

class EvaluateJob(Job):
    def __init__(self, submission_id):
        Job.__init__(self, submission_id)

    def run(self):
        success = self.task_type.execute()
        try:
            self.es.evaluation_finished(success, self.submission_id)
            if success:
                Utils.log("Reported successful operation")
            else:
                Utils.log("Reported failed operation")
        except IOError:
            Utils.log("Could not report finished operation, dropping it")
 
class Worker(RPCServer):
    def __init__(self, listen_address, listen_port):
        RPCServer.__init__(self, "Worker", listen_address, listen_port,
                           [self.compile,
                            self.evaluate])

    def compile(self, submission_id):
        Utils.set_operation("compiling submission %s" % (submission_id))
        Utils.log("Request received")
        j = CompileJob(submission_id)
        j.start()
        return True

    def evaluate(self, submission_id):
        Utils.set_operation("evaluating submission %s" % (submission_id))
        Utils.log("Request received")
        j = EvaluateJob(submission_id)
        j.start()
        return True

if __name__ == "__main__":
    import CouchObject
    import sys
    worker_num = int(sys.argv[1])
    address, port = Configuration.workers[worker_num]
    Utils.set_service("worker %d (%s:%d)" % (worker_num, address, port))
    w = Worker(address, port)
