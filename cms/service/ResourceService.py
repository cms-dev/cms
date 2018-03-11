#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013-2017 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""Service to be run once for each machine the system is running on,
that saves the resources usage in that machine.

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa
from six import iteritems

from collections import defaultdict, deque
import logging
import os
import re
import time

import psutil

from gevent import subprocess
try:
    from subprocess import DEVNULL  # py3k
except ImportError:
    DEVNULL = os.open(os.devnull, os.O_WRONLY)

from cms import config, get_safe_shard, ServiceCoord
from cms.io import Service, rpc_method


logger = logging.getLogger(__name__)


B_TO_MB = 1000 * 1000

MAX_RESOURCE_SECONDS = 11 * 60  # MAX time window for remote resource query

PSUTIL_PROC_ATTRS = \
    ["cmdline", "cpu_times", "create_time", "memory_info", "num_threads"]


class ProcessMatcher(object):
    def __init__(self):
        # Running processes, lazily loaded.
        self._procs = None

    def find(self, service, cpu_times=None):
        """Returns the pid of a given service running on this machine.

        service (ServiceCoord): the service we are interested in.
        cpu_times ({ServiceCoord: object}|None): if not None, a dict to update
            with the cputimes of the found process, if found.

        return (psutil.Process|None): the process of service, or None
             if not found

        """
        logger.debug("ProcessMatcher.find %s", service)
        if self._procs is None:
            self._procs = ProcessMatcher._get_interesting_running_processes()
        shards = self._procs.get(service.name, {})
        for shard, proc in iteritems(shards):
            if get_safe_shard(service.name, shard) == service.shard:
                logger.debug("Found %s", service)
                if cpu_times is not None:
                    cpu_times[service] = proc.cpu_times()
                return proc
        return None

    @staticmethod
    def _get_all_processes():
        """Wrapper of psutil for testing.

        return (([string], psutil.Process)): generator for tuples
            (full command line, process).

        """
        for proc in psutil.process_iter():
            try:
                yield proc.cmdline(), proc
            except psutil.NoSuchProcess:
                continue

    @staticmethod
    def _get_interesting_running_processes():
        """Return the processes that might be CMS services

        return ({string: {int|None: psutil.Process}): maps service
            names to a map from shards to the corresponding process.

        """
        logger.debug("_get_interesting_running_processes")
        ret = defaultdict(dict)
        for cmdline, proc in ProcessMatcher._get_all_processes():
            data = ProcessMatcher._is_interesting_command_line(cmdline)
            if data is not None:
                service, shard = data
                ret[service][shard] = proc
        return ret

    @staticmethod
    def _is_interesting_command_line(cmdline):
        """Returns if cmdline can be the command line of a service.

        cmdline ([string]): a command line.

        return ((string, int|None)|None): if cmdline is not a CMS
            service, None; otherwise, a tuple whose first element is
            the service name, and the second is the shard number, or
            None if the default was used.

        """
        if not cmdline:
            return None

        start_index = 0
        if os.path.basename(cmdline[0]) == "env":
            start_index = 1

        if len(cmdline) - start_index < 2:
            return None

        cl_interpreter = cmdline[start_index]
        if "python" not in cl_interpreter:
            return None

        cl_service = re.search(r"\bcms([a-zA-Z]+)$", cmdline[start_index + 1])
        if not cl_service:
            return None
        cl_service = cl_service.groups()[0]

        # We assume that apart from the shard, all other
        # options are in the form "-<something> <something>".
        shard = None
        for i in range(start_index + 2, len(cmdline), 2):
            if cmdline[i].isdigit():
                shard = int(cmdline[i])
                break
        return (cl_service, shard)


class ResourceService(Service):
    """This service looks at the resources usage (CPU, load, memory,
    network) every seconds, stores it locally, and offer (new) data
    upon request.

    """
    def __init__(self, shard, contest_id=None, autorestart=False):
        """If contest_id is not None, we assume the user wants the
        autorestart feature.

        """
        Service.__init__(self, shard)

        self.contest_id = contest_id
        self.autorestart = autorestart or (contest_id is not None)

        # _local_store is a dictionary indexed by time in int(epoch)
        self._local_store = deque()
        # Floating point epoch using for precise measurement of percents
        self._last_saved_time = time.time()
        # Starting point for cpu times
        self._prev_cpu_times = self._get_cpu_times()
        # Sorted list of ServiceCoord running in the same machine
        self._local_services = self._find_local_services()
        if "ProxyService" in (s.name for s in self._local_services) and \
                self.contest_id is None:
            logger.warning("Will not run ProxyService "
                           "since it requires a contest id.")
        # Dict service with bool to mark if we will restart them.
        self._will_restart = dict((service,
                                   None if not self.autorestart else True)
                                  for service in self._local_services)
        # Found process associate to the ServiceCoord.
        self._procs = dict((service, None)
                           for service in self._local_services)
        # Previous cpu time for each service.
        self._services_prev_cpu_times = \
            dict((service, (0.0, 0.0)) for service in self._local_services)
        # Start finding processes and their cputimes.
        self._store_resources(store=False)

        self.add_timeout(self._store_resources, None, 5.0)
        if self.autorestart:
            self._launched_processes = set([])
            self.add_timeout(self._restart_services, None, 5.0,
                             immediately=True)

    def _restart_services(self):
        """Check if the services that are supposed to run on this
        machine are actually running. If not, start them.

        """
        # To avoid zombies, we poll the process we launched. Anyway we
        # use the information from psutil to see if the process we are
        # interested in are alive (since if the user has already
        # launched another instance, we don't want to duplicate
        # services).
        new_launched_processes = set([])
        for process in self._launched_processes:
            if process.poll() is None:
                new_launched_processes.add(process)
        self._launched_processes = new_launched_processes

        # Look for dead processes, and restart them.
        matcher = ProcessMatcher()
        for service in self._local_services:
            # We let the user start logservice and resourceservice.
            if service.name == "LogService" or \
                    service.name == "ResourceService" or \
                    (self.contest_id is None and
                     service.name == "ProxyService"):
                continue

            # If the user specified not to restart some service, we
            # ignore it.
            if not self._will_restart[service]:
                continue

            # If we don't have a previously found process, or the one
            # we have terminated, we find the process.
            proc = self._procs[service]
            if proc is None or not proc.is_running():
                proc = matcher.find(service, self._services_prev_cpu_times)
                self._procs[service] = proc
            # If we still do not find it, there is no process, and we
            # have nothing to do.
            if proc is None or not proc.is_running():
                # We give contest_id even if the service doesn't need
                # it, since it causes no trouble.
                logger.info("Restarting (%s, %s)...",
                            service.name, service.shard)
                command = "cms%s" % service.name
                if not config.installed:
                    command = os.path.join(
                        ".",
                        "scripts",
                        "cms%s" % service.name)
                args = [command, "%d" % service.shard]
                if self.contest_id is not None:
                    args += ["-c", str(self.contest_id)]
                else:
                    args += ["-c", "ALL"]
                process = subprocess.Popen(args,
                                           stdout=DEVNULL,
                                           stderr=subprocess.STDOUT
                                           )
                self._launched_processes.add(process)

        # Run forever.
        return True

    def _find_local_services(self):
        """Returns the services that are running on the same machine
        as us.

        returns (list): a list of ServiceCoord elements, sorted by
                        name and shard

        """
        logger.debug("ResourceService._find_local_services")
        services = config.async.core_services
        local_machine = services[self._my_coord].ip
        local_services = [x
                          for x in services
                          if services[x].ip == local_machine]
        return sorted(local_services)

    @staticmethod
    def _get_cpu_times():
        """Wrapper of psutil.cpu_times to get the format we like.

        return (dict): dictionary of cpu times information.

        """
        cpu_times = psutil.cpu_times()
        return {"user": cpu_times.user,
                "nice": cpu_times.nice,
                "system": cpu_times.system,
                "idle": cpu_times.idle,
                "iowait": cpu_times.iowait,
                "irq": cpu_times.irq,
                "softirq": cpu_times.softirq}

    def _store_resources(self, store=True):
        """Looks at the resources usage and store the data locally.

        store (bool): if False, run the method but do not store the
                      resulting values - useful for initializing the
                      previous values

        """
        logger.debug("ResourceService._store_resources")
        # We use the precise time to compute the delta
        now = time.time()
        delta = now - self._last_saved_time
        self._last_saved_time = now
        now = int(now)

        data = {}

        def percent_from_delta(v):
            return int(round(v / delta * 100))

        # CPU
        cpu_times = self._get_cpu_times()
        data["cpu"] = dict((x, percent_from_delta(cpu_times[x] -
                                                  self._prev_cpu_times[x]))
                           for x in cpu_times)
        data["cpu"]["num_cpu"] = psutil.cpu_count()
        self._prev_cpu_times = cpu_times

        # Memory. The following relations hold (I think... I only
        # verified them experimentally on a swap-less system):
        # * vmem.free == vmem.available - vmem.cached - vmem.buffers
        # * vmem.total == vmem.used + vmem.free
        # That means that cache & buffers are counted both in .used
        # and in .available. We want to partition the memory into
        # types that sum up to vmem.total.
        vmem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        data["memory"] = {
            "ram_total": vmem.total / B_TO_MB,
            "ram_available": vmem.free / B_TO_MB,
            "ram_cached": vmem.cached / B_TO_MB,
            "ram_buffers": vmem.buffers / B_TO_MB,
            "ram_used": (vmem.used - vmem.cached - vmem.buffers) / B_TO_MB,
            "swap_total": swap.total / B_TO_MB,
            "swap_available": swap.free / B_TO_MB,
            "swap_used": swap.used / B_TO_MB,
            }

        data["services"] = {}

        # Details of our services
        matcher = ProcessMatcher()
        for service in self._local_services:
            dic = {"autorestart": self._will_restart[service],
                   "running": True}
            proc = self._procs[service]

            # If we don't have a previously found process, or the one
            # we have terminated, we find the process.
            if proc is None or not proc.is_running():
                proc = matcher.find(service, self._services_prev_cpu_times)
            # If we still do not find it, there is no process, and we
            # have nothing to do.
            if proc is None:
                dic["running"] = False
                data["services"]["%s" % (service,)] = dic
                continue

            try:
                proc_info = proc.as_dict(attrs=PSUTIL_PROC_ATTRS)
                dic["since"] = self._last_saved_time - proc_info["create_time"]
                dic["resident"] = proc_info["memory_info"].rss // B_TO_MB
                dic["virtual"] = proc_info["memory_info"].vms // B_TO_MB
                cpu_times = proc_info["cpu_times"]
                dic["user"] = percent_from_delta(
                    cpu_times[0] - self._services_prev_cpu_times[service][0])
                dic["sys"] = percent_from_delta(
                    cpu_times[1] - self._services_prev_cpu_times[service][1])

                self._services_prev_cpu_times[service] = cpu_times
                try:
                    dic["threads"] = proc_info["num_threads"]
                except AttributeError:
                    dic["threads"] = 0  # 0 = Not implemented

                self._procs[service] = proc
            except psutil.NoSuchProcess:
                # Shut down while we operated?
                dic = {"autorestart": self._will_restart[service],
                       "running": False}
            data["services"]["%s" % (service,)] = dic

        if store:
            while self._local_store \
                    and self._local_store[-1][0] < now - MAX_RESOURCE_SECONDS:
                self._local_store.pop()
            self._local_store.appendleft((now, data))

        return True

    @rpc_method
    def get_resources(self, last_time=0.0):
        """Returns the resurce usage information from last_time to
        now.

        last_time (float): timestamp of the last time the caller
            called this method.

        """
        logger.debug("ResourceService._get_resources")

        last_time = max(last_time, time.time() - MAX_RESOURCE_SECONDS)
        result = list()
        for sample_time, data in self._local_store:
            if sample_time > last_time:
                result.append((sample_time, data))
        result.reverse()
        return result

    @rpc_method
    def kill_service(self, service):
        """Restart the service. Note that after calling successfully
        this method, get_resource could still report the service
        running untile we call _store_resources again.

        service (string): format: name,shard.

        """
        logger.info("Killing %s as asked.", service)
        try:
            idx = service.rindex(",")
        except ValueError:
            logger.error("Unable to decode service string.")
        name = service[:idx]
        try:
            shard = int(service[idx + 1:])
        except ValueError:
            logger.error("Unable to decode service shard.")

        remote_service = self.connect_to(ServiceCoord(name, shard))
        result = remote_service.quit(reason="Asked by ResourceService")
        return result.get()

    @rpc_method
    def toggle_autorestart(self, service):
        """If the service is scheduled for autorestart, disable it,
        otherwise enable it.

        service (string): format: name,shard.

        return (bool/None): current status of will_restart.

        """
        if not self.autorestart:
            return None

        # Decode name,shard
        try:
            idx = service.rindex(",")
        except ValueError:
            logger.error("Unable to decode service string.")
        name = service[:idx]

        # ProxyService requires contest_id
        if self.contest_id is None and name == "ProxyService":
            return None

        try:
            shard = int(service[idx + 1:])
        except ValueError:
            logger.error("Unable to decode service shard.")
        service = ServiceCoord(name, shard)

        self._will_restart[service] = not self._will_restart[service]
        logger.info("Will restart %s,%s is now %s.",
                    service.name, service.shard, self._will_restart[service])

        return self._will_restart[service]
