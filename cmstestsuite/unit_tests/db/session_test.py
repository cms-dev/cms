#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""Tests for session.py."""

import unittest
from unittest.mock import patch

from cms import config
from cms.db.session import custom_psycopg2_connection


def _patch_db(s):
    """Patch the db connection string in the configuration"""
    return patch.object(config, "database", s)


@patch("psycopg2.connect")
class TestCustomPsycopg2Connect(unittest.TestCase):
    """Tests for the function custom_psycopg2_connect."""

    def test_network(self, connect):
        # Simple TCP connection.
        with _patch_db("postgresql+psycopg2://usrn:pwd@hooost:5433/dbname"):
            r = custom_psycopg2_connection()
            self.assertIs(r, connect.return_value)
            connect.assert_called_once_with(
                host="hooost",
                port=5433,
                user="usrn",
                password="pwd",
                database="dbname")

    def test_network_missing_port(self, connect):
        # If port is missing, the default 5432 is used.
        with _patch_db("postgresql+psycopg2://usrn:pwd@hooost/dbname"):
            r = custom_psycopg2_connection()
            self.assertIs(r, connect.return_value)
            connect.assert_called_once_with(
                host="hooost",
                port=5432,
                user="usrn",
                password="pwd",
                database="dbname")

    def test_unix_domain_socket(self, connect):
        with _patch_db("postgresql+psycopg2://usrn:pwd@/dbname"):
            r = custom_psycopg2_connection()
            self.assertIs(r, connect.return_value)
            connect.assert_called_once_with(
                host=None,
                port=None,
                user="usrn",
                password="pwd",
                database="dbname")

    def test_unix_domain_socket_custom_dir(self, connect):
        with _patch_db("postgresql+psycopg2://"
                       "usrn:pwd@/dbname?host=/var/postgresql"):
            r = custom_psycopg2_connection()
            self.assertIs(r, connect.return_value)
            connect.assert_called_once_with(
                host="/var/postgresql",
                port=None,
                user="usrn",
                password="pwd",
                database="dbname")

    def test_missing_password(self, connect):
        with _patch_db("postgresql+psycopg2://u@h:1/db"):
            r = custom_psycopg2_connection()
            self.assertIs(r, connect.return_value)
            connect.assert_called_once_with(
                host="h",
                port=1,
                user="u",
                password=None,
                database="db")

    def test_not_psycopg2(self, connect):
        with _patch_db("sqlite://file"):
            with self.assertRaises(AssertionError):
                custom_psycopg2_connection()


if __name__ == "__main__":
    unittest.main()
