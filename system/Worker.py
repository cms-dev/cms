#!/usr/bin/python
# -*- coding: utf-8 -*-

import Configuration

from SimpleXMLRPCServer import SimpleXMLRPCServer
import xmlrpclib
import threading

class Job(threading.Thread):
    def __init__(self, contest, submission_id, port):
        self.contest = contest
        self.submission_id = submission_id
        self.submission = CouchObject.from_couch(submission_id)
        self.worker = xmlrpclib.ServerProxy("http://localhost:%d" % port)

class CompileJob(Job):
    def __init__(self, **kwargs):
        Job.__init__(self, **kwargs)

    def run(self):
        sleep(3)
        self.worker.compile_end(self.submission_id)

class EvaluateJob(threading.Thread):
    def __init__(self, **kwargs):
        Job.__init__(self, **kwargs)

    def run(self):
        sleep(3)
        self.worker.evaluate_end(self.submission_id)

class Worker:
    def __init__(self, contest, listen_address, listen_port):
        self.contest = contest
        self.es = xmlrpclib.ServerProxy("http://%s:%d" % Configuration.evaluation_server)

        # Create server
        self.port = listen_port
        server = SimpleXMLRPCServer((listen_address, listen_port))
        server.register_introspection_functions()

        server.register_function(self.compile)
        server.register_function(self.evaluate)
        server.register_function(self.compile_end)
        server.register_function(self.evaluate_end)

        # Run the server's main loop
        server.serve_forever()

    def compile(self, submission_id):
        j = CompileJob(self.contest, submission_id, self.port)
        j.start()
        return True

    def compile_end(self, submission_id):
        self.es.compilation_finished(True, submission_id)
        pass

    def evaluate(self, submission_id):
        j = EvaluateJob(self.contest, submission_id, self.port)
        j.start()
        return True

    def evaluate_end(self, submission_id):
        pass


if __name__ == "__main__":
    import Contest
    import Submission
    c = Contest.sample_contest()
    s = Submission.sample_submission()
    c.submissions.append(s)
    port = 8000
    w = Worker(c, "", port)

