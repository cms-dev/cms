#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2014-2017 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2015 Stefano Maggiolo <s.maggiolo@gmail.com>
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

import unittest
from unittest.mock import Mock, patch

import gevent
import gevent.event
import gevent.socket
from gevent.server import StreamServer

from cms import Address, ServiceCoord
from cms.io import RPCError, rpc_method, RemoteServiceServer, \
    RemoteServiceClient


class MockService:
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
        self._server = StreamServer((host, port), self.handle_new_connection)
        self._server.start()
        self.host = self._server.server_host
        self.port = self._server.server_port
        self.mock.return_value = Address(self.host, self.port)

    def kill_listener(self):
        """Stop listening."""
        # Some code may kill the listener in the middle of a test, and
        # plan to spawn a new one afterwards. Yet if the test fails
        # then upon tearDown _server will still be unset.
        if hasattr(self, "_server"):
            self._server.stop()
            del self._server
        # We leave self.host and self.port.

    def handle_new_connection(self, socket_, address):
        """Create a new RemoteServiceServer to handle a new connection.

        Instantiate a RemoteServiceServer, add it to self.servers and
        have it listen on the given socket (which is for a connection
        opened by a remote host from the given address). This method
        will block until the socket gets closed.

        socket_ (socket): the socket to use
        address (tuple): the (ip address, port) of the remote part

        """
        server = RemoteServiceServer(self.service, address)
        self.servers.append(server)
        server.handle(socket_)

    def get_client(self, coord, block=True, auto_retry=None):
        """Obtain a new RemoteServiceClient to connect to a server.

        Instantiate a RemoteServiceClient, spawn its greenlet and add
        it to self.clients. It will try to connect to the service at
        the given coordinates.

        coord (ServiceCoord): the (name, shard) of the service
        block (bool): whether to wait for the connection to be
            established before returning
        auto_retry (float|None): how long to wait after a disconnection
            before trying to reconnect
        return (RemoteServiceClient): a client

        """
        client = RemoteServiceClient(coord, auto_retry)
        client.connect()
        if block:
            client._connection_event.wait()
        self.clients.append(client)
        return client

    def disconnect_servers(self):
        """Disconnect all registered servers from their clients."""
        servers = self.servers.copy()
        for server in servers:
            if server.connected:
                server.disconnect()

    def disconnect_clients(self):
        """Disconnect all registered clients from their servers."""
        clients = self.clients.copy()
        for client in clients:
            if client.connected:
                client.disconnect()

    @staticmethod
    def sleep():
        """Pause the greenlet so other work can be done."""
        gevent.sleep(0.005)

    def tearDown(self):
        self.kill_listener()
        self.disconnect_clients()
        self.disconnect_servers()
        self.sleep()

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

    @patch("cms.io.rpc.gevent.socket.socket")
    def test_background_connect(self, socket_mock):
        # Patch the connect method of sockets so that it blocks until
        # we set the done_event (we will do so at the end of the test).
        connect_mock = socket_mock.return_value.connect
        done_event = gevent.event.Event()
        connect_mock.side_effect = lambda _: done_event.wait()
        # Connect to the RPC server in non-blocking mode and make sure
        # that we indeed don't block (i.e., take more than 0.001s).
        with gevent.Timeout(0.001) as timeout:
            try:
                client = self.get_client(ServiceCoord("Foo", 0), block=False)
            except gevent.Timeout as t:
                if t is not timeout:
                    raise
                self.fail("Connecting blocks")
        # As socket.connect() never returned, the RPC client cannot have
        # connected.
        self.assertFalse(client.connected)
        # Unblock the socket's connect method and make sure it actually
        # got called (otherwise this whole tests is pointless). Also,
        # yield to other greenlets so that they can be awoken after the
        # event triggered.
        done_event.set()
        gevent.sleep()
        connect_mock.assert_called_once_with(Address(self.host, self.port))

    def test_autoreconnect1(self):
        client = self.get_client(ServiceCoord("Foo", 0), auto_retry=0.002)
        self.sleep()
        self.assertTrue(client.connected)
        self.disconnect_servers()
        gevent.sleep(0.1)
        self.assertTrue(client.connected,
                        "Autoreconnect didn't kick in "
                        "after server disconnected")

    def test_autoreconnect2(self):
        client = self.get_client(ServiceCoord("Foo", 0), auto_retry=0.002)
        self.sleep()
        self.assertTrue(client.connected)
        self.disconnect_servers()
        self.kill_listener()
        self.sleep()
        self.assertFalse(client.connected)
        self.spawn_listener(port=self.port)
        self.sleep()
        self.assertTrue(client.connected, "Autoreconnect didn't kick in "
                                          "after server came back online")

    def test_autoreconnect3(self):
        client = self.get_client(ServiceCoord("Foo", 0), auto_retry=0.002)
        self.sleep()
        self.assertTrue(client.connected)
        self.disconnect_clients()
        self.sleep()
        self.assertFalse(client.connected, "Autoreconnect still active "
                                           "after explicit disconnection")

    def test_concurrency(self):
        client = self.get_client(ServiceCoord("Foo", 0))
        result1 = client.infinite()
        self.sleep()
        result2 = client.echo(value=True)
        self.sleep()
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
        self.sleep()
        client.disconnect()
        on_connect_handler = Mock()
        client.add_on_connect_handler(on_connect_handler)
        on_disconnect_handler = Mock()
        client.add_on_disconnect_handler(on_disconnect_handler)

        client.connect()
        self.sleep()
        self.assertTrue(client.connected)
        on_connect_handler.assert_called_once_with(coord)
        on_connect_handler.reset_mock()
        self.assertFalse(on_disconnect_handler.called)

        client.disconnect()
        self.sleep()
        self.assertFalse(client.connected)
        self.assertFalse(on_connect_handler.called)
        on_disconnect_handler.assert_called_once_with()
        on_disconnect_handler.reset_mock()

        client.connect()
        self.sleep()
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

            self.sleep()
            client.disconnect()
            self.assertFalse(client.connected)
            self.sleep()
            client.connect()
            client._connection_event.wait()
            self.assertTrue(client.connected)

        self.sleep()

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
        self.get_client(ServiceCoord("Foo", 0))
        self.sleep()
        self.assertRaises(Exception, self.servers[0].initialize, "foo")

    def test_double_disconnect_client(self):
        # Check that asking a non-connected client to disconnect is
        # harmless (i.e. disconnection is idempotent).
        client = self.get_client(ServiceCoord("Foo", 0))
        client.disconnect()
        self.sleep()
        client.disconnect()
        self.sleep()

    def test_double_disconnect_server(self):
        # Check that asking a non-connected server to disconnect is
        # harmless (i.e. disconnection is idempotent).
        self.get_client(ServiceCoord("Foo", 0))
        self.sleep()
        self.servers[0].disconnect()
        self.sleep()
        self.servers[0].disconnect()
        self.sleep()

    def test_send_invalid_json(self):
        sock = gevent.socket.create_connection((self.host, self.port))
        sock.sendall(b"foo\r\n")
        self.sleep()
        # Malformed messages cause the connection to be closed.
        self.assertFalse(self.servers[0].connected)
        sock.close()

    def test_send_incomplete_json(self):
        sock = gevent.socket.create_connection((self.host, self.port))
        sock.sendall(b'{"__id": "foo"}\r\n')
        self.sleep()
        # Malformed messages cause the connection to be closed.
        self.assertFalse(self.servers[0].connected)
        sock.close()


if __name__ == "__main__":
    unittest.main()
