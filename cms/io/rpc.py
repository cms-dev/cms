#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2015 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013-2017 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa
from six import iterkeys, itervalues

import functools
import json
import logging
import socket
import traceback
import uuid
from weakref import WeakSet

import gevent
import gevent.lock
import gevent.socket
import gevent.event

from cms import Address, get_service_address


logger = logging.getLogger(__name__)


class RPCError(Exception):
    """Generic error during RPC communication."""
    pass


def rpc_method(func):
    """Decorator for a method that other services are allowed to call.

    Does not do a lot, just defines the right method's attribute.

    func (function): the method to make RPC callable.
    return (function): the decorated method.

    """
    func.rpc_callable = True
    return func


class RemoteServiceBase(object):
    """Base class for both ends of a RPC connection.

    Just provides some basic helpers for I/O. It alternates between two
    states:
    - disconnected (when self.connected is False) means that no socket
      is bound and therefore no I/O can be performed. Attempting to
      read or write will fail. This is the default state.
    - connected (when self.connected is True) means that a socket is
      bound and (presumably) active. I/O can be performed. This state
      can be entered by calling initialize and can be exited by calling
      disconnect. It will also be exited when errors occur.

    When the state changes the on_connect or on_disconnect handlers
    will be fired.

    """
    # Incoming messages larger than 1 MB are dropped to avoid DOS
    # attacks. XXX Check that this size is sensible.
    MAX_MESSAGE_SIZE = 1000 * 1000

    def __init__(self, remote_address):
        """Prepare to handle a connection with the given remote address.

        remote_address (Address): the address of the other end of the
            connection (origin or target, depending on its direction).

        """
        self.remote_address = remote_address
        self.connected = False

        self._on_connect_handlers = list()
        self._on_disconnect_handlers = list()

        self._socket = None
        self._reader = None
        self._writer = None

        self._read_lock = gevent.lock.RLock()
        self._write_lock = gevent.lock.RLock()

    def add_on_connect_handler(self, handler):
        """Register a callback for connection establishment.

        handler (function): a no-args callable that gets notified when
            a new connection has been established.

        """
        self._on_connect_handlers.append(handler)

    def add_on_disconnect_handler(self, handler):
        """Register a callback for connection termination.

        handler (function): a no-args callable that gets notified when
            a connection has been closed.

        """
        self._on_disconnect_handlers.append(handler)

    def _repr_remote(self):
        """Describe the other end of the connection.

        return (unicode): a human-readable sensible identifier for the
            remote address, for use in log messages and exceptions.

        """
        return "%s:%d" % (self.remote_address)

    def initialize(self, sock, plus):
        """Activate the communication on the given socket.

        Put this class in its "connected" state, setting up all needed
        attributes. Call the on_connect callback.

        sock (socket): the socket acting as low-level communication
            channel.
        plus (object): object to pass to the on_connect callbacks.

        """
        if self.connected:
            raise RuntimeError("Already connected.")

        self._socket = sock
        self._reader = self._socket.makefile('rb')
        self._writer = self._socket.makefile('wb')
        self.connected = True

        logger.info("Established connection with %s.", self._repr_remote())

        for handler in self._on_connect_handlers:
            gevent.spawn(handler, plus)

    def finalize(self, reason=""):
        """Deactivate the communication on the current socket.

        Take the class back to the disconnected state and call the
        on_disconnect callback.

        reason (unicode): the human-readable reason for closing the
            connection, to be put in log messages and exceptions.

        """
        if not self.connected:
            return

        self._socket = None
        self._reader = None
        self._writer = None
        self.connected = False

        logger.info("Terminated connection with %s: %s", self._repr_remote(),
                    reason)

        for handler in self._on_disconnect_handlers:
            gevent.spawn(handler)

    def disconnect(self):
        """Gracefully close the connection.

        return (bool): True if the service was connected.

        """
        if not self.connected:
            return False

        try:
            self._socket.shutdown(socket.SHUT_RDWR)
            self._socket.close()
        except socket.error as error:
            logger.warning("Couldn't disconnect from %s: %s.",
                           self._repr_remote(), error)
        finally:
            self.finalize("Disconnection requested.")
        return True

    def _read(self):
        """Receive a message from the socket.

        Read from the socket until a "\\r\\n" is found. That is what we
        consider a "message" in the communication protocol.

        return (bytes): the retrieved message.

        raise (IOError): if reading fails.

        """
        if not self.connected:
            raise IOError("Not connected.")

        try:
            with self._read_lock:
                if not self.connected:
                    raise IOError("Not connected.")
                data = self._reader.readline(self.MAX_MESSAGE_SIZE)
                # If there weren't a "\r\n" between the last message
                # and the EOF we would have a false positive here.
                # Luckily there is one.
                if len(data) > 0 and not data.endswith(b"\r\n"):
                    logger.error(
                        "The client sent a message larger than %d bytes (that "
                        "is MAX_MESSAGE_SIZE). Consider raising that value if "
                        "the message seemed legit.", self.MAX_MESSAGE_SIZE)
                    self.finalize("Client misbehaving.")
                    raise IOError("Message too long.")
        except socket.error as error:
            logger.warning("Failed reading from socket: %s.", error)
            self.finalize("Read failed.")
            raise error

        return data

    def _write(self, data):
        """Send a message to the socket.

        Automatically append "\\r\\n" to make it a correct message.

        data (bytes): the message to transmit.

        raise (IOError): if writing fails.

        """
        if not self.connected:
            raise IOError("Not connected.")

        if len(data + b'\r\n') > self.MAX_MESSAGE_SIZE:
            logger.error(
                "A message wasn't sent to %r because it was larger than %d "
                "bytes (that is MAX_MESSAGE_SIZE). Consider raising that "
                "value if the message seemed legit.", self._repr_remote(),
                self.MAX_MESSAGE_SIZE)
            # No need to call finalize.
            raise IOError("Message too long.")

        try:
            with self._write_lock:
                if not self.connected:
                    raise IOError("Not connected.")
                # Does the same as self._socket.sendall.
                self._writer.write(data + b'\r\n')
                self._writer.flush()
        except socket.error as error:
            self.finalize("Write failed.")
            logger.warning("Failed writing to socket: %s.", error)
            raise error


class RemoteServiceServer(RemoteServiceBase):
    """The server side of a RPC communication.

    Considers all messages coming from the other end as requests for
    RPCs executions. Will perform them and send results as responses.

    After having created an instance and initialized it with a socket
    the reader loop should be started by calling run.

    """
    def __init__(self, local_service, remote_address):
        """Create a responder for the given service.

        local_service (Service): the object whose methods should be
            called via RPC.

        For other arguments see RemoteServiceBase.

        """
        super(RemoteServiceServer, self).__init__(remote_address)
        self.local_service = local_service

        self.pending_incoming_requests_threads = WeakSet()

    def finalize(self, reason=""):
        """See RemoteServiceBase.finalize."""
        super(RemoteServiceServer, self).finalize(reason)

        for thread in self.pending_incoming_requests_threads:
            thread.kill(RPCError(reason), block=False)

        self.pending_incoming_requests_threads.clear()

    def handle(self, socket_):
        self.initialize(socket_, self.remote_address)
        self.run()

    def run(self):
        """Start listening for requests, and go on forever.

        Read messages from the socket and issue greenlets to parse
        them, execute methods and send the response to the client.
        This method won't return as long as there's something to read,
        it's therefore advisable to spawn a greenlet to call it.

        """
        while True:
            try:
                data = self._read()
            except IOError:
                break

            if len(data) == 0:
                self.finalize("Connection closed.")
                break

            gevent.spawn(self.process_data, data)

    def process_data(self, data):
        """Handle the message.

        JSON-decode it and forward it to process_incoming_request
        (unconditionally!).

        data (bytes): the message read from the socket.

        """
        # Decode the incoming data.
        try:
            message = json.loads(data.decode('utf-8'))
        except ValueError:
            logger.warning("Cannot parse incoming message, discarding.")
            return

        self.process_incoming_request(message)

    def process_incoming_request(self, request):
        """Handle the request.

        Parse the request, execute the method it asks for, format the
        result and send the response.

        request (dict): the JSON-decoded request.

        """
        # Validate the request.
        if not {"__id", "__method", "__data"}.issubset(iterkeys(request)):
            logger.warning("Request is missing some fields, ingoring.")
            return

        # Determine the ID.
        id_ = request["__id"]

        # Store the request.
        self.pending_incoming_requests_threads.add(gevent.getcurrent())

        # Build the response.
        response = {"__id": id_,
                    "__data": None,
                    "__error": None}

        method_name = request["__method"]

        if not hasattr(self.local_service, method_name):
            response["__error"] = "Method %s doesn't exist." % method_name
        else:
            method = getattr(self.local_service, method_name)

            if not getattr(method, "rpc_callable", False):
                response["__error"] = "Method %s isn't callable." % method_name
            else:
                try:
                    response["__data"] = method(**request["__data"])
                except Exception as error:
                    response["__error"] = "%s: %s\n%s" % \
                        (error.__class__.__name__, error,
                         traceback.format_exc())

        # Encode it.
        try:
            data = json.dumps(response).encode('utf-8')
        except (TypeError, ValueError):
            logger.warning("JSON encoding failed.", exc_info=True)
            return

        # Send it.
        try:
            self._write(data)
        except IOError:
            # Log messages have already been produced.
            return


class RemoteServiceClient(RemoteServiceBase):
    """The client side of a RPC communication.

    Considers all messages coming from the other end as responses for
    RPCs previously sent. Will parse them and forward them to the
    original callers.

    It also offers an interface to issue RPCs, with execute_rpc and
    some syntactic sugar.

    After having created an instance and initialized it with a socket
    the reader loop should be started by calling run.

    """
    def __init__(self, remote_service_coord, auto_retry=None):
        """Create a caller for the service at the given coords.

        remote_service_coord (ServiceCoord): the coordinates (i.e. name
            and shard) of the service to which to send RPC requests.
        auto_retry (float|None): if a number is given then it's the
            interval (in seconds) between attempts to reconnect to the
            remote service in case the connection is lost; if not given
            no automatic reconnection attempts will occur.

        raise (KeyError): if the coordinates are not specified in the
            configuration.

        """
        super(RemoteServiceClient, self).__init__(
            get_service_address(remote_service_coord))
        self.remote_service_coord = remote_service_coord

        self.pending_outgoing_requests = dict()
        self.pending_outgoing_requests_results = dict()

        self.auto_retry = auto_retry

        self._loop = None

    def _repr_remote(self):
        """See RemoteServiceBase._repr_remote."""
        return "%s:%d (%r)" % (self.remote_address +
                               (self.remote_service_coord,))

    def finalize(self, reason=""):
        """See RemoteServiceBase.finalize."""
        super(RemoteServiceClient, self).finalize(reason)

        for result in itervalues(self.pending_outgoing_requests_results):
            result.set_exception(RPCError(reason))

        self.pending_outgoing_requests.clear()
        self.pending_outgoing_requests_results.clear()

    def _connect(self):
        """Establish a connection and initialize that socket.

        """
        try:
            sock = gevent.socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(self.remote_address)
        except socket.error as error:
            logger.debug("Couldn't connect to %s: %s.",
                         self._repr_remote(), error)
        else:
            self.initialize(sock, self.remote_service_coord)

    def _run(self):
        """Maintain the connection up, if required.

        """
        if self.connected:
            self.run()

        if self.auto_retry is not None:
            while True:
                self._connect()
                while not self.connected:
                    gevent.sleep(self.auto_retry)
                    self._connect()
                self.run()

    def connect(self):
        """Connect and start the main loop.

        """
        self._connect()
        self._loop = gevent.spawn(self._run)

    def disconnect(self):
        """See RemoteServiceBase.disconnect."""
        if super(RemoteServiceClient, self).disconnect():
            self._loop.kill()
            self._loop = None

    def run(self):
        """Start listening for responses, and go on forever.

        Read messages from the socket and issue greenlets to parse
        them, determine the request they're for and fill the results.
        This method won't return as long as there's something to read,
        it's therefore advisable to spawn a greenlet to call it.

        """
        while True:
            try:
                data = self._read()
            except IOError:
                break

            if len(data) == 0:
                self.finalize("Connection closed.")
                break

            gevent.spawn(self.process_data, data)

    def process_data(self, data):
        """Handle the message.

        JSON-decode it and forward it to process_incoming_response
        (unconditionally!).

        data (bytes): the message read from the socket.

        """
        # Decode the incoming data.
        try:
            message = json.loads(data.decode('utf-8'))
        except ValueError:
            logger.warning("Cannot parse incoming message, discarding.")
            return

        self.process_incoming_response(message)

    def process_incoming_response(self, response):
        """Handle the response.

        Parse the response, determine the request it's for and its
        associated result and fill it.

        response (dict): the JSON-decoded response.

        """
        # Validate the response.
        if not {"__id", "__data", "__error"}.issubset(iterkeys(response)):
            logger.warning("Response is missing some fields, ingoring.")
            return

        # Determine the ID.
        id_ = response["__id"]

        if id_ not in self.pending_outgoing_requests:
            logger.warning("No pending request with id %s found.", id_)
            return

        request = self.pending_outgoing_requests.pop(id_)
        result = self.pending_outgoing_requests_results.pop(id_)
        error = response["__error"]

        if error is not None:
            err_msg = "%s signaled RPC for method %s was unsuccessful: %s." % (
                self.remote_service_coord, request["__method"], error)
            logger.error(err_msg)
            result.set_exception(RPCError(error))
        else:
            result.set(response["__data"])

    def execute_rpc(self, method, data):
        """Send an RPC request to the remote service.

        method (string): the name of the method to call.
        data (dict): keyword arguments to pass to the methods.

        return (AsyncResult): an object that holds (or will hold) the
            result of the call, either the value or the error that
            prevented successful completion.

        """
        # Determine the ID.
        id_ = uuid.uuid4().hex

        # Build the request.
        request = {"__id": id_,
                   "__method": method,
                   "__data": data}

        result = gevent.event.AsyncResult()

        # Encode it.
        try:
            data = json.dumps(request).encode('utf-8')
        except (TypeError, ValueError):
            logger.error("JSON encoding failed.", exc_info=True)
            result.set_exception(RPCError("JSON encoding failed."))
            return result

        # Send it.
        try:
            self._write(data)
        except IOError:
            result.set_exception(RPCError("Write failed."))
            return result

        # Store it.
        self.pending_outgoing_requests[id_] = request
        self.pending_outgoing_requests_results[id_] = result

        return result

    def __getattr__(self, method):
        """Syntactic sugar to enable a transparent proxy.

        All unresolved attributes on this object are interpreted as
        methods of the remote service and therefore a wrapper function
        is returned that will call execute_rpc with the proper args.

        As an additional comfort, one can also insert a "callback" and
        (optionally) a "plus" item among the keywords arguments in the
        call to the returned function to be notified when the RPC ends.
        The callback should be a callable able to receive the data and
        (optionally) the plus object as positional args and the error
        as a keyword arg. It will be run in a dedicated greenlet.

        method (string): the name of the accessed method.
        return (function): a proxy to a RPC.

        """
        def run_callback(func, plus, result):
            """Execute the given callback safely.

            Get data and/or error from result and call func passing it
            data, plus (if needed) and error. Catch, log and suppress
            all exceptions.

            func (function): the callback to invoke.
            plus (object): optional additional data.
            result (AsyncResult): the result of a (finished) RPC call.

            """
            data = result.value
            error = None if result.successful() else "%s" % result.exception
            try:
                if plus is None:
                    func(data, error=error)
                else:
                    func(data, plus, error=error)
            except Exception as error:
                logger.error("RPC callback for %s.%s raised exception.",
                             self.remote_service_coord.name, method,
                             exc_info=True)

        def remote_method(**data):
            """Forward arguments to execute_rpc.

            """
            callback = data.pop("callback", None)
            plus = data.pop("plus", None)
            result = self.execute_rpc(method=method, data=data)
            if callback is not None:
                callback = functools.partial(run_callback, callback, plus)
                result.rawlink(functools.partial(gevent.spawn, callback))
            return result

        return remote_method


class FakeRemoteServiceClient(RemoteServiceClient):
    """A RemoteServiceClient not actually connected to anything.

    This is useful for connections to optional services, to avoid
    having to specify different behaviors in the case the services are
    or are not available.

    In all aspects, an object of this class behaves exactly like a
    RemoteServiceClient that will never be able to connect.

    """
    def __init__(self, remote_service_coord, auto_retry=None):
        """Initialization.

        This constructor does not call the parent constructor, because
        it would fail (as the service coord are not in the
        configuration). This is potentially a problem, but as this
        client will never connect not many member variable access are
        performed.

        """
        RemoteServiceBase.__init__(self, Address("None", 0))
        self.remote_service_coord = remote_service_coord
        self.pending_outgoing_requests = dict()
        self.pending_outgoing_requests_results = dict()
        self.auto_retry = auto_retry

    def connect(self):
        """Do nothing, as this is a fake client."""
        pass

    def disconnect(self):
        """Do nothing, as this is a fake client."""
        return True

    def execute_rpc(self, method, data):
        """Just return an AsyncResult encoding an error."""
        result = gevent.event.AsyncResult()
        result.set_exception(
            RPCError("Called a method of a non-configured service."))
        return result
