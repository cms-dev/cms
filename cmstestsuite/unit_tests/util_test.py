#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2014 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2020 Andrey Vihrov <andrey.vihrov@gmail.com>
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

"""Tests for general utility functions."""

import netifaces
import os
import tempfile
import unittest
from unittest.mock import Mock
from cms.conf import EphemeralServiceConfig

import cms.util
from cms import Address, ServiceCoord, \
    get_safe_shard, get_service_address, get_service_shards, rmtree


class FakeAsyncConfig:
    """Fake class for the configuration of service addresses."""
    core_services = {
        ServiceCoord("Service", 0): Address("0.0.0.0", 0),
        ServiceCoord("Service", 1): Address("0.0.0.1", 1),
    }
    other_services = {}
    ephemeral_services = {"Service":
                          EphemeralServiceConfig("1.0.0.0/8", 1, 1000)}


def _set_up_async_config(restore=False):
    """Fake the async config."""
    if not restore:
        if not hasattr(_set_up_async_config, "original"):
            _set_up_async_config.original = cms.util.async_config
        cms.util.async_config = FakeAsyncConfig()
    else:
        cms.util.async_config = _set_up_async_config.original


def _set_up_ip_addresses(addresses=None, restore=False):
    """Instruct the netifaces module to return the specific ips."""
    if not restore:
        if not hasattr(_set_up_ip_addresses, "original"):
            _set_up_ip_addresses.original = \
                (netifaces.interfaces, netifaces.ifaddresses)
        dict_addresses = {
            netifaces.AF_INET: [{"addr": address} for address in addresses]}
        netifaces.interfaces = Mock(return_value="eth0")
        netifaces.ifaddresses = Mock(return_value=dict_addresses)
    else:
        netifaces.interfaces, netifaces.ifaddresses = \
            _set_up_ip_addresses.original


class TestGetSafeShard(unittest.TestCase):
    """Test the function cms.util.get_safe_shard."""

    def setUp(self):
        """Set up the default mocks."""
        _set_up_async_config()
        _set_up_ip_addresses(["1.1.1.1", "0.0.0.1"])

    def tearDown(self):
        """Restore the mocks to ensure normal operations."""
        _set_up_async_config(restore=True)
        _set_up_ip_addresses(restore=True)

    def test_success(self):
        """Test success cases.

        This tests for both giving explicitly the shard number, and
        for autodetecting it.

        """
        self.assertEqual(get_safe_shard("Service", 0), 0)
        self.assertEqual(get_safe_shard("Service", 1), 1)
        self.assertEqual(get_safe_shard("Service", None), 1)

    def test_shard_not_present(self):
        """Test failure when the given shard is not in the config."""
        with self.assertRaises(ValueError):
            get_safe_shard("Service", 2)

    def test_service_not_present(self):
        """Test failure when the given service is not in the config."""
        with self.assertRaises(ValueError):
            get_safe_shard("ServiceNotPresent", 0)

    def test_no_autodetect(self):
        """Test failure when no shard is given and autodetect fails."""
        # Setting up non-matching IPs.
        _set_up_ip_addresses(["1.1.1.1", "0.0.0.2"])
        with self.assertRaises(ValueError):
            get_safe_shard("Service", None)


class TestGetServiceAddress(unittest.TestCase):
    """Test the function cms.util.get_service_address.

    """

    def setUp(self):
        """Set up the default mocks."""
        _set_up_async_config()

    def tearDown(self):
        """Restore the mocks to ensure normal operations."""
        _set_up_async_config(restore=True)

    def test_success(self):
        """Test success cases."""
        self.assertEqual(
            get_service_address(ServiceCoord("Service", 0)),
            Address("0.0.0.0", 0))
        self.assertEqual(
            get_service_address(ServiceCoord("Service", 1)),
            Address("0.0.0.1", 1))

    def test_shard_not_present(self):
        """Test failure when the shard of the service is invalid."""
        with self.assertRaises(ValueError):
            get_service_address(ServiceCoord("Service", 2))

    def test_service_not_present(self):
        """Test failure when the service is invalid."""
        with self.assertRaises(KeyError):
            get_service_address(ServiceCoord("ServiceNotPresent", 0))

    def test_ephemeral(self):
        """Test ephemeral service case."""
        self.assertEqual(get_service_address(ServiceCoord(
            "Service", EphemeralServiceConfig.EPHEMERAL_SHARD_OFFSET + 1000)), Address("1.0.0.1", 1))


class TestGetServiceShards(unittest.TestCase):
    """Test the function cms.util.get_service_shards.

    """

    def setUp(self):
        """Set up the default mocks."""
        _set_up_async_config()

    def tearDown(self):
        """Restore the mocks to ensure normal operations."""
        _set_up_async_config(restore=True)

    def test_success(self):
        """Test success cases."""
        self.assertEqual(get_service_shards("Service"), 2)
        self.assertEqual(get_service_shards("ServiceNotPresent"), 0)


class TestRmtree(unittest.TestCase):
    """Test the function cms.util.rmtree.

    """

    def setUp(self):
        """Set up temporary directory."""
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        """Remove temporary directory."""
        os.rmdir(self.tmpdir)

    def test_success(self):
        """Test success case."""
        testdir = os.path.join(self.tmpdir, "test")
        os.makedirs(os.path.join(testdir, "a"))
        os.makedirs(os.path.join(testdir, "b", "c"))
        open(os.path.join(testdir, "x"), "w").close()
        os.symlink("foo", os.path.join(testdir, "a", "y"))
        os.symlink(self.tmpdir, os.path.join(testdir, "b", "z"))

        rmtree(testdir)
        self.assertFalse(os.path.exists(testdir))
        self.assertTrue(os.path.isdir(self.tmpdir))

    def test_symlink(self):
        """Test failure on a symlink."""
        link = os.path.join(self.tmpdir, "link")
        os.symlink(self.tmpdir, link)

        with self.assertRaises(NotADirectoryError):
            rmtree(link)

        os.remove(link)

    def test_missing(self):
        """Test failure on a missing directory."""
        with self.assertRaises(FileNotFoundError):
            rmtree(os.path.join(self.tmpdir, "missing"))


if __name__ == "__main__":
    unittest.main()
