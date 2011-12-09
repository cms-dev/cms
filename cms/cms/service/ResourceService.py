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

"""Service to be run once for each machine the system is running on,
that saves the resources usage in that machine. We require psutil >=
0.2.

"""

import time

import psutil

from cms.async.AsyncLibrary import Service, rpc_method, logger
from cms.async import ServiceCoord, Config


class ResourceService(Service):
    """This service looks at the resources usage (CPU, load, memory,
    network) every seconds, stores it locally, and offer (new) data
    upon request.

    """

    def __init__(self, shard):
        logger.initialize(ServiceCoord("ResourceService", shard))
        logger.debug("ResourceService.__init__")
        Service.__init__(self, shard)

        # _local_store is a dictionary indexed by time in int(epoch)
        self._local_store = []
        # Floating point epoch using for precise measurement of percents
        self._last_saved_time = time.time()
        # Starting point for cpu times
        self._prev_cpu_times = psutil.get_system_cpu_times()
        # Sorted list of ServiceCoord running in the same machine
        self._local_services = self._find_local_services()
        self._procs = dict((service, None)
            for service in self._local_services)
        self._services_prev_cpu_times = dict((service, (0.0, 0.0))
            for service in self._local_services)
        self._store_resources(store=False)

        self.add_timeout(self._store_resources, None, 5)

    def _find_local_services(self):
        """Returns the services that are running on the same machine
        as us.

        returns (list): a list of ServiceCoord elements, sorted by
                        name and shard

        """
        logger.debug("ResourceService._find_local_services")
        services = Config.core_services
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
        cmdline = Config.process_cmdline[:]
        l = len(cmdline)
        for i in range(l):
            cmdline[i] = cmdline[i].replace("%s", service.name)
            cmdline[i] = cmdline[i].replace("%d", str(service.shard))
        for proc in psutil.get_process_list():
            try:
                if proc.cmdline[:l] == cmdline:
                    self._services_prev_cpu_times[service] = \
                        proc.get_cpu_times()
                    return proc
            except psutil.error.NoSuchProcess:
                continue
        return None

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
        cpu_times = psutil.get_system_cpu_times()
        data["cpu"] = dict((x, int(round((cpu_times[x] -
                                          self._prev_cpu_times[x])
                                   / delta * 100.0)))
                            for x in cpu_times)
        data["cpu"]["num_cpu"] = psutil.NUM_CPUS
        self._prev_cpu_times = cpu_times

        # Memory
        ram_cached = psutil.cached_phymem()
        ram_buffers = psutil.phymem_buffers()
        data["memory"] = {
            "ram_total": psutil.TOTAL_PHYMEM / 1048576.0,
            "ram_available": psutil.avail_phymem() / 1048576.0,
            "ram_cached": ram_cached / 1048576.0,
            "ram_buffers": ram_buffers / 1048576.0,
            "ram_used": (psutil.used_phymem() - ram_cached - ram_buffers)
                              / 1048576.0,
            "swap_total": psutil.total_virtmem() / 1048576.0,
            "swap_available": psutil.avail_virtmem() / 1048576.0,
            "swap_used": psutil.used_virtmem() / 1048576.0,
            }

        data["services"] = {}
        # Details of our services
        for service in self._local_services:
            d = {}
            proc = self._procs[service]
            # If we don't have a previously found process for the
            # service, we find it
            if proc is None:
                proc = self._find_proc(service)
            # If we still do not find it, there is no process
            if proc is None:
                data["services"][str(service)] = {"running": False}
                continue
            # We have a process, but maybe it has been shut down
            try:
                proc.getcwd()
            except psutil.error.NoSuchProcess:
                # If so, let us find the new one
                proc = self._find_proc(service)
                # If there is no new one, continue
                if proc is None:
                    data["services"][str(service)] = {"running": False}
                    continue

            try:
                d["running"] = True
                d["since"] = self._last_saved_time - \
                                         proc.create_time
                d["resident"], d["virtual"] = \
                    (x / 1048576  for x in proc.get_memory_info())
                cpu_times = proc.get_cpu_times()
                d["user"] = int(round((cpu_times[0] -
                    self._services_prev_cpu_times[service][0])
                    / delta * 100))
                d["sys"] = int(round((cpu_times[1] -
                    self._services_prev_cpu_times[service][1])
                    / delta * 100))
                self._services_prev_cpu_times[service] = cpu_times
                try:
                    d["threads"] = proc.get_num_threads()
                except AttributeError:
                    d["threads"] = 0 # 0 = Not implemented

                self._procs[service] = proc
            except psutil.error.NoSuchProcess:
                d = {"running": False}
            data["services"][str(service)] = d

        if store:
            self._local_store.append((now, data))

        return True

    def _locate(self, time, start=0, end=None):
        """Perform a binary search to find the index of the first
        element >= time.

        time (int): the time to search
        returns (int): the index of the first element >= time

        """
        logger.debug("ResourceService._locate")
        if end is None:
            end = len(self._local_store) - 1
        if self._local_store[start][0] >= time:
            return start
        elif self._local_store[end][0] < time:
            return None
        elif end == start + 1:
            return end
        mid = (start + end) / 2
        if self._local_store[mid][0] >= time:
            return self._locate(time, start, mid)
        else:
            return self._locate(time, mid, end)

    @rpc_method
    def get_resources(self, last_time=0):
        """Returns the resurce usage information from last_time to
        now.

        last_time (int): timestamp of the last time the caller called
                         this method.

        """
        logger.debug("ResourceService._get_resources")
        index = self._locate(last_time + 1)
        return self._local_store[index:]


def main():
    import sys
    if len(sys.argv) != 2:
        print sys.argv[0], "shard"
    else:
        ResourceService(int(sys.argv[1])).run()


if __name__ == "__main__":
    main()
