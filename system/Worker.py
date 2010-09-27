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

import Configuration

from SimpleXMLRPCServer import SimpleXMLRPCServer
import xmlrpclib
import threading
import time

class Job(threading.Thread):
    def __init__(self, submission_id):
        threading.Thread.__init__(self)
        print "Initializing Job", submission_id
        self.es = xmlrpclib.ServerProxy("http://%s:%d" % Configuration.evaluation_server)
        self.submission_id = submission_id
        self.submission = CouchObject.from_couch(submission_id)

class CompileJob(Job):
    def __init__(self, submission_id):
        Job.__init__(self, submission_id)

    def run(self):
        time.sleep(3)
        self.submission.compilation_result = "OK, gcc is proud of you"
        self.submission.to_couch()
        self.es.compilation_finished(True, self.submission_id)

class EvaluateJob(Job):
    def __init__(self, submission_id):
        Job.__init__(self, submission_id)

    def run(self):
        time.sleep(3)
        self.submission.evaluation_status = "Wonderful, you're a tough coder! :-)"
        self.submission.to_couch()
        self.es.evaluation_finished(True, self.submission_id)

class Worker:
    def __init__(self, listen_address, listen_port):
        # Create server
        server = SimpleXMLRPCServer((listen_address, listen_port))
        server.register_introspection_functions()

        server.register_function(self.compile)
        server.register_function(self.evaluate)

        # Run the server's main loop
        server.serve_forever()

    def compile(self, submission_id):
        j = CompileJob(submission_id)
        j.start()
        return True

    def evaluate(self, submission_id):
        j = EvaluateJob(submission_id)
        j.start()
        return True

if __name__ == "__main__":
    import CouchObject
    import sys
    address, port = Configuration.workers[int(sys.argv[1])]
    w = Worker(address, port)

