#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2014 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""This file defines classes to handle asynchronous RPC communication
using gevent and JSON encoding.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import errno
import functools
import logging
import os
import pwd
import signal
import socket
import _socket
import time

import gevent
import gevent.socket
import gevent.event
from gevent.server import StreamServer
from gevent.backdoor import BackdoorServer

from cms import ConfigError, config, mkdir, ServiceCoord, Address, \
    get_service_address
from cms.log import root_logger, shell_handler, ServiceFilter, \
    CustomFormatter, LogServiceHandler, FileHandler
from cmscommon.datetime import monotonic_time

from .rpc import rpc_method, RemoteServiceServer, RemoteServiceClient, \
    FakeRemoteServiceClient


logger = logging.getLogger(__name__)


def repeater(func, period):
    """Repeatedly call the given function.

    Continuosly calls the given function, over and over. For a call to
    be issued the previous one needs to have returned, and at least the
    given number of seconds needs to have passed. Raised exceptions are
    caught, logged and then suppressed.

    func (function): the function to call.
    period (float): the desired interval between successive calls.

    """
    while True:
        call = monotonic_time()

        try:
            func()
        except Exception:
            logger.error("Unexpected error.", exc_info=True)

        gevent.sleep(max(call + period - monotonic_time(), 0))


class Service(object):

    def __init__(self, shard=0):
        signal.signal(signal.SIGINT, lambda unused_x, unused_y: self.exit())

        self.name = self.__class__.__name__
        self.shard = shard
        self._my_coord = ServiceCoord(self.name, self.shard)

        # Dictionaries of (to be) connected RemoteServiceClients.
        self.remote_services = {}

        self.initialize_logging()

        # We setup the listening address for services which want to
        # connect with us.
        try:
            address = get_service_address(self._my_coord)
        except KeyError:
            raise ConfigError("Unable to find address for service %r. "
                              "Is it specified in core_services in cms.conf?" %
                              (self._my_coord,))

        self.rpc_server = StreamServer(address, self._connection_handler)
        self.backdoor = None

    def initialize_logging(self):
        """Set up additional logging handlers.

        What we do, in detail, is to add a logger to file (whose
        filename depends on the coords) and a remote logger to a
        LogService. We also attach the service coords to all log
        messages.

        """
        filter_ = ServiceFilter(self.name, self.shard)

        # Update shell handler to attach service coords.
        shell_handler.addFilter(filter_)

        # Determine location of log file, and make directories.
        log_dir = os.path.join(config.log_dir,
                               "%s-%d" % (self.name, self.shard))
        mkdir(config.log_dir)
        mkdir(log_dir)
        log_filename = "%d.log" % int(time.time())

        # Install a file handler.
        file_handler = FileHandler(os.path.join(log_dir, log_filename),
                                   mode='w', encoding='utf-8')
        if config.file_log_debug:
            file_log_level = logging.DEBUG
        else:
            file_log_level = logging.INFO
        file_handler.setLevel(file_log_level)
        file_handler.setFormatter(CustomFormatter(False))
        file_handler.addFilter(filter_)
        root_logger.addHandler(file_handler)

        # Provide a symlink to the latest log file.
        try:
            os.remove(os.path.join(log_dir, "last.log"))
        except OSError:
            pass
        os.symlink(log_filename, os.path.join(log_dir, "last.log"))

        # Setup a remote LogService handler (except when we already are
        # LogService, to avoid circular logging).
        if self.name != "LogService":
            log_service = self.connect_to(ServiceCoord("LogService", 0))
            remote_handler = LogServiceHandler(log_service)
            remote_handler.setLevel(logging.INFO)
            remote_handler.addFilter(filter_)
            root_logger.addHandler(remote_handler)

    def _connection_handler(self, sock, address):
        """Receive and act upon an incoming connection.

        A new RemoteServiceServer is spawned to take care of the new
        connection.

        """
        try:
            ipaddr, port = address
            ipaddr = gevent.socket.gethostbyname(ipaddr)
            address = Address(ipaddr, port)
        except socket.error:
            logger.warning("Unexpected error.", exc_info=True)
            return
        remote_service = RemoteServiceServer(self, address)
        remote_service.handle(sock)

    def connect_to(self, coord, on_connect=None, on_disconnect=None,
                   must_be_present=True):
        """Return a proxy to a remote service.

        Obtain a communication channel to the remote service at the
        given coord (reusing an existing one, if possible), attach the
        on_connect and on_disconnect handlers and return it.

        coord (ServiceCoord): the coord of the service to connect to.
        on_connect (function|None): to be called when the service
            connects.
        on_disconnect (function|None): to be called when it
            disconnects.
        must_be_present (bool): if True, the coord must be present in
            the configuration; otherwise, it can be missing and in
            that case the return value is a fake client (that is, a
            client that never connects and ignores all calls).

        return (RemoteServiceClient): a proxy to that service.

        """
        if coord not in self.remote_services:
            try:
                service = RemoteServiceClient(coord, auto_retry=0.5)
            except KeyError:
                # The coordinates are invalid: raise a ConfigError if
                # the service was needed, or return a dummy client if
                # the service was optional.
                if must_be_present:
                    raise ConfigError("Missing address and port for %s "
                                      "in cms.conf." % (coord, ))
                else:
                    service = FakeRemoteServiceClient(coord, None)
            service.connect()
            self.remote_services[coord] = service
        else:
            service = self.remote_services[coord]

        if on_connect is not None:
            service.add_on_connect_handler(on_connect)

        if on_disconnect is not None:
            service.add_on_disconnect_handler(on_disconnect)

        return service

    def add_timeout(self, func, plus, seconds, immediately=False):
        """Register a function to be called repeatedly.

        func (function): the function to call.
        plus (object): additional data to pass to the function.
        seconds (float): the minimum interval between successive calls
            (may be larger if a call doesn't return on time).
        immediately (bool): whether to call right off or wait also
            before the first call.

        """
        if plus is None:
            plus = {}
        func = functools.partial(func, **plus)
        if immediately:
            gevent.spawn(repeater, func, seconds)
        else:
            gevent.spawn_later(seconds, repeater, func, seconds)

    def exit(self):
        """Terminate the service at the next step.

        """
        logger.warning("%r received request to shut down.", self._my_coord)
        self.rpc_server.stop()

    def get_backdoor_path(self):
        """Return the path for a UNIX domain socket to use as backdoor.

        """
        return os.path.join(config.run_dir, "%s_%d" % (self.name, self.shard))

    @rpc_method
    def start_backdoor(self, backlog=50):
        """Start a backdoor server on a local UNIX domain socket.

        """
        backdoor_path = self.get_backdoor_path()
        try:
            os.remove(backdoor_path)
        except OSError as error:
            if error.errno != errno.ENOENT:
                raise
        else:
            logger.warning("A backdoor socket has been found and deleted.")
        mkdir(os.path.dirname(backdoor_path))
        backdoor_sock = _socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        backdoor_sock.setblocking(0)
        backdoor_sock.bind(backdoor_path)
        user = pwd.getpwnam("cmsuser")
        # We would like to also set the user to "cmsuser" but only root
        # can do that. Therefore we limit ourselves to the group.
        os.chown(backdoor_path, os.getuid(), user.pw_gid)
        os.chmod(backdoor_path, 0o770)
        backdoor_sock.listen(backlog)
        self.backdoor = BackdoorServer(backdoor_sock, locals={'service': self})
        self.backdoor.start()

    @rpc_method
    def stop_backdoor(self):
        """Stop a backdoor server started by start_backdoor.

        """
        if self.backdoor is not None:
            self.backdoor.stop()
        backdoor_path = self.get_backdoor_path()
        try:
            os.remove(backdoor_path)
        except OSError as error:
            if error.errno != errno.ENOENT:
                raise

    def run(self):
        """Starts the main loop of the service.

        return (bool): True if successful.

        """
        try:
            self.rpc_server.start()

        # This must come before socket.error, because socket.gaierror
        # extends socket.error
        except socket.gaierror:
            logger.critical("Service %s could not listen on "
                            "specified address, because it cannot "
                            "be resolved.", self.name)
            return False

        except socket.error as error:
            if error.errno == errno.EADDRINUSE:
                logger.critical("Listening port %s for service %s is "
                                "already in use, quitting.",
                                self.rpc_server.address.port, self.name)
                return False
            elif error.errno == errno.EADDRNOTAVAIL:
                logger.critical("Service %s could not listen on "
                                "specified address, because it is not "
                                "available.", self.name)
                return False
            else:
                raise

        if config.backdoor:
            self.start_backdoor()

        logger.info("%s %d up and running!", *self._my_coord)

        # This call will block until self.rpc_server.stop() is called.
        self.rpc_server.serve_forever()

        logger.info("%s %d is shutting down", *self._my_coord)

        if config.backdoor:
            self.stop_backdoor()

        self._disconnect_all()
        return True

    def _disconnect_all(self):
        """Disconnect all remote services.

        """
        for service in self.remote_services.itervalues():
            if service.connected:
                service.disconnect()

    @rpc_method
    def echo(self, string):
        """Simple RPC method.

        string (string): the string to be echoed.
        return (string): string, again.

        """
        return string

    @rpc_method
    def quit(self, reason=""):
        """Shut down the service

        reason (string): why, oh why, you want me down?

        """
        logger.info("Trying to exit as asked by another service (%s).", reason)
        self.exit()
