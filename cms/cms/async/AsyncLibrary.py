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

"""This file defines classes to handle asynchronous RPC communication
usinc asynchat and JSON encoding.

"""

import socket
import time
import sys
import os
import threading

import asyncore
import asynchat
import datetime
import codecs

from Utils import random_string, mkdir, \
     encode_binary, encode_length, encode_json, \
     decode_binary, decode_length, decode_json
from cms.async import ServiceCoord, Address, get_service_address


def rpc_callback(func):
    """Tentative decorator for a RPC callback function. Up to now it
    does not do a lot, I hope to be able to manage errors in a
    Pythonic way.

    """

    def newfunc(self, *args, **kwargs):
        """Mangle __error and give back error when appropriate.

        """
        if "__error" in kwargs:
            if kwargs["__error"] != None:
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


def rpc_binary_response(func):
    """Decorator for a RPC method that wants its response to be
    treated as a binary string.

    """
    func.binary_response = True
    return func


def rpc_threaded(func):
    """Decorator for a RPC method that we want to execute in a
    separate thread.

    """
    func.threaded = True
    return func


class AuthorizationError(Exception):
    pass


class RPCRequest:
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
        logger.debug("RPCRequest.__init__")
        self.message = message
        self.bind_obj = bind_obj
        self.callback = callback
        self.plus = plus

    def pre_execute(self):
        """Store in the class the RPC request before sending it, in
        order to couple later the response.

        return (object): the object to send.
        """
        logger.debug("RPCRequest.pre_execute")
        self.message["__id"] = random_string(16)
        RPCRequest.pending_requests[self.message["__id"]] = self

        return self.message

    def complete(self, response):
        """To be called when the response arrive. It deletes the
        stored state and execute the callback.

        response (object): The response, already decoded from JSON.
        """
        logger.debug("RPCRequest.complete")
        del RPCRequest.pending_requests[self.message["__id"]]
        if self.callback != None:
            params = []
            if self.bind_obj != None:
                params.append(self.bind_obj)
            params.append(response["__data"])
            if self.plus != None:
                params.append(self.plus)
            self.callback(*params,
                          __error=response.get("__error", None))
        else:
            error = response.get("__error", None)
            if error != None:
                logger.error("Error in a call without callback: %s" % error)


class Service:
    """Interface to be subclassed of an RPC service using JSON
    encoding. It is designed for a service that accept requests and
    also query other services, but it can be used for services that
    need only one of the two behaviours.

    """
    def __init__(self, shard=0):
        logger.debug("Service.__init__")
        self.shard = shard
        self._timeouts = {}
        self._seconds = 0
        self._connections = set([])
        self._exit = False
        self._threaded_responses = []
        self._threaded_responses_lock = threading.Lock()
        self.remote_services = {}

        self._my_coord = ServiceCoord(self.__class__.__name__, self.shard)
        self.add_timeout(self._reconnect, None, 10, immediately=True)
        try:
            address = get_service_address(self._my_coord)
        except KeyError:
            address = None
        if address != None:
            self.server = ListeningSocket(self, address)

    def connect_to(self, service, sync=False):
        """Ask the service to connect to another service. A channel is
        established and connected. The connection will be reopened if
        closed.

        service (ServiceCoord): the service to connect to.
        return (RemoteService): the connected RemoteService istance.
        """
        self._connections.add(service)
        self.remote_services[service] = RemoteService(self, service, sync=sync)
        try:
            self.remote_services[service].connect_remote_service()
        except:
            pass
        return self.remote_services[service]

    def add_timeout(self, func, plus, seconds, immediately=False):
        """Registers a function to be called every tot seconds.

        func (function): the function to call.
        plus (object): additional data to pass to the function.
        seconds (float): the function will be called every seconds
                         seconds.
        immediately (bool): if True, func will be called also at the
                            beginning.

        """
        last = time.time()
        if immediately:
            last -= seconds
        self._timeouts[func] = [plus, seconds, last]

    def exit(self):
        """Terminate the service at the next step.

        """
        self._exit = True

    def run(self):
        """Starts the main loop of the service.

        """
        logger.debug("Service.run")
        while not self._exit:
            self._step()

    def _step(self):
        """One step of the main loop.

        """
        # Let's not spam the logs...
        # logger.debug("Service._step")
        asyncore.loop(0.02, True, None, 1)
        self._trigger()

    def _reconnect(self):
        """Reconnect to all remote services that have been disconnected.

        """
        logger.debug("Service._reconnect")
        for service in self._connections:
            remote_service = self.remote_services[service]
            if not remote_service.connected:
                try:
                    remote_service.connect_remote_service()
                except:
                    pass
        return True

    def _trigger(self):
        """Call the timeouts that have expired.

        """
        current = time.time()

        # Check if some threaded RPC call ended
        self._threaded_responses_lock.acquire()
        local_threaded_responses = self._threaded_responses[:]
        self._threaded_responses = []
        self._threaded_responses_lock.release()
        for remote_service, response in local_threaded_responses:
            remote_service.send_reply(*response)

        # Check if some scheduled function needs to be called
        for func in self._timeouts.keys():
            plus, seconds, timestamp = self._timeouts[func]
            if current - timestamp > seconds:
                self._timeouts[func][2] = current
                if plus == None:
                    ret = func()
                else:
                    ret = func(plus)
                if not ret:
                    del self._timeouts[func]

    @rpc_method
    def echo(self, string):
        """Simple RPC method.

        string (string): the string to be echoed.
        return (string): string, again.

        """
        logger.debug("Service.echo")
        return string

    def handle_rpc_response(self, message):
        """To be called when the channel finishes to collect a message
        that is a response. It ask the RPCRequest do complete the
        conversation.

        message (object): the decoded message.
        """
        logger.debug("Service.handle_rpc_response")
        if "__id" not in message:
            logger.error("Response without __id field detected, discarding.")
            return
        ident = message["__id"]
        if ident in RPCRequest.pending_requests:
            rpc = RPCRequest.pending_requests[ident]
            rpc.complete(message)
        else:
            logger.error("No pending request with id %s found." % ident)

    def method_info(self, method_name):
        """Returns some information about the requested method, or
        exceptions if the method does not exists.

        method_name (string): the requested method
        return (dict): infos about the method

        """
        logger.debug("Service.method_info")

        try:
            method = getattr(self, method_name)
        except:
            raise KeyError("Service has no method " + method_name)

        res = {}
        res["callable"] = hasattr(method, "rpc_callable")
        res["binary_response"] = hasattr(method, "binary_response")
        res["threaded"] = hasattr(method, "threaded")

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
        logger.debug("Service.handle_message")

        method_name = message["__method"]
        try:
            method = getattr(self, method_name)
        except:
            raise KeyError("Service has no method " + method_name)

        if not hasattr(method, "rpc_callable"):
            raise AuthorizationError("Method %s not callable from RPC" %
                                     method)

        if "__data" not in message:
            raise ValueError("No data present.")

        result = method(**message["__data"])

        return result


class ThreadedRPC(threading.Thread):
    """In this class we run the computation of rpc methods defined
    with the @rpc_threaded decorator. The found_terminator method
    start this thread and then returns immediately. When the
    computation is done, we store the result in a list in the service
    class, that send the appropriate reply to the remote service when
    it can.

    """
    def __init__(self, remote_service, message,
                 response, binary_response):
        """Initialize the thread.

        remote_service (RemoteService): the service that called our
                                        method.
        message (dict): the coordinate to pass to the local service
                          to run the appropriate rpc method with the
                          right parameters.
        response (dict): the partial reply (to be integrated with the
                         actual value returned by the rpc method).
        binary_response (bool): if the method is supposed to return a
                                binary string.

        """
        threading.Thread.__init__(self)
        self.remote_service = remote_service
        self.service = self.remote_service.service
        self.response = response
        self.binary_response = binary_response
        self.message = message

    def run(self):
        """When the thread runs, it execute the rpc method and fill
        the appropriate list in the service class with the result. The
        list _threaded_responses contains elements of this format:
        (remote_service, parameters_of_the_send_reply_method).

        """
        try:
            method_response = self.service.handle_message(self.message)
        except Exception, exception:
            print exception
            self.response["__error"] = "%s: %s" % (
                exception.__class__.__name__,
                " ".join([str(x) for x in exception.args]))
            self.binary_response = False
            method_response = None
        self.service._threaded_responses_lock.acquire()
        self.service._threaded_responses.append((self.remote_service,
            (self.response,
             method_response,
             self.binary_response)))
        self.service._threaded_responses_lock.release()

class SyncRPCError(Exception):
    pass

class RemoteService(asynchat.async_chat):
    """This class mimick the local presence of a remote service. A
    local service can define many RemoteService object and call
    methods of those services almost as if they were local. Almost
    because being asynchronous, the responses of the requests have to
    be collected using callback functions.

    """

    def __init__(self, service, remote_service_coord=None,
                 address=None, sync=False):
        """Create a communication channel to a remote service.

        service (Service): the local service.
        remote_service_coord (ServiceCoord): the description of the
                                             remote service to connect
                                             to.
        address (Address): alternatively, the address to connect to
                           (used when accepting a connection).
        sync (bool): if True, all rpc calls return immediately

        """
        # Can't log using logger here, since it is not yet defined.
        # logger.debug("RemoteService.__init__")
        if address == None and remote_service_coord == None:
            raise
        self.service = service
        self.sync = sync
        self.sync_responses = {}
        if address == None:
            self.remote_service_coord = remote_service_coord
            self.address = get_service_address(remote_service_coord)
        else:
            self.remote_service_coord = ""
            self.address = address
        self.connected = False
        self.data = []

    def _initialize_channel(self, sock):
        """When we have a socket, we configure the channel using this
        socket.

        sock (socket): the socket to use as a communication channel.
        """
        logger.debug("RemoteService._initialize_channel")
        asynchat.async_chat.__init__(self, sock)
        self.set_terminator("\r\n")

    def collect_incoming_data(self, data):
        """Function called when something arrived through the socket.

        data (string): arrived data.
        """
        logger.debug("RemoteService.collect_incoming_data")
        if self.service == None:
            return
        self.data.append(data)

    def found_terminator(self):
        """Function called when a terminator is detected in the
        stream. It clear the cache and decode the data. Then it ask
        the local service to act and in case the service wants to
        respond, it sends back the response.

        """
        logger.debug("RemoteService.found_terminator")
        if self.service == None:
            return
        data = "".join(self.data)
        self.data = []

        try:
            json_length = decode_length(data[:4])
            message = decode_json(data[4:json_length + 4])
            if len(data) > json_length + 4:
                if message["__data"] == None:
                    message["__data"] = \
                        decode_binary(data[json_length + 4:])
                else:
                    message["__data"]["binary_data"] = \
                        decode_binary(data[json_length + 4:])
        except:
            logger.error("Cannot understand incoming message, discarding.")
            return

        response = {"__data": None,
                    "__error": None}
        if "__id" in message:
            response["__id"] = message["__id"]
        if "__method" in message:
            # We first find the properties of the called rpc method.
            try:
                method_info = self.service.method_info(message["__method"])
                binary_response = method_info["binary_response"]
                threaded = method_info["threaded"]
            except KeyError:
                response["__error"] = "%s: %s" % (
                    exception.__class__.__name__,
                    " ".join([str(x) for x in exception.args]))
                binary_response = False
                method_response = None

            # If the rpc method is threaded, then we start the thread
            # and return immediately.
            if threaded:
                t = ThreadedRPC(self, message, response, binary_response)
                t.start()
                return
            # Otherwise, we compute the method here and send the reply
            # right away.
            try:
                method_response = self.service.handle_message(message)
            except Exception, exception:
                response["__error"] = "%s: %s" % (
                    exception.__class__.__name__,
                    " ".join([str(x) for x in exception.args]))
                binary_response = False
                method_response = None
            self.send_reply(response, method_response, binary_response)
        else:
            self.service.handle_rpc_response(message)

    def send_reply(self, response, method_response, binary_response):
        """Send back a reply to an rpc call.

        response (dict): the metadata of the reply.
        method_response (object): the actual returned value.
        binary_response (bool): True if method_response is a binary string.

        """
        try:
            if binary_response:
                response["__data"] = None
                binary_message = encode_binary(method_response)
            else:
                response["__data"] = method_response
                binary_message = ""
            json_message = encode_json(response)
            json_length = encode_length(len(json_message))
        except ValueError as e:
            logger.error("Cannot send response because of " +
                         "encoding error. %s" % repr(e))
            return
        self._push_right(json_length + json_message + binary_message)

    def execute_rpc(self, method, data,
                    callback=None, plus=None, bind_obj=None):
        """Method to send an RPC request to the remote service.

        The message sent to the remote service is of this kind:
        {"__method": <name of the requested method>
         "__data": {"<name of first arg>": <value of first arg,
                    ...
                   }
         "__id": <16 letters random ID>
        }

        The __id field is put by the pre_execute method of
        RPCRequest. Also, if in the arguments we have a field
        named "binary_data", we send it separatedly as a binary
        attachment after the JSON encoded message.

        method (string): the name of the method to call.
        data (object): the object to pass to the remote method.
        callback (function): method to call with the RPC response.
        plus (object): additional object to be passed to the callback.
        bind_obj (object): context for the callback (None means the
                           local service).

        """
        logger.debug("RemoteService.execute_rpc")
        if not self.connected:
            self.connect_remote_service()
            if not self.connected:
                if self.sync:
                    raise SyncRPCError("Couldn't connect to remote service")
                else:
                    return False
        if bind_obj == None:
            bind_obj = self.service
        message = {}
        message["__method"] = method
        message["__data"] = data
        if self.sync:
            bind_obj = None
            plus = random_string(16)
            callback = self.execute_rpc_callback
        request = RPCRequest(message, bind_obj, callback, plus)
        message = request.pre_execute()
        if "binary_data" not in data:
            try:
                json_message = encode_json(message)
                json_length = encode_length(len(json_message))
                binary_message = ""
            except ValueError:
                logger.error(("Cannot send request of method %s because of " +
                             "encoding error.") % method)
                request.complete(None)
                return
        else:
            try:
                binary_data = data["binary_data"]
                del data["binary_data"]
                json_message = encode_json(message)
                json_length = encode_length(len(json_message))
                binary_message = encode_binary(binary_data)
            except ValueError:
                logger.error(("Cannot send request of method %s because of " +
                             "encoding error.") % method)
                request.complete(None)
                return
        self._push_right(json_length + json_message + binary_message)
        if self.sync:
            while not plus in self.sync_responses:
                asyncore.loop(0.02, True, None, 1)
            (response, error) = self.sync_responses[plus]
            del self.sync_responses[plus]
            if error is not None:
                raise SyncRPCError(error)
            return response
        return True

    @rpc_callback
    def execute_rpc_callback(self, data, plus, error=None):
        """If the connection is synchronous, we use this callback that
        collects the response and signal to the waiting execute_rpc
        that the rpc ended and we can return. Note that plus is lost,
        but if calls are synchronous, plus is useless anyway.

        data (object): response of the rpc.
        plus (string): plus object of the call, the random_id assigned
                       by execute_rpc
        error (string): errors from the callee.

        """
        self.sync_responses[plus] = (data, error)

    def __getattr__(self, method):
        """Syntactic sugar to call a remote method without using
        execute_rpc. If the local service ask for something that is
        not present, we assume that it is a remote RPC method.

        method (string): the method to call.

        """
        logger.debug("RemoteService.__getattr__(%s)" % method)

        def remote_method(callback=None,
                          plus=None,
                          bind_obj=None,
                          **data):
            """Call execute_rpc with the given method name.

            """
            return self.execute_rpc(method, data,
                                    callback, plus, bind_obj)
        return remote_method

    def _push_right(self, data):
        """Send a request or a response with the right terminator in
        the end.

        data (string): the data to send.

        """
        logger.debug("RemoteService._push_right")
        to_push = "".join(data) + "\r\n"
        self.push(to_push)

    def handle_error(self):
        """Handle a generic error in the communication.

        """
        logger.debug("RemoteService.handle_error")
        self.handle_close()
        raise

    def handle_close(self):
        """Handle the case when the connection fall.

        """
        logger.debug("RemoteService.handle_close")
        self.close()
        self.connected = False

    def connect_remote_service(self):
        """Try to connect to the remote service.

        """
        logger.debug("RemoteService.connect_remote_service")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(self.address)
        except:
            return
        else:
            self.connected = True
            self._initialize_channel(sock)


class ListeningSocket(asyncore.dispatcher):
    """This class starts a listening socket. It is needed by a Service
    that wants to be able to receive RPC requests.

    """

    def __init__(self, service, address):
        """This creates a listening socket for the service at the
        specified address.

        service (Service): this socket listens for this service.
        address (Address): the address to listen at.

        """
        logger.debug("ListeningSocket.__init__")
        asyncore.dispatcher.__init__(self)
        self._service = service
        self._address = address

        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.bind(("", self._address.port))
        self.listen(5)

    def handle_accept(self):
        """Handle a connection request. It creates a RemoteService to
        manage the connection.

        """
        logger.debug("ListeningSocket.handle_accept")
        try:
            connection, address = self.accept()
        except socket.error:
            logger.error("Error: %s %s" % (sys.exc_info()[:2]))
            return
        try:
            ipaddr, port = socket.getnameinfo(address, socket.NI_NOFQDN)
            address = Address(ipaddr, int(port))
        except:
            logger.error("Error: %s %s" % (sys.exc_info()[:2]))
            return
        remote_service = RemoteService(self._service,
                                       address=address)
        remote_service._initialize_channel(connection)
        self.connected = True

    def handle_close(self):
        """Handle when the connection falls.

        """
        logger.debug("ListeningSocket.handle_close")


class Logger:
    """Utility class to connect to the remote log service and to
    store/display locally and remotely log messages.

    """


    def __init__(self):
        Logger.CRITICAL = "CRITICAL"
        Logger.ERROR    = "ERROR   "
        Logger.WARNING  = "WARNING "
        Logger.INFO     = "INFO    "
        Logger.DEBUG    = "DEBUG   "

        Logger.TO_STORE = [
            Logger.CRITICAL,
            Logger.ERROR,
            Logger.WARNING,
            Logger.INFO,
            Logger.DEBUG,
            ]
        Logger.TO_DISPLAY = [
            Logger.CRITICAL,
            Logger.ERROR,
            Logger.WARNING,
            Logger.INFO,
            Logger.DEBUG
            ]
        Logger.TO_SEND = [
            Logger.CRITICAL,
            Logger.ERROR,
            Logger.WARNING,
            Logger.INFO,
            ]

        self._log_service = RemoteService(None,
                                          ServiceCoord("LogService", 0))
        self.operation = ""

    def initialize(self, service):
        """To be set by the service we are currently running.

        service (ServiceCoord): the service that we are running

        """
        self._my_coord = service
        mkdir("logs")
        self._log_file = codecs.open(\
            os.path.join("logs", "%d-%s-%d.local-log" %
                         (time.time(), service.name, service.shard)),
            "w", "utf-8")


    def log(self, msg, operation=None, severity=None, timestamp=None):
        """Record locally a log message and tries to send it to the
        log service.

        msg (string): the message to log
        operation (string): a high-level description of the long-term
                            operation that is going on in the service
        severity (string): a constant defined in Logger
        timestamp (float): seconds from epoch

        """
        if severity is None:
            severity = Logger.INFO
        if timestamp is None:
            timestamp = time.time()
        if operation is None:
            operation = self.operation

        log = self.format_log(msg, operation, severity, timestamp)

        if severity in Logger.TO_DISPLAY:
            print log
        if severity in Logger.TO_STORE:
            print >> self._log_file, log
        if severity in Logger.TO_SEND:
            self._log_service.Log(msg=log)

    def debug(self, msg, operation="", timestamp=None):
        """Syntactic sugar.

        """
        return self.log(msg, operation, Logger.DEBUG, timestamp)

    def info(self, msg, operation="", timestamp=None):
        """Syntactic sugar.

        """
        return self.log(msg, operation, Logger.INFO, timestamp)

    def warning(self, msg, operation="", timestamp=None):
        """Syntactic sugar.

        """
        return self.log(msg, operation, Logger.WARNING, timestamp)

    def error(self, msg, operation="", timestamp=None):
        """Syntactic sugar.

        """
        return self.log(msg, operation, Logger.ERROR, timestamp)

    def critical(self, msg, operation="", timestamp=None):
        """Syntactic sugar.

        """
        return self.log(msg, operation, Logger.CRITICAL, timestamp)

    def format_log(self, msg, operation, severity, timestamp):
        """Format a log message in a common way (for local and remote
        logging).

        msg (string): the message to log
        operation (string): a high-level description of the long-term
                            operation that is going on in the service
        severity (string): a constant defined in Logger
        timestamp (float): seconds from epoch
        returns (string): the formatted log

        """
        d = datetime.datetime.fromtimestamp(timestamp)
        service_full = repr(self._my_coord)
        if operation != "":
            service_full += "/%s" % (operation)
        return "%s - %s [%s] %s" % ('{0:%Y/%m/%d %H:%M:%S}'.format(d),
                                    severity, service_full, msg)


logger = Logger()


def sync_call(function, args,
              callback=None, plus=None, bind_obj=None,
              sync=False):
    if sync:
        plus = {'finished': False,
                'data': None,
                'error':None}

        @rpc_callback
        def sync_callback(context, data, plus, error=None):
            logger.debug("sync_callback: callback for sync function received")
            plus['data'] = data
            plus['error'] = error
            plus['finished'] = True

        function(callback=sync_callback,
                 plus=plus,
                 bind_obj=None,
                 **args)
        while not plus['finished']:
            asyncore.loop(0.02, True, None, 1)

        error = plus['error']
        data = plus['data']
        if error is not None:
            raise SyncRPCError(error)
        else:
            return data

    else:
        return function(callback=callback,
                        plus=plus,
                        bind_obj=bind_obj,
                        **args)
