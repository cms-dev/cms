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
from SimpleXMLRPCServer import SimpleXMLRPCServer

import Configuration
import Utils
import TaskType

class Job(threading.Thread):
    def __init__(self, submission_id):
        threading.Thread.__init__(self)
        print "Initializing Job", submission_id
        self.es = xmlrpclib.ServerProxy("http://%s:%d" % Configuration.evaluation_server)
        self.submission_id = submission_id
        self.submission = CouchObject.from_couch(submission_id)
        self.task_type = TaskType.get_task_type_class(self.submission.task.task_type)

class CompileJob(Job):
    def __init__(self, submission_id):
        Job.__init__(self, submission_id)

    def run(self):
        Utils.log("Compilation of submission %s started" % (self.submission_id))
        success = self.task_type.compile(self.submission)
        if success:
            Utils.log("Compilation of submission %s finished successfully" % (self.submission_id))
        else:
            Utils.log("Compilation of submission %s failed" % (self.submission_id))
        try:
            self.es.compilation_finished(success, self.submission_id)
        except IOError:
            Utils.log("Could not report finished compilation for submission %s, dropping it" % (self.submission_id))

class EvaluateJob(Job):
    def __init__(self, submission_id):
        Job.__init__(self, submission_id)

    def run(self):
        Utils.log("Evaluation of submission %s started" % (self.submission_id))
        success = self.task_type.execute(self.submission)
        if success:
            Utils.log("Evaluation of submission %s finished successfully" % (self.submission_id))
        else:
            Utils.log("Evaluation of submission %s failed" % (self.submission_id))
        try:
            self.es.evaluation_finished(True, self.submission_id)
        except IOError:
            Utils.log("Could not report finished evaluation for submission %s, dropping it" % (self.submission_id))

class Worker:
    def __init__(self, listen_address, listen_port):
        # Create server
        server = SimpleXMLRPCServer((listen_address, listen_port))
        server.register_introspection_functions()

        server.register_function(self.compile)
        server.register_function(self.evaluate)

        Utils.log("Worker started...")

        # Run the server's main loop
        server.serve_forever()

    def compile(self, submission_id):
        Utils.log("Request to compile submission %s received" % (submission_id))
        j = CompileJob(submission_id)
        j.start()
        return True

    def evaluate(self, submission_id):
        Utils.log("Request to evaluate submission %s received" % (submission_id))
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
