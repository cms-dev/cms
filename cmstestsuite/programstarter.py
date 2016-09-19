#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2012 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2013-2016 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2013-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Luca Versari <veluca93@gmail.com>
# Copyright © 2014 William Di Luigi <williamdiluigi@gmail.com>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import atexit
import errno
import io
import json
import logging
import os
import signal
import socket
import subprocess
import threading
import time
from urlparse import urlsplit

from cmstestsuite import CONFIG, FrameworkException, get_cms_config


logger = logging.getLogger(__name__)


# Maximum number of attempts to check if a service becomes healthy.
_MAX_ATTEMPTS = 20


class RemoteService(object):
    """Class which implements the RPC protocol used by CMS.

    This is deliberately a re-implementation in order to catch or
    trigger bugs in the CMS services.

    """
    def __init__(self, service_name, shard):
        address, port = get_cms_config()["core_services"][service_name][shard]

        self.service_name = service_name
        self.shard = shard
        self.address = address
        self.port = port

    def call(self, function_name, data):
        """Perform a synchronous RPC call."""
        s = json.dumps({
            "__id": "foo",
            "__method": function_name,
            "__data": data,
        })
        msg = s + "\r\n"

        # Send message.
        sock = socket.socket()
        sock.connect((self.address, self.port))
        sock.send(msg)

        # Wait for response.
        s = ''
        while len(s) < 2 or s[-2:] != "\r\n":
            s += sock.recv(1)
        s = s[:-2]
        sock.close()

        # Decode reply.
        reply = json.loads(s)

        return reply


class Program(object):
    """An instance of a program, which might be running or not."""

    _COVERAGE_CMDLINE = \
        ["python", "-m", "coverage", "run", "-p", "--source=cms"]

    def __init__(self, service_name, shard=0, contest=None):
        self.service_name = service_name
        self.shard = shard
        self.contest = contest
        self.instance = None
        self.healthy = False

    def start(self):
        """Start a CMS service."""
        logger.info("Starting %s.", self.service_name)
        executable = os.path.join(
            ".", "scripts", "cms%s" % (self.service_name))
        if CONFIG["TEST_DIR"] is None:
            executable = "cms%s" % self.service_name

        args = [executable]
        if self.shard is not None:
            args.append("%s" % self.shard)
        if self.contest is not None:
            args += ["-c", "%s" % self.contest]

        self.instance = self._spawn(args)
        t = threading.Thread(target=self._check_with_backoff)
        t.daemon = True
        t.start()

    @property
    def running(self):
        """Return whether the program is live."""
        self._check()
        return self.healthy

    def stop(self):
        """Quit gracefully. Or not: if the quit RPC does not work, kill."""
        if self.service_name != "RankingWebServer":
            # Try to terminate gracefully (RWS does not have a way to do it).
            logger.info("Asking %s/%s to terminate...",
                        self.service_name, self.shard)
            rs = RemoteService(self.service_name, self.shard)
            rs.call("quit", {"reason": "from test harness"})

        # If it didn't understand, use bad manners.
        self._check()
        if self.healthy:
            logger.info("Killing %s/%s.", self.service_name, self.shard)
            os.kill(self.instance.pid, signal.SIGINT)
            self.instance.wait()

    def _check_with_backoff(self):
        """Check and wait that the service is healthy."""
        self.healthy = False
        attempts = 0
        while attempts < _MAX_ATTEMPTS:
            attempts += 1
            self._check()
            if not self.healthy:
                time.sleep(0.2 * (1.2 ** attempts))
            else:
                return

        # Service did not start.
        raise FrameworkException("Failed to bring up service %s/%s" %
                                 (self.service_name, self.shard))

    def _check(self):
        """Check that the program is healthy and set the healthy bit.

        raise (FrameworkException): when the state is weird, critical.

        """
        try:
            if self.service_name == "RankingWebServer":
                self._check_ranking_web_server()
            else:
                self._check_service()
        except socket.error as error:
            self.healthy = False
            if error.errno != errno.ECONNREFUSED:
                raise FrameworkException("Weird connection state.")
        else:
            self.healthy = True

    def _check_service(self):
        """Health checker for services and servers."""
        rs = RemoteService(self.service_name, self.shard)
        reply = rs.call("echo", {"string": "hello"})
        if reply["__data"] != "hello":
            raise FrameworkException("Strange response from service.")

        # In case it is a server, we also check HTTP is serving.
        if self.service_name == "AdminWebServer":
            port = get_cms_config()["admin_listen_port"]
        elif self.service_name == "ContestWebServer":
            port = get_cms_config()["contest_listen_port"][self.shard]
        else:
            return

        sock = socket.socket()
        sock.connect(("127.0.0.1", port))
        sock.close()

    def _check_ranking_web_server(self):
        """Health checker for RWS."""
        url = urlsplit(get_cms_config()["rankings"][0])
        sock = socket.socket()
        sock.connect((url.hostname, url.port))
        sock.close()

    @staticmethod
    def _spawn(cmdline):
        """Execute a python application."""

        def kill(job):
            try:
                job.kill()
            except OSError:
                pass

        if CONFIG["VERBOSITY"] >= 1:
            logger.info("$" + " ".join(cmdline))

        if CONFIG["TEST_DIR"] is not None and CONFIG.get("COVERAGE"):
            cmdline = Program._COVERAGE_CMDLINE + cmdline

        if CONFIG["VERBOSITY"] >= 3:
            stdout = None
            stderr = None
        else:
            stdout = io.open(os.devnull, "wb")
            stderr = stdout
        job = subprocess.Popen(cmdline, stdout=stdout, stderr=stderr)
        atexit.register(lambda: kill(job))
        return job


class ProgramStarter(object):
    """Utility to keep track of all programs started."""

    def __init__(self):
        # Map of arguments to Program instances.
        self._programs = {}

        # Map Program: check_function
        self._check_to_perform = {}

    def start(self, service_name, shard=0, contest=None):
        """Start a CMS service."""
        p = Program(service_name, shard, contest)
        p.start()
        self._programs[(service_name, shard, contest)] = p

    def count_unhealthy(self):
        return len([p for p in self._programs.itervalues() if not p.healthy])

    def wait(self):
        attempts = 0
        while attempts <= _MAX_ATTEMPTS:
            attempts += 1
            unhealthy = self.count_unhealthy()
            if unhealthy == 0:
                logger.info("All healthy! Continuing.")
                return
            logger.info("Still %s unhealthy.", unhealthy)
            time.sleep(0.2 * (1.2 ** attempts))
        raise FrameworkException(
            "Failed to bring up services: %s" %
            ", ".join("%s/%s" % (p.service_name, p.shard)
                      for p in self._programs.itervalues() if not p.healthy))

    def restart(self, service_name, shard=0, contest=None):
        p = self._programs[(service_name, shard, contest)]
        p.stop()
        p.start()

    def stop(self, service_name, shard=0, contest=None):
        p = self._programs[(service_name, shard, contest)]
        p.stop()
        del self._programs[(service_name, shard, contest)]

    def stop_all(self):
        for p in self._programs.itervalues():
            p.stop()
