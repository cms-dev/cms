#!/usr/bin/python
# -*- coding: utf-8 -*-

from SimpleXMLRPCServer import SimpleXMLRPCServer
import Contest
import CouchObject
import Configuration
import threading
import heapq
import time
import xmlrpclib
from Utils import log

class JobQueue:
    def __init__(self):
        self.semaphore = threading.BoundedSemaphore()
        self.queue = []

    def lock(self):
        self.semaphore.acquire()

    def unlock(self):
        self.semaphore.release()

    def push(self, job, priority, timestamp = None):
        if timestamp == None:
            try:
                timestamp = job[1].timestamp
            except:
                timestamp = time.time()
        heapq.heappush(self.queue, (priority, timestamp, job))

    def pop(self):
        return heapq.heappop(self.queue)[2]

    def search(self, job):
        for i in self.queue:
            if queue[i][2] == job:
                return i
        raise LookupError("Job not present in queue")

    def delete(self, pos):
        self.queue[pos] = self.queue[-1]
        self.queue = self.queue[:-1]
        heapq.heapify(self.queue)

    def length(self):
        return len(self.queue)

    def empty(self):
        return self.length() == 0

    def poll_queue(self, sleep_time = 2):
        while True:
            self.lock()
            wait = False
            try:
                job = self.pop()
            except IndexError:
                wait = True
            self.unlock()
            if wait:
                time.sleep(sleep_time)
            else:
                return job

class WorkerPool:
    def __init__(self, worker_num):
        self.workers = [None] * worker_num

    def acquire_worker(self, job):
        try:
            worker = self.find_worker(None)
            self.workers[worker] = job
            return worker
        except LookupError:
            raise LookupError("No available workers")

    def release_worker(self, n):
        if self.workers[n] == None:
            raise ValueError("Worker was inactive")
        self.workers[n] = None

    def find_worker(self, job):
        for worker, workerJob in enumerate(self.workers):
            if workerJob == job:
                return worker
        raise LookupError("No such job")

    def poll_worker(self, job, sleep_time = 2):
        while True:
            try:
                worker = self.acquire_worker(job)
                return worker
            except LookupError:
                time.sleep(sleep_time)

class JobDispatcher(threading.Thread):
    def __init__(self, queue, workers):
        threading.Thread.__init__(self)
        self.queue = queue
        self.workers = workers

    def run(self):
        while True:
            job = self.queue.poll_queue()
            action = job[0]
            if action == EvaluationServer.JOB_TYPE_BOMB:
                log("KABOOM!! (but I should wait for all the workers to finish their jobs)")
                return
            else:
                submission = job[1]
                worker = self.workers.poll_worker(job)

                log("Asking worker %d (%s:%d) to %s submission %s" %
                    (worker,
                     Configuration.workers[worker][0],
                     Configuration.workers[worker][1],
                     action,
                     submission.couch_id))
                p = xmlrpclib.ServerProxy("http://%s:%d" %
                                          Configuration.workers[worker])
                if action == EvaluationServer.JOB_TYPE_COMPILATION:
                    p.compile(submission.couch_id)
                elif action == EvaluationServer.JOB_TYPE_EVALUATION:
                    p.evaluate(submission.couch_id)

class EvaluationServer:
    JOB_PRIORITY_HIGH, JOB_PRIORITY_MEDIUM, JOB_PRIORITY_LOW, JOB_PRIORITY_EXTRA_LOW = range(4)
    JOB_TYPE_COMPILATION, JOB_TYPE_EVALUATION, JOB_TYPE_BOMB = ["compile", "evaluate", "bomb"]

    def __init__(self, contest, listen_address = None, listen_port = None):
        if listen_address == None:
            listen_address = Configuration.evaluation_server[0]
        if listen_port == None:
            listen_port = Configuration.evaluation_server[1]

        server = SimpleXMLRPCServer((listen_address, listen_port))
        server.register_introspection_functions()

        self.queue = JobQueue()
        self.workers = WorkerPool(len(Configuration.workers))
        self.jd = JobDispatcher(self.queue, self.workers)

        self.contest = contest
        for sub in self.contest.submissions:
            sub.invalid()
            self.add_job(sub.couch_id)

        server.register_function(self.add_job)
        server.register_function(self.compilation_finished)
        server.register_function(self.evaluation_finished)
        server.register_function(self.self_destruct)

        self.jd.start()
        server.serve_forever()

    def add_job(self, submission_id):
        log("Queueing compilation for submission %s" % (submission_id))
        submission = CouchObject.from_couch(submission_id)
        self.queue.lock()
        self.queue.push((EvaluationServer.JOB_TYPE_COMPILATION, submission),
                        EvaluationServer.JOB_PRIORITY_HIGH)
        self.queue.unlock()
        return True

    def action_finished(self, job):
        worker = self.workers.find_worker(job)
        self.workers.release_worker(worker)
        log("Worker %d (%s:%d) finished to %s submission %s" %
            (worker,
             Configuration.workers[worker][0],
             Configuration.workers[worker][1],
             job[0],
             job[1].couch_id))

    def compilation_finished(self, success, submission_id):
        submission = CouchObject.from_couch(submission_id)
        self.action_finished((EvaluationServer.JOB_TYPE_COMPILATION, submission))
        if success:
            log("Compilation succeeded for submission %s" % (submission_id))
            log("Queueing evaluation for submission %s" % (submission_id))
            self.queue.lock()
            self.queue.push((EvaluationServer.JOB_TYPE_EVALUATION, submission),
                            EvaluationServer.JOB_PRIORITY_LOW)
            self.queue.unlock()
        else:
            self.add_job(submission_id)
            log("Compilation failed for submission %s" % (submission_id))
        return True

    def evaluation_finished(self, success, submission_id):
        submission = CouchObject.from_couch(submission_id)
        self.action_finished((EvaluationServer.JOB_TYPE_EVALUATION, submission))
        if success:
            log("Evaluation succeeded for submission %s" % (submission_id))
        else:
            self.queue.lock()
            self.queue.push((EvaluationServer.JOB_TYPE_EVALUATION, submission),
                            EvaluationServer.JOB_PRIORITY_LOW)
            self.queue.unlock()
            log("Evaluation failed for submission %s" % (submission_id))
        return True

    def self_destruct(self):
        self.queue.lock()
        self.queue.push((EvaluationServer.JOB_TYPE_BOMB, None),
                        EvaluationServer.JOB_PRIORITY_EXTRA_LOW)
        self.queue.unlock()
        return True

if __name__ == "__main__":
    import Worker
    import Contest
    import Submission
    import sys

    es_address, es_port = Configuration.evaluation_server
    if sys.argv[1] == "run":
#        c = Contest.sample_contest()
#        s = Submission.sample_submission()
#        print "Submission ID:", s.couch_id
#        c.submissions.append(s)
#        c.to_couch()
#        print "Contest ID:", c.couch_id
        c = CouchObject.from_couch('2bbb185b8b92bcfe51adf41c0ec89b3b')

        e = EvaluationServer(c, es_address, es_port)

    elif sys.argv[1] == "destroy":
        es = xmlrpclib.ServerProxy("http://localhost:%d" % es_port)
        es.self_destruct()

    else:
        s = CouchObject.from_couch('3bba67b41846e836d9c91f82c0ac4dd5')
        es = xmlrpclib.ServerProxy("http://localhost:%d" % es_port)
        es.add_job(s.couch_id)
