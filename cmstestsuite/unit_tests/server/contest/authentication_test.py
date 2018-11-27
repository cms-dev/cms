#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""Tests for authentication functions.

"""

import ipaddress
import unittest
from datetime import timedelta
from unittest.mock import patch

# Needs to be first to allow for monkey patching the DB connection string.
from cmstestsuite.unit_tests.databasemixin import DatabaseMixin

from cms import config
from cms.server.contest.authentication import validate_login, \
    authenticate_request
# Prefer build_password (which defaults to a plaintext method) over
# hash_password (which defaults to bcrypt) as it is a lot faster.
from cmscommon.crypto import build_password, hash_password
from cmscommon.datetime import make_datetime


class TestValidateLogin(DatabaseMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.timestamp = make_datetime()
        self.add_contest()
        self.contest = self.add_contest(allow_password_authentication=True)
        self.add_user(username="otheruser")
        self.user = self.add_user(
            username="myuser", password=build_password("mypass"))
        self.participation = self.add_participation(
            contest=self.contest, user=self.user)

    def assertSuccess(self, username, password, ip_address):
        # We had an issue where due to a misuse of contains_eager we ended up
        # with the wrong user attached to the participation. This only happens
        # if the correct user isn't already in the identity map, which is what
        # these lines trigger.
        self.session.flush()
        self.session.expire(self.user)
        self.session.expire(self.contest)

        authenticated_participation, cookie = validate_login(
            self.session, self.contest, self.timestamp,
            username, password, ipaddress.ip_address(ip_address))

        self.assertIsNotNone(authenticated_participation)
        self.assertIsNotNone(cookie)
        self.assertIs(authenticated_participation, self.participation)
        self.assertIs(authenticated_participation.user, self.user)
        self.assertIs(authenticated_participation.contest, self.contest)

    def assertFailure(self, username, password, ip_address):
        authenticated_participation, cookie = validate_login(
            self.session, self.contest, self.timestamp,
            username, password, ipaddress.ip_address(ip_address))

        self.assertIsNone(authenticated_participation)
        self.assertIsNone(cookie)

    def test_successful_login(self):
        self.assertSuccess("myuser", "mypass", "127.0.0.1")

    def test_no_user(self):
        self.assertFailure("myotheruser", "mypass", "127.0.0.1")

    def test_no_participation_for_user_in_contest(self):
        other_contest = self.add_contest(allow_password_authentication=True)
        other_user = self.add_user(
            username="myotheruser", password=build_password("mypass"))
        self.add_participation(contest=other_contest, user=other_user)

        self.assertFailure("myotheruser", "mypass", "127.0.0.1")

    def test_participation_specific_password(self):
        self.participation.password = build_password("myotherpass")

        self.assertFailure("myuser", "mypass", "127.0.0.1")
        self.assertSuccess("myuser", "myotherpass", "127.0.0.1")

    def test_unallowed_password_authentication(self):
        self.contest.allow_password_authentication = False

        self.assertFailure("myuser", "mypass", "127.0.0.1")

    def test_unallowed_hidden_participation(self):
        self.contest.block_hidden_participations = True
        self.participation.hidden = True

        self.assertFailure("myuser", "mypass", "127.0.0.1")

    def test_invalid_password_stored_in_user(self):
        # It's invalid, as it's not created by build_password.
        self.user.password = "mypass"

        # Mainly checks that no exception is raised.
        self.assertFailure("myuser", "mypass", "127.0.0.1")

    def test_invalid_password_stored_in_participation(self):
        # It's invalid, as it's not created by build_password.
        self.participation.password = "myotherpass"

        # Mainly checks that no exception is raised.
        self.assertFailure("myuser", "myotherpass", "127.0.0.1")

    def test_ip_lock(self):
        self.contest.ip_restriction = True
        self.participation.ip = [ipaddress.ip_network("10.0.0.0/24")]

        self.assertSuccess("myuser", "mypass", "10.0.0.1")
        self.assertFailure("myuser", "wrongpass", "10.0.0.1")
        self.assertFailure("myuser", "mypass", "10.0.1.1")

        self.participation.ip = [ipaddress.ip_network("10.9.0.0/24"),
                                 ipaddress.ip_network("127.0.0.1/32")]

        self.assertSuccess("myuser", "mypass", "127.0.0.1")
        self.assertFailure("myuser", "mypass", "127.0.0.0")
        self.assertSuccess("myuser", "mypass", "10.9.0.7")

        # Corner cases.
        self.participation.ip = []
        self.assertFailure("myuser", "mypass", "10.0.0.1")

        self.participation.ip = None
        self.assertSuccess("myuser", "mypass", "10.0.0.1")

    def test_deactivated_ip_lock(self):
        self.contest.ip_restriction = False
        self.participation.ip = [ipaddress.ip_network("10.0.0.0/24")]

        self.assertSuccess("myuser", "mypass", "10.0.1.1")


class TestAuthenticateRequest(DatabaseMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.timestamp = make_datetime()
        self.add_contest()
        self.contest = self.add_contest()
        self.add_user(username="otheruser")
        self.user = self.add_user(
            username="myuser", password=build_password("mypass"))
        self.participation = self.add_participation(
            contest=self.contest, user=self.user)
        _, self.cookie = validate_login(
            self.session, self.contest, self.timestamp, self.user.username,
            "mypass", ipaddress.ip_address("10.0.0.1"))

    def attempt_authentication(self, **kwargs):
        # The arguments need to be passed as keywords and are timestamp, cookie
        # and ip_address. A missing argument means the default value is used
        # instead. An argument passed as None means that None will be used.
        return authenticate_request(
            self.session, self.contest,
            kwargs.get("timestamp", self.timestamp),
            kwargs.get("cookie", self.cookie),
            ipaddress.ip_address(kwargs.get("ip_address", "10.0.0.1")))

    def assertSuccess(self, **kwargs):
        # Assert that the authentication succeeds in any way (be it through IP
        # autologin or thanks to the cookie) and return the cookie that should
        # be set (or None, if it should be cleared/left unset).
        # The arguments are the same as those of attempt_authentication.

        # We had an issue where due to a misuse of contains_eager we ended up
        # with the wrong user attached to the participation. This only happens
        # if the correct user isn't already in the identity map, which is what
        # these lines trigger.
        self.session.flush()
        self.session.expire(self.user)
        self.session.expire(self.contest)

        authenticated_participation, cookie = \
            self.attempt_authentication(**kwargs)

        self.assertIsNotNone(authenticated_participation)
        self.assertIs(authenticated_participation, self.participation)
        self.assertIs(authenticated_participation.user, self.user)
        self.assertIs(authenticated_participation.contest, self.contest)

        return cookie

    def assertSuccessAndCookieRefreshed(self, **kwargs):
        # Assert that the authentication succeeds and that a cookie is returned
        # as well, to be refreshed on the client. (This typically indicates
        # that the authentication was performed through the cookie.)
        # The arguments are the same as those of attempt_authentication.
        cookie = self.assertSuccess(**kwargs)
        self.assertIsNotNone(cookie)
        return cookie

    def assertSuccessAndCookieCleared(self, **kwargs):
        # Assert that the authentication succeeds and no cookie is returned,
        # meaning that it needs to be cleared (or left unset) on the client.
        # (This typically indicates that the authentication occurred by IP
        # autologin.)
        # The arguments are the same as those of attempt_authentication.
        cookie = self.assertSuccess(**kwargs)
        self.assertIsNone(cookie)

    def assertFailure(self, **kwargs):
        # Assert that the authentication fails.
        # The arguments are the same as those of attempt_authentication.
        authenticated_participation, cookie = \
            self.attempt_authentication(**kwargs)
        self.assertIsNone(authenticated_participation)
        self.assertIsNone(cookie)

    @patch.object(config, "cookie_duration", 10)
    def test_cookie_contains_timestamp(self):
        self.contest.ip_autologin = False
        self.contest.allow_password_authentication = True

        # The cookie allows to authenticate.
        self.assertSuccessAndCookieRefreshed()

        # Until the duration expires.
        new_cookie = self.assertSuccessAndCookieRefreshed(
            timestamp=self.timestamp + timedelta(seconds=8))

        # But not after it expires.
        self.assertFailure(timestamp=self.timestamp + timedelta(seconds=14))

        # Unless the cookie is refreshed.
        self.assertSuccessAndCookieRefreshed(
            timestamp=self.timestamp + timedelta(seconds=14),
            cookie=new_cookie)

    def test_cookie_contains_password(self):
        self.contest.ip_autologin = False

        # Cookies are of no use if one cannot login by password.
        self.contest.allow_password_authentication = False
        self.assertFailure()
        self.contest.allow_password_authentication = True

        # Cookies contain the password, which is validated every time.
        self.user.password = build_password("newpass")
        self.assertFailure()

        # Contest-specific passwords take precedence over global ones.
        self.participation.password = build_password("mypass")
        self.assertSuccessAndCookieRefreshed()

        # And they do so in the negative case too.
        self.user.password = build_password("mypass")
        self.participation.password = build_password("newpass")
        self.assertFailure()

    def test_ip_autologin(self):
        self.contest.ip_autologin = True
        self.contest.allow_password_authentication = False

        self.participation.ip = [ipaddress.ip_network("10.0.0.1/32")]
        self.assertSuccessAndCookieCleared()

        self.assertFailure(ip_address="10.1.0.1")

        self.participation.ip = [ipaddress.ip_network("10.0.0.0/24")]
        self.assertFailure()

    def test_ip_autologin_with_ambiguous_addresses(self):
        # If two users have the same IP address neither of them can autologin.
        self.contest.ip_autologin = True
        self.contest.allow_password_authentication = False
        self.participation.ip = [ipaddress.ip_network("10.0.0.1/32")]
        other_user = self.add_user()
        other_participation = self.add_participation(
            contest=self.contest, user=other_user,
            ip=[ipaddress.ip_network("10.0.0.1/32")])
        self.assertFailure()

        # In fact, they don't even fall back to cookie-based authentication.
        self.contest.allow_password_authentication = True
        self.assertFailure()

        # But if IP autologin is disabled altogether, ambiguous IP addresses
        # are disregarded and cookie-based authentication kicks in.
        self.contest.ip_autologin = False
        self.assertSuccessAndCookieRefreshed()

        # Ambiguous IP addresses are allowed if only one of them is non-hidden
        # (and hidden users are barred from logging in).
        self.contest.ip_autologin = True
        self.contest.block_hidden_participations = True
        other_participation.hidden = True
        self.assertSuccessAndCookieCleared()

        # But not if hidden users aren't blocked.
        self.contest.block_hidden_participations = False
        self.assertFailure()

    def test_invalid_password_in_database(self):
        self.contest.ip_autologin = False
        self.contest.allow_password_authentication = True
        self.user.password = "not a valid password"
        self.assertFailure()

        self.user.password = build_password("mypass")
        self.participation.password = "not a valid password"
        self.assertFailure()

    def test_invalid_cookie(self):
        self.contest.ip_autologin = False
        self.contest.allow_password_authentication = True
        self.assertFailure(cookie=None)
        self.assertFailure(cookie="not a valid cookie")

    def test_no_user(self):
        self.session.delete(self.user)
        self.assertFailure()

    def test_no_participation_for_user_in_contest(self):
        self.session.delete(self.participation)
        self.assertFailure()

    def test_hidden_user(self):
        self.contest.ip_autologin = True
        self.contest.allow_password_authentication = True
        self.contest.block_hidden_participations = True
        self.participation.hidden = True
        self.assertFailure()

    def test_ip_lock(self):
        self.contest.ip_autologin = True
        self.contest.allow_password_authentication = True
        self.contest.ip_restriction = True
        self.participation.ip = [ipaddress.ip_network("10.0.0.0/24"),
                                 ipaddress.ip_network("127.0.0.1/32")]

        self.assertSuccessAndCookieCleared(ip_address="127.0.0.1")
        self.assertSuccessAndCookieRefreshed(ip_address="10.0.0.1")
        self.assertFailure(ip_address="10.1.0.1")

        self.contest.ip_restriction = False
        self.assertSuccessAndCookieRefreshed()

        # Corner cases.
        self.contest.ip_restriction = True
        self.participation.ip = []
        self.assertFailure()

        self.participation.ip = None
        self.assertSuccessAndCookieRefreshed()


if __name__ == "__main__":
    unittest.main()
