#!/usr/bin/python
# -*- encoding: utf-8 -*-

from SimpleXMLRPCServer import SimpleXMLRPCServer
import Contest
import CouchObject
import Configuration
import threading
import heapq
import time
import xmlrpclib

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
                raise KeyError("The job is not a submission, you have to specify a timestamp")
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

class WorkerPool:
    def __init__(self, worker_num):
        self.workers = [True] * worker_num

    def acquire_worker():
        for i in self.workers:
            if self.workers:
                self.workers[i] = False
                return i
        raise LookupError("No available workers")

    def release_worker(n):
        if self.workers[n]:
            raise ValueError("Worker was inactive")
        self.workers[n] = True

class JobDispatcher(threading.Thread):
    def __init__(self, queue, workers):
        self.queue = queue
        self.workers = workers

    def run(self):
        while True:
            # Wait a few seconds if the queue is empty
            while True:
                self.queue.lock()
                wait = False
                try:
                    job = self.queue.pop()
                except IndexError:
                    wait = True
                self.queue.unlock()
                if wait:
                    time.sleep(2)
                else:
                    break

            action = job[0]
            if action == "bomb":
                return
            else:
                submission = job[1]

                # Wait a few seconds if there are no worker available
                while True:
                    try:
                        worker = self.workers.acquire_worker()
                        break
                    except LookupError:
                        time.sleep(2)

                p = xmlrpclib.ServerProxy("http://%s:%d" % Configuration.workers[worker])
                if action == "compile":
                    p.compile(submission.couch_id)
                elif action == "execute":
                    p.execute(submission.couch_id)

class EvaluationServer:
    def __init__(self, contest, listen_address = None, listen_port = None):
        self.contest = contest        
        if listen_address == None:
            listen_address = Configuration.evaluation_server[0]
        if listen_port == None:
            listen_port = Configuration.evaluation_server[1]

        # Create server
        server = SimpleXMLRPCServer((listen_address, listen_port))
        server.register_introspection_functions()

        self.queue = JobQueue()
        self.workers = WorkerPool(len(Configuration.workers))
        self.jd = JobDispatcher(queue, workers)
        jd.start()

        server.register_function(self.compilation_finished)
        server.register_function(self.execution_finished)

        # Run forever the server's main loop
        server.serve_forever()

    def compilation_finished(self):
        pass

    def execution_finished(self):
        pass
