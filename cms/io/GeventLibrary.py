#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2013 Stefano Maggiolo <s.maggiolo@gmail.com>
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

import errno
import heapq
import json
import logging
import os
import pwd
import signal
import _socket
import time
import traceback
import uuid
from functools import wraps

import gevent
import gevent.socket
import gevent.event
from gevent.server import StreamServer
from gevent.backdoor import BackdoorServer

from cms import config, mkdir
from cms.log import root_logger, shell_handler, ServiceFilter, \
    CustomFormatter, LogServiceHandler, FileHandler
from cms.io import ServiceCoord, Address, get_service_address
from cms.io.PsycoGevent import make_psycopg_green
from cmscommon.datetime import monotonic_time


logger = logging.getLogger(__name__)


# Fix psycopg in order to support gevent greenlets
make_psycopg_green()


def rpc_callback(func):
    """Tentative decorator for a RPC callback function. Up to now it
    does not do a lot, I hope to be able to manage errors in a
    Pythonic way.

    """
    @wraps(func)
    def newfunc(self, *args, **kwargs):
        """Mangle __error and give back error when appropriate.

        """
        if "__error" in kwargs:
            if kwargs["__error"] is not None:
                kwargs["error"] = kwargs["__error"]
# We want to be able to manage the exception, so no raise.
#                raise Exception(kwargs["__error"])
            del kwargs["__error"]
        return func(self, *args, **kwargs)

    return newfunc


def rpc_method(func):
    """Decorator for a method that other services are allowed to
    call. Does not do a lot, just defines the right method's
    attribute.

    """
    func.rpc_callable = True
    return func


class AuthorizationError(Exception):
    pass


class RPCRequest(object):
    """Class to keep the state of an RPC request, while we were
    waiting for the response. There is also a class variable that
    stores all the pending RPC requests.

    """
    pending_requests = {}

    def __init__(self, message, bind_obj, callback, plus):
        """Create the istance of a RPC query.

        message (object): the message to send.
        bind_obj (object): the context for the callback.
        callback (function): the function to call on completion.
        plus (object): additional argument for callback.

        """
        self.message = message
        self.bind_obj = bind_obj
        self.callback = callback
        self.plus = plus

    def pre_execute(self):
        """Store in the class the RPC request before sending it, in
        order to couple later the response.

        return (object): the object to send.
        """
        self.message["__id"] = uuid.uuid4().hex
        RPCRequest.pending_requests[self.message["__id"]] = self

        return self.message

    def complete(self, response):
        """To be called when the response arrives. It deletes the
        stored state and executes the callback.

        response (object): The response, already decoded from JSON.

        """
        del RPCRequest.pending_requests[self.message["__id"]]
        if self.callback is not None:
            params = []
            if self.bind_obj is not None:
                params.append(self.bind_obj)
            params.append(response["__data"])
            if self.plus is not None:
                params.append(self.plus)
            gevent.spawn(self.callback,
                         *params,
                         __error=response.get("__error", None))
        else:
            error = None
            if response is not None:
                error = response.get("__error", None)
            if error is not None:
                try:
                    err_msg = "Error in the call without callback `%s': " \
                              "%s." % (self.message["__method"], error)
                except KeyError:
                    err_msg = "Error in a call without callback: %s." % \
                              error
                logger.error(err_msg)


class Service(object):

    def __init__(self, shard=0):
        signal.signal(signal.SIGINT, lambda unused_x, unused_y: self.exit())

        self.name = self.__class__.__name__
        self.shard = shard

        self.initialize_logging()

        # Stores the function to call periodically. It is to be
        # managed with heapq. Format: (next_timeout, period, function,
        # plus)
        self._timeouts = []
        # Whether we want to exit the main loop
        self._exit = False
        # Dictionaries of (to be) connected RemoteService, and
        # dictionaries of callback functions that are going to be
        # called every time the remote service becomes online.
        self.remote_services = {}
        self.on_remote_service_connected = {}
        # Event to signal that something happened and the sleeping in
        # run() must be interrupted
        self.event = gevent.event.Event()
        self.event.clear()

        self._my_coord = ServiceCoord(self.name, self.shard)

        # We setup the listening address for services which want to
        # connect with us.
        try:
            address = get_service_address(self._my_coord)
        except KeyError:
            address = None
        if address is not None:
            self.server = StreamServer(address, self._connection_handler)
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
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(CustomFormatter(False))
        file_handler.addFilter(filter_)
        root_logger.addHandler(file_handler)

        # Provide a symlink to the latest log file.
        try:
            os.remove(os.path.join(log_dir, "last.log"))
        except OSError:
            pass
        os.symlink(log_filename,
                   os.path.join(log_dir, "last.log"))

        # Setup a remote LogService handler (except when we already are
        # LogService, to avoid circular logging).
        if self.name != "LogService":
            log_service = RemoteService(None, ServiceCoord("LogService", 0))
            remote_handler = LogServiceHandler(log_service)
            remote_handler.setLevel(logging.INFO)
            remote_handler.addFilter(filter_)
            root_logger.addHandler(remote_handler)

    def _connection_handler(self, socket, address):
        """Receive and act upon an incoming connection.

        A new RemoteService is spawned to take care of the new
        connection.

        """
        try:
            ipaddr, port = address
            ipaddr = gevent.socket.gethostbyname(ipaddr)
            address = Address(ipaddr, port)
        except:
            logger.warning("Error: %s" % (traceback.format_exc()))
            return
        remote_service = RemoteService(self, address=address)
        remote_service.initialize_channel(socket)

    def connect_to(self, service, on_connect=None):
        """Ask the service to connect to another service. A channel is
        established and connected. The connection will be reopened if
        closed.

        service (ServiceCoord): the service to connect to.
        on_connect (function): to be called when the service connects.
        return (RemoteService): the connected RemoteService istance.

        """
        self.on_remote_service_connected[service] = on_connect
        self.remote_services[service] = RemoteService(self, service)
        return self.remote_services[service]

    def add_timeout(self, func, plus, seconds, immediately=False):
        """Registers a function to be called every x seconds.

        func (function): the function to call.
        plus (object): additional data to pass to the function.
        seconds (float): the function will be called every seconds
                         seconds.
        immediately (bool): if True, func will be called also at the
                            beginning.

        """
        next_timeout = monotonic_time()
        if not immediately:
            next_timeout += seconds
        heapq.heappush(self._timeouts, (next_timeout, seconds, func, plus))

        # Wake up the run() cycle
        self.event.set()

    def exit(self):
        """Terminate the service at the next step.

        """
        logger.warning("%s %d received request to shut down" % self._my_coord)
        self._exit = True

        # Wake up the run() cycle
        self.event.set()

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
        backdoor_sock = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
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
            self.server.start()

        # This must come before socket.error, because socket.gaierror
        # extends socket.error
        except gevent.socket.gaierror:
            logger.critical("Service %s could not listen on "
                            "specified address, because it cannot "
                            "be resolved." % (self.name))
            return False

        except gevent.socket.error as (error, unused_msg):
            if error == errno.EADDRINUSE:
                logger.critical("Listening port %s for service %s is "
                                "already in use, quitting." %
                                (self.server.address.port,
                                 self.name))
                return False
            elif error == errno.EADDRNOTAVAIL:
                logger.critical("Service %s could not listen on "
                                "specified address, because it is not "
                                "available." % (self.name))
                return False
            else:
                raise

        if config.backdoor:
            self.start_backdoor()

        logger.info("%s %d up and running!" % self._my_coord)

        try:
            while not self._exit:
                next_timeout = self._trigger(maximum=0.5)
                self.event.clear()
                self.event.wait(timeout=next_timeout)
        except Exception as error:
            err_msg = "Exception not managed, quitting. " \
                      "Exception `%s' and traceback `%s'" % \
                      (repr(error), traceback.format_exc())
            logger.critical(err_msg)

        logger.info("%s %d is shutting down" % self._my_coord)

        if config.backdoor:
            self.stop_backdoor()

        self._disconnect_all()
        self.server.stop()
        return True

    def _reconnect(self):
        """Reconnect to all remote services that have been disconnected.

        """
        for service in self.remote_services:
            remote_service = self.remote_services[service]
            if not remote_service.connected:
                try:
                    remote_service.connect_remote_service()
                except:
                    pass
                if remote_service.connected and \
                        self.on_remote_service_connected[service] \
                        is not None:
                    self.on_remote_service_connected[service](service)
        return True

    def _disconnect_all(self):
        """Disconnect all remote services.

        """
        for service in self.remote_services:
            remote_service = self.remote_services[service]
            if remote_service.connected:
                remote_service.disconnect_remote_service()

    def _trigger(self, maximum=2.0):
        """Call the timeouts that have expired and find interval to
        next timeout (capped to maximum second).

        maximum (float): seconds to cap to the value.
        return (float): seconds to next timeout.

        """
        current = monotonic_time()

        # Try to connect to disconnected services.
        self._reconnect()

        # Check if some scheduled function needs to be called.
        while self._timeouts != []:
            timeout_data = self._timeouts[0]
            next_timeout, _, _, _ = timeout_data
            if current > next_timeout:
                heapq.heappop(self._timeouts)

                # The helper function checks the return value and, if
                # needed, enqueues the next timeout call
                def helper(timeout_data):
                    next_timeout, seconds, func, plus = timeout_data
                    if plus is None:
                        ret = func()
                    else:
                        ret = func(plus)
                    if ret:
                        heapq.heappush(self._timeouts,
                                       (next_timeout + seconds,
                                        seconds, func, plus))

                gevent.spawn(helper, timeout_data)
            else:
                break

        # Compute time to next timeout call
        next_timeout = maximum
        if self._timeouts != []:
            next_timeout = min(next_timeout, self._timeouts[0][0] - current)
        return max(0.0, next_timeout)

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
        logger.info("Trying to exit as asked by another service (%s)."
                    % reason)
        self.exit()

    def method_info(self, method_name):
        """Returns some information about the requested method, or
        exceptions if the method does not exists.

        method_name (string): the requested method
        return (dict): infos about the method

        """
        try:
            method = getattr(self, method_name)
        except:
            raise KeyError("Service has no method " + method_name)

        res = {}
        res["callable"] = hasattr(method, "rpc_callable")

        return res

    def handle_message(self, message):
        """To be called when the channel finishes to collect a message
        that is a RPC request. It calls the requested method.

        message (object): the decoded message.
        return (object, bool): the object is the value returned by the
                               method, the bool is True if the object
                               is to be interpreted as a binary
                               string.
        """
        method_name = message["__method"]
        try:
            method = getattr(self, method_name)
        except:
            raise KeyError("Service has no method " + method_name)

        if not hasattr(method, "rpc_callable"):
            raise AuthorizationError("Method %s not callable from RPC" %
                                     method)

        if "__data" not in message:
            raise ValueError("No data present when calling %s." %
                             (method_name))

        result = method(**message["__data"])

        return result


class RemoteService(object):
    """This class mimick the local presence of a remote service. A
    local service can define many RemoteService object and call
    methods of those services almost as if they were local. Almost
    because being asynchronous, the responses of the requests have to
    be collected using callback functions.

    """

    # Requests bigger than 100 KiB are dropped to avoid DOS attacks
    # XXX - Check that these sizes are sensible
    RECV_SIZE = 4096
    MAX_INBOX_SIZE = 1024 * 1024

    def __init__(self, service, remote_service_coord=None, address=None):
        """Create a communication channel to a remote service.

        service (Service): the local service.
        remote_service_coord (ServiceCoord): the description of the
                                             remote service to connect
                                             to.
        address (Address): alternatively, the address to connect to
                           (used when accepting a connection).

        """
        if address is None and remote_service_coord is None:
            raise ValueError("Please provide address or "
                             "remote_service_coord")

        # service is the local service connecting to the remote one.
        self.service = service

        if address is None:
            self.remote_service_coord = remote_service_coord
            self.address = get_service_address(remote_service_coord)
        else:
            self.remote_service_coord = ""
            self.address = address
        self.connected = False

    def _loop(self):
        inbox = b''
        ignore_first_message = False
        while True:
            try:
                buf = self.socket.recv(RemoteService.RECV_SIZE)
            except gevent.socket.error as (error, msg):
                if self.remote_service_coord == '':
                    logger.warning("Connection with unknown "
                                   "remote service was lost"
                                   " (%s)" % (msg))
                else:
                    logger.warning("Connection with remote "
                                   "service %s was lost"
                                   " (%s)"
                                   % (self.remote_service_coord, msg))
                self.connected = False
                break

            splits = (inbox + buf).split('\r\n')
            inbox = splits[-1]

            # Check that the data buffer doesn't exceed a maximum
            # size; otherwise, this could be a DOS attack vector
            # TODO - This check is disabled, because it risks to stop
            # legitimate messages; we have to carefully check which
            # maximum length has to be considered acceptable
            # TODO - This check wouldn't work as expected anyway,
            # because it does prevent the first message from being
            # interpreted, but it doesn't prevent the inbox to be
            # bloated with a good share of it
            #if len(inbox) > RemoteService.MAX_INBOX_SIZE:
            #    inbox = b''
            #    ignore_first_message = True
            #    logger.error("Message too long, I'm discarding it")

            # Process incoming data
            for data in splits[:-1]:
                if ignore_first_message:
                    ignore_first_message = False
                    continue
                #logger.debug("Message length: %d" % (len(data)))
                gevent.spawn(self.process_data, data)

            # Connection has been closed
            if buf == b'':
                self.connected = False
                break

    def initialize_channel(self, sock):
        """When we have a socket, we configure the channel using this
        socket. This spawns a new Greenlet that monitors the incoming
        channel and collects data.

        sock (socket): the socket to use as a communication channel.
        """
        self.socket = sock
        self.connected = True
        gevent.spawn(self._loop)

    def process_data(self, data):
        """Function called when a terminator is detected in the
        stream. It clears the buffer and decode the data. Then it asks
        the local service to act and in case the service wants to
        respond, it sends back the response.

        data (string): the raw string received from the remote party,
                       to be JSON-decoded.

        """
        # We decode the arriving data
        try:
            message = json.loads(data, encoding='utf-8')
        except ValueError:
            logger.warning("Cannot understand incoming message, discarding.")
            return

        # If __method is present, someone is calling an rpc of the
        # local service
        if "__method" in message:
            # We initialize the data we are going to send back
            response = {"__data": None,
                        "__error": None}
            if "__id" in message:
                response["__id"] = message["__id"]

            # Otherwise, we compute the method here and send the reply
            # right away.
            try:
                method_response = self.service.handle_message(message)
            except Exception as exception:
                response["__error"] = "%s: %s\n%s" % \
                    (exception.__class__.__name__, exception,
                     traceback.format_exc())
                method_response = None
            self.send_reply(response, method_response)

        # Otherwise, is a response to our rpc call.
        else:
            if "__id" not in message:
                logger.warning("Response without __id field, discarding.")
                return
            ident = message["__id"]
            if ident in RPCRequest.pending_requests:
                rpc = RPCRequest.pending_requests[ident]
                rpc.complete(message)
            else:
                logger.warning("No pending request with id %s found." % ident)

    def send_reply(self, response, method_response):
        """Send back a reply to an rpc call.

        response (dict): the metadata of the reply.
        method_response (object): the actual returned value.

        """
        response["__data"] = method_response
        try:
            json_message = json.dumps(response, encoding='utf-8')
        except ValueError as error:
            logger.warning("Cannot send response because of " +
                           "encoding error. %s" % repr(error))
            return
        self._push_right(json_message)

    def connect_remote_service(self):
        """Try to connect to the remote service.

        """
        try:
            sock = gevent.socket.socket(gevent.socket.AF_INET,
                                        gevent.socket.SOCK_STREAM)
            sock.connect(self.address)
        except:
            pass
        else:
            self.initialize_channel(sock)

    def disconnect_remote_service(self):
        """Disconnect from remote service.

        Errors are silently ignored.

        """
        try:
            self.socket.shutdown(gevent.socket.SHUT_RDWR)
            self.socket.close()
        except:
            pass
        self.connected = False

    def execute_rpc(self, method, data, callback=None, plus=None):
        """Method to send an RPC request to the remote service.

        The message sent to the remote service is of this kind:
        {"__method": <name of the requested method>
         "__data": {"<name of first arg>": <value of first arg,
                    ...
                   }
         "__id": <32-digit hex-encoded UUID>
        }

        The __id field is put by the pre_execute method of
        RPCRequest.

        method (string): the name of the method to call.
        data (object): the object to pass to the remote method.
        callback (function): method to call with the RPC response.
        plus (object): additional object to be passed to the callback.

        return (bool|dict): False if the remote service is not
            connected; in a non-yielded call True if it is connected;
            in a yielded call, a dictionary with fields 'completed',
            'data', and 'error'.

        """
        # Try to connect, or fail.
        if not self.connected:
            self.connect_remote_service()
            if not self.connected:
                return False

        # We start building the request message
        message = {}
        message["__method"] = method
        message["__data"] = data

        # And we remember that we need to wait for a reply
        request = RPCRequest(message, self.service, callback, plus)
        message = request.pre_execute()

        # We encode the request and send it
        try:
            json_message = json.dumps(message, encoding='utf-8')
        except ValueError:
            msg = "Cannot send request of method %s because of " \
                "encoding error." % method
            request.complete({"__error": msg})
            return
        ret = self._push_right(json_message)
        if not ret:
            msg = "Transfer interrupted"
            request.complete({"__error": msg})
            return

        return True

    def __getattr__(self, method):
        """Syntactic sugar to call a remote method without using
        execute_rpc. If the local service asks for something that is
        not present, we assume that it is a remote RPC method.

        method (string): the method to call.

        """
        def remote_method(callback=None,
                          plus=None,
                          **data):
            """Call execute_rpc with the given method name.

            """
            return self.execute_rpc(method=method, data=data,
                                    callback=callback, plus=plus)
        return remote_method

    def _push_right(self, data):
        """Send a request or a response with the right terminator in
        the end.

        data (string): the data to send.

        """
        to_push = b''.join(data) + b'\r\n'
        try:
            while to_push != b'':
                num = self.socket.send(to_push)
                to_push = to_push[num:]
                if num == 0:
                    logger.warning("Push not ended correctly: socket close.")
                    self.connected = False
                    return False
        except Exception as error:
            logger.warning("Push not ended correctly because of %r." % error)
            return False
        return True
