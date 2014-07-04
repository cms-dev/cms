#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""Tests for RPC system.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import gevent
import gevent.socket
import gevent.event
from gevent.server import StreamServer

from mock import Mock, patch

from cms import Address, ServiceCoord
from cms.io import RPCError, rpc_method, RemoteServiceServer, \
    RemoteServiceClient


class MockService(object):
    def not_rpc_callable(self):
        pass

    @rpc_method
    def raise_exception(self):
        raise RuntimeError()

    @rpc_method
    def return_unencodable(self):
        return RuntimeError()

    @rpc_method
    def echo(self, value):
        return value

    @rpc_method
    def echo_slow(self, value):
        gevent.sleep(0.01)
        return value

    @rpc_method
    def infinite(self):
        event = gevent.event.Event()
        event.wait()


class TestRPC(unittest.TestCase):

    def setUp(self):
        patcher = patch("cms.io.rpc.get_service_address")
        self.mock = patcher.start()
        self.addCleanup(patcher.stop)

        self.service = MockService()
        self.servers = list()
        self.clients = list()
        self.spawn_listener()

    def spawn_listener(self, host="127.0.0.1", port=0):
        """Start listening on the given host and port.

        Each incoming connection will cause a RemoteServiceServer to be
        instantiated (and therefore a greenlet to be spawned) and to be
        inserted in self.servers. The listening host and port will also
        be stored as self.host and self.port.

        host (string): the hostname or IP address
        port (int): the port (0 causes any available port to be chosen)

        """
        self._server = StreamServer((host, port), self.get_server)
        self._server.start()
        self.host = self._server.server_host
        self.port = self._server.server_port
        self.mock.return_value = Address(self.host, self.port)

    def kill_listener(self):
        """Stop listening."""
        self._server.stop()
        del self._server
        # We leave self.host and self.port.

    def get_server(self, socket_, address):
        """Obtain a new RemoteServiceServer to handle a new connection.

        Instantiate a RemoteServiceServer, spawn its greenlet and add
        it to self.servers. It will listen on the given socket, that
        represents a connection opened by a remote host at the given
        address.

        socket_ (socket): the socket to use
        address (tuple): the (ip address, port) of the remote part
        return (RemoteServiceServer): a server

        """
        server = RemoteServiceServer(self.service, address)
        server.handle(socket_)
        self.servers.append(server)
        return server

    def get_client(self, coord, auto_retry=None):
        """Obtain a new RemoteServiceClient to connect to a server.

        Instantiate a RemoteServiceClient, spawn its greenlet and add
        it to self.clients. It will try to connect to the service at
        the given coordinates.

        coord (ServiceCoord): the (name, shard) of the service
        auto_retry (float|None): how long to wait after a disconnection
            before trying to reconnect
        return (RemoteServiceClient): a client

        """
        client = RemoteServiceClient(coord, auto_retry)
        client.connect()
        self.clients.append(client)
        return client

    def disconnect_servers(self):
        """Disconnect all registered servers from their clients."""
        for server in self.servers:
            if server.connected:
                server.disconnect()

    def disconnect_clients(self):
        """Disconnect all registered clients from their servers."""
        for client in self.clients:
            if client.connected:
                client.disconnect()

    def tearDown(self):
        self.kill_listener()
        self.disconnect_clients()
        self.disconnect_servers()
        gevent.sleep(0.002)

    def test_method_not_existent(self):
        client = self.get_client(ServiceCoord("Foo", 0))
        result = client.not_existent()
        result.wait()
        self.assertFalse(result.successful())
        self.assertIsInstance(result.exception, RPCError)

    def test_method_not_rpc_callable(self):
        client = self.get_client(ServiceCoord("Foo", 0))
        result = client.not_rpc_callable()
        result.wait()
        self.assertFalse(result.successful())
        self.assertIsInstance(result.exception, RPCError)

    def test_method_raise_exception(self):
        client = self.get_client(ServiceCoord("Foo", 0))
        result = client.raise_exception()
        result.wait()
        self.assertFalse(result.successful())
        self.assertIsInstance(result.exception, RPCError)

    def test_method_send_unencodable(self):
        client = self.get_client(ServiceCoord("Foo", 0))
        result = client.echo(value=RuntimeError())
        result.wait()
        self.assertFalse(result.successful())
        self.assertIsInstance(result.exception, RPCError)

    # TODO Are we sure we want this to be the correct behavior? That
    # means that if the server (by mistake?) sends unencodable data
    # then the client will never get any data nor any error. It will
    # get stuck until it goes in timeout.
    def test_method_return_unencodable(self):
        client = self.get_client(ServiceCoord("Foo", 0))
        result = client.return_unencodable()
        result.wait(timeout=0.002)
        self.assertFalse(result.ready())

    def test_method_return_bool(self):
        client = self.get_client(ServiceCoord("Foo", 0))
        result = client.echo(value=True)
        result.wait()
        self.assertTrue(result.successful())
        self.assertIs(result.value, True)

    def test_method_return_int(self):
        client = self.get_client(ServiceCoord("Foo", 0))
        result = client.echo(value=42)
        result.wait()
        self.assertTrue(result.successful())
        self.assertEqual(result.value, 42)

    def test_method_return_string(self):
        client = self.get_client(ServiceCoord("Foo", 0))
        result = client.echo(value="Hello World")
        result.wait()
        self.assertTrue(result.successful())
        self.assertEqual(result.value, "Hello World")

    def test_method_return_list(self):
        client = self.get_client(ServiceCoord("Foo", 0))
        result = client.echo(value=["Hello", 42, "World"])
        result.wait()
        self.assertTrue(result.successful())
        self.assertEqual(result.value, ["Hello", 42, "World"])

    def test_autoreconnect1(self):
        client = self.get_client(ServiceCoord("Foo", 0), 0.002)
        gevent.sleep(0.002)
        self.assertTrue(client.connected)
        self.disconnect_servers()
        gevent.sleep(0.002)
        self.assertTrue(client.connected, "Autoreconnect didn't kick in "
                                          "after server disconnected")

    def test_autoreconnect2(self):
        client = self.get_client(ServiceCoord("Foo", 0), 0.002)
        gevent.sleep(0.002)
        self.assertTrue(client.connected)
        self.disconnect_servers()
        self.kill_listener()
        gevent.sleep(0.002)
        self.assertFalse(client.connected)
        self.spawn_listener(port=self.port)
        gevent.sleep(0.002)
        self.assertTrue(client.connected, "Autoreconnect didn't kick in "
                                          "after server came back online")

    def test_autoreconnect3(self):
        client = self.get_client(ServiceCoord("Foo", 0), 0.002)
        gevent.sleep(0.002)
        self.assertTrue(client.connected)
        self.disconnect_clients()
        gevent.sleep(0.002)
        self.assertFalse(client.connected, "Autoreconnect still active "
                                           "after explicit disconnection")

    def test_concurrency(self):
        client = self.get_client(ServiceCoord("Foo", 0))
        result1 = client.infinite()
        gevent.sleep(0.002)
        result2 = client.echo(value=True)
        gevent.sleep(0.002)
        self.assertTrue(result2.successful())
        self.assertIs(result2.value, True)
        self.assertFalse(result1.ready())
        self.disconnect_clients()
        self.assertTrue(result1.ready())
        self.assertFalse(result1.successful())
        self.assertIsInstance(result1.exception, RPCError)

    def test_callbacks(self):
        coord = ServiceCoord("Foo", 0)
        client = self.get_client(coord)
        gevent.sleep(0.002)
        client.disconnect()
        on_connect_handler = Mock()
        client.add_on_connect_handler(on_connect_handler)
        on_disconnect_handler = Mock()
        client.add_on_disconnect_handler(on_disconnect_handler)

        client.connect()
        gevent.sleep(0.002)
        self.assertTrue(client.connected)
        on_connect_handler.assert_called_once_with(coord)
        on_connect_handler.reset_mock()
        self.assertFalse(on_disconnect_handler.called)

        client.disconnect()
        gevent.sleep(0.002)
        self.assertFalse(client.connected)
        self.assertFalse(on_connect_handler.called)
        on_disconnect_handler.assert_called_once_with()
        on_disconnect_handler.reset_mock()

        client.connect()
        gevent.sleep(0.002)
        self.assertTrue(client.connected)
        on_connect_handler.assert_called_once_with(coord)
        on_connect_handler.reset_mock()
        self.assertFalse(on_disconnect_handler.called)

        self.disconnect_servers()
        gevent.sleep(0.1)
        self.assertFalse(client.connected)
        self.assertFalse(on_connect_handler.called)
        on_disconnect_handler.assert_called_once_with()
        on_disconnect_handler.reset_mock()

    def test_reusability(self):
        client = self.get_client(ServiceCoord("Foo", 0))

        on_connect_handler = Mock()
        client.add_on_connect_handler(on_connect_handler)
        on_disconnect_handler = Mock()
        client.add_on_disconnect_handler(on_disconnect_handler)

        for i in range(10):
            self.assertTrue(client.connected)
            result = client.echo(value=42)
            result.wait()
            self.assertTrue(result.successful())
            self.assertEqual(result.value, 42)
            self.assertTrue(client.connected)

            gevent.sleep(0.002)
            client.disconnect()
            self.assertFalse(client.connected)
            gevent.sleep(0.002)
            client.connect()
            self.assertTrue(client.connected)

        gevent.sleep(0.002)

        self.assertEqual(on_connect_handler.call_count, 10)
        self.assertEqual(on_disconnect_handler.call_count, 10)

    def test_double_connect_client(self):
        # Check that asking an already-connected client to connect
        # again causes an error.
        client = self.get_client(ServiceCoord("Foo", 0))
        self.assertRaises(Exception, client.connect)

    def test_double_connect_server(self):
        # Check that asking an already-connected server to initialize
        # again its connection causes an error.
        client = self.get_client(ServiceCoord("Foo", 0))
        gevent.sleep(0.002)
        self.assertRaises(Exception, self.servers[0].initialize, "foo")

    def test_double_disconnect_client(self):
        # Check that asking a non-connected client to disconnect is
        # harmless (i.e. disconnection is idempotent).
        client = self.get_client(ServiceCoord("Foo", 0))
        client.disconnect()
        gevent.sleep(0.002)
        client.disconnect()
        gevent.sleep(0.002)

    def test_double_disconnect_server(self):
        # Check that asking a non-connected server to disconnect is
        # harmless (i.e. disconnection is idempotent).
        client = self.get_client(ServiceCoord("Foo", 0))
        gevent.sleep(0.002)
        self.servers[0].disconnect()
        gevent.sleep(0.002)
        self.servers[0].disconnect()
        gevent.sleep(0.002)

    def test_send_invalid_json(self):
        sock = gevent.socket.create_connection((self.host, self.port))
        sock.sendall("foo\r\n")
        gevent.sleep(0.002)
        self.assertTrue(self.servers[0].connected)
        # Verify the server resumes normal operation.
        self.test_method_return_int()

    def test_send_incomplete_json(self):
        sock = gevent.socket.create_connection((self.host, self.port))
        sock.sendall('{"__id": "foo"}\r\n')
        gevent.sleep(0.002)
        self.assertTrue(self.servers[0].connected)
        # Verify the server resumes normal operation.
        self.test_method_return_int()


if __name__ == "__main__":
    unittest.main()
