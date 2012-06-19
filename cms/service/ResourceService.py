#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
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
that saves the resources usage in that machine. We require psutil >=
0.2.0.

"""

import os
import time
import subprocess
import argparse
import bisect

import psutil

from cms import config, logger, find_local_addresses
from cms.async import ServiceCoord, get_shard_from_addresses
from cms.async.AsyncLibrary import Service, rpc_method, RemoteService
from cms.db import ask_for_contest


# We need to use one set of methods for versions < 0.3.0, and another
# for versions >= 0.3.0. See
# http://code.google.com/p/psutil/wiki/Documentation#Memory .
psutil_version = tuple(int(x) for x in psutil.__version__.split("."))
assert psutil_version >= (0, 2, 0), \
       "Please install python-psutil >= 0.2.0."

B_TO_MB = 1024.0 * 1024.0


class ResourceService(Service):
    """This service looks at the resources usage (CPU, load, memory,
    network) every seconds, stores it locally, and offer (new) data
    upon request.

    """

    def __init__(self, shard, contest_id=None):
        """If contest_id is not None, we assume the user wants the
        autorestart feature.

        """
        logger.initialize(ServiceCoord("ResourceService", shard))
        Service.__init__(self, shard, custom_logger=logger)

        self.contest_id = contest_id

        # _local_store is a dictionary indexed by time in int(epoch)
        self._local_store = []
        # Floating point epoch using for precise measurement of percents
        self._last_saved_time = time.time()
        # Starting point for cpu times
        self._prev_cpu_times = self._get_cpu_times()
        # Sorted list of ServiceCoord running in the same machine
        self._local_services = self._find_local_services()
        # Dict service with bool to mark if we will restart them.
        self._will_restart = dict((service,
                                   None if self.contest_id is None else True)
                                  for service in self._local_services)
        # Found process associate to the ServiceCoord.
        self._procs = dict((service, None)
            for service in self._local_services)
        # Previous cpu time for each service.
        self._services_prev_cpu_times = dict((service, (0.0, 0.0))
            for service in self._local_services)
        # Start finding processes and their cputimes.
        self._store_resources(store=False)

        self.add_timeout(self._store_resources, None, 5)
        if self.contest_id is not None:
            self._launched_processes = set([])
            self.add_timeout(self._restart_services, None, 5,
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
        for service in self._local_services:
            # We let the user start logservice and resourceservice.
            if service.name == "LogService" or \
                   service.name == "ResourceService":
                continue

            # If the user specified not to restart some service, we
            # ignore it.
            if not self._will_restart[service]:
                continue

            running = True
            proc = self._procs[service]
            # If we don't have a previously found process for the
            # service, we find it
            if proc is None:
                proc = self._find_proc(service)
            if proc is None:
                running = False
            else:
                self._procs[service] = proc
                # We have a process, but maybe it has been shut down
                if not proc.is_running():
                    # If so, let us find the new one
                    proc = self._find_proc(service)
                    # If there is no new one, continue
                    if proc is None:
                        running = False
                    else:
                        self._procs[service] = proc

            if not running:
                # We give contest_id even if the service doesn't need
                # it, since it causes no trouble.
                logger.info("Restarting (%s, %s)..." % (service.name,
                                                        service.shard))
                devnull = os.open(os.devnull, os.O_WRONLY)
                process = subprocess.Popen(["cms%s" % service.name,
                                            str(service.shard),
                                            "-c",
                                            str(self.contest_id)],
                                           stdout=devnull,
                                           stderr=subprocess.STDOUT)
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

    def _find_proc(self, service):
        """Returns the pid of a given service running on this machine.

        service (ServiceCoord): the service we are interested in
        returns (psutil.Process): the process of service, or None if
                                  not found

        """
        logger.debug("ResourceService._find_proc")
        cmdline = config.process_cmdline[:]
        length = len(cmdline)
        for i in range(length):
            cmdline[i] = cmdline[i].replace("%s", service.name)
            cmdline[i] = cmdline[i].replace("%d", str(service.shard))
        for proc in psutil.get_process_list():
            try:
                if proc.cmdline[:length] == cmdline:
                    self._services_prev_cpu_times[service] = \
                        proc.get_cpu_times()
                    return proc
            except psutil.error.NoSuchProcess:
                continue
        return None

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

        # CPU
        cpu_times = self._get_cpu_times()
        data["cpu"] = dict((x, int(round((cpu_times[x] -
                                          self._prev_cpu_times[x])
                                   / delta * 100.0)))
                            for x in cpu_times)
        data["cpu"]["num_cpu"] = psutil.NUM_CPUS
        self._prev_cpu_times = cpu_times

        # Memory. We differentiate from old and deprecated (< 0.3.0)
        # methods to the new ones. Remove the differentiation when we
        # drop the support for Ubuntu 11.10 (which ships 0.2.1).
        ram_cached = psutil.cached_phymem()
        ram_buffers = psutil.phymem_buffers()
        if psutil_version < (0, 3, 0):
            data["memory"] = {
                "ram_total": psutil.TOTAL_PHYMEM / B_TO_MB,
                "ram_available": psutil.avail_phymem() / B_TO_MB,
                "ram_cached": ram_cached / B_TO_MB,
                "ram_buffers": ram_buffers / B_TO_MB,
                "ram_used": (psutil.used_phymem() - ram_cached - ram_buffers)
                                  / B_TO_MB,
                "swap_total": psutil.total_virtmem() / B_TO_MB,
                "swap_available": psutil.avail_virtmem() / B_TO_MB,
                "swap_used": psutil.used_virtmem() / B_TO_MB,
                }
        else:
            phymem = psutil.phymem_usage()
            virtmem = psutil.virtmem_usage()
            data["memory"] = {
                "ram_total": phymem.total / B_TO_MB,
                "ram_available": phymem.free / B_TO_MB,
                "ram_cached": ram_cached / B_TO_MB,
                "ram_buffers": ram_buffers / B_TO_MB,
                "ram_used": (phymem.used - ram_cached - ram_buffers) / B_TO_MB,
                "swap_total": virtmem.total / B_TO_MB,
                "swap_available": virtmem.free / B_TO_MB,
                "swap_used": virtmem.used / B_TO_MB,
                }

        data["services"] = {}
        # Details of our services
        for service in self._local_services:
            dic = {"autorestart": self._will_restart[service],
                   "running": True}
            proc = self._procs[service]
            # If we don't have a previously found process for the
            # service, we find it
            if proc is None:
                proc = self._find_proc(service)
            # If we still do not find it, there is no process
            if proc is None:
                dic["running"] = False
            # We have a process, but maybe it has been shut down
            elif not proc.is_running():
                # If so, let us find the new one
                proc = self._find_proc(service)
                # If there is no new one, continue
                if proc is None:
                    dic["running"] = False
            # If the process is not running, we have nothing to do.
            if not dic["running"]:
                data["services"][str(service)] = dic
                continue

            try:
                dic["since"] = self._last_saved_time - proc.create_time
                dic["resident"], dic["virtual"] = \
                    (x / 1048576  for x in proc.get_memory_info())
                cpu_times = proc.get_cpu_times()
                dic["user"] = int(
                    round((cpu_times[0] -
                           self._services_prev_cpu_times[service][0])
                          / delta * 100))
                dic["sys"] = int(
                    round((cpu_times[1] -
                           self._services_prev_cpu_times[service][1])
                          / delta * 100))
                self._services_prev_cpu_times[service] = cpu_times
                try:
                    dic["threads"] = proc.get_num_threads()
                except AttributeError:
                    dic["threads"] = 0  # 0 = Not implemented

                self._procs[service] = proc
            except psutil.error.NoSuchProcess:
                # Shut down while we operated?
                dic = {"autorestart": self._will_restart[service],
                       "running": False}
            data["services"][str(service)] = dic

        if store:
            if len(self._local_store) >= 5000:  # almost 7 hours
                self._local_store = self._local_store[1:]
            self._local_store.append((now, data))

        return True

    @rpc_method
    def get_resources(self, last_time=0):
        """Returns the resurce usage information from last_time to
        now.

        last_time (int): timestamp of the last time the caller called
                         this method.

        """
        logger.debug("ResourceService._get_resources")
        index = bisect.bisect_right(self._local_store, (last_time, 0))
        return self._local_store[index:]

    @rpc_method
    def kill_service(self, service):
        """Restart the service. Note that after calling successfully
        this method, get_resource could still report the service
        running untile we call _store_resources again.

        service (string): format: name,shard.

        """
        logger.info("Killing %s as asked." % service)
        try:
            idx = service.rindex(",")
        except ValueError:
            logger.error("Unable to decode service string.")
        name = service[:idx]
        try:
            shard = int(service[idx + 1:])
        except ValueError:
            logger.error("Unable to decode service shard.")

        remote_service = RemoteService(self, ServiceCoord(name, shard))
        remote_service.quit(reason="Asked by ResourceService")

    @rpc_method
    def toggle_autorestart(self, service):
        """If the service is scheduled for autorestart, disable it,
        otherwise enable it.

        service (string): format: name,shard.

        return (bool/None): current status of will_restart.

        """
        # If the contest_id is not set, we cannot autorestart.
        if self.contest_id is None:
            return None

        # Decode name,shard
        try:
            idx = service.rindex(",")
        except ValueError:
            logger.error("Unable to decode service string.")
        name = service[:idx]
        try:
            shard = int(service[idx + 1:])
        except ValueError:
            logger.error("Unable to decode service shard.")
        service = ServiceCoord(name, shard)

        self._will_restart[service] = not self._will_restart[service]
        logger.info("Will restart %s,%s is now %s." %
                    (service.name, service.shard, self._will_restart[service]))

        return self._will_restart[service]


def main():
    """Parses arguments and launch service.

    """
    parser = argparse.ArgumentParser(
        description="Resource monitor and service starter for CMS.")
    parser.add_argument("-a", "--autorestart", metavar="CONTEST_ID",
                        help="restart automatically services on its machine",
                        nargs="?", type=int, const=-1)
    parser.add_argument("shard", type=int, nargs="?", default=-1)
    args = parser.parse_args()

    # If the shard is -1 (i.e., unspecified) we find it basing on the
    # local IP addresses
    if args.shard == -1:
        addrs = find_local_addresses()
        args.shard = get_shard_from_addresses("ResourceService", addrs)

    if args.autorestart is not None:
        if args.autorestart == -1:
            ResourceService(args.shard,
                            contest_id=ask_for_contest()).run()
        else:
            ResourceService(args.shard, contest_id=args.autorestart).run()
    else:
        ResourceService(args.shard).run()


if __name__ == "__main__":
    main()
