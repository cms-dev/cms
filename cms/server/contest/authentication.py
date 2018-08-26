#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2016 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2015-2016 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
# Copyright © 2016 Amir Keivan Mohtashami <akmohtashami97@gmail.com>
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

import ipaddress
import json
import logging
from datetime import timedelta

from sqlalchemy.orm import contains_eager

from cms import config
from cms.db import Participation, User
from cmscommon.crypto import validate_password
from cmscommon.datetime import make_datetime, make_timestamp


__all__ = ["validate_login", "authenticate_request"]


logger = logging.getLogger(__name__)


def safe_validate_password(participation, password):
    """Check that the password is correct for the authentication.

    Validate the given password against the participation (using either
    the global or the contest-specific password that is stored in the
    database), and guard against a misconfiguration.

    participation (Participation): a participation.
    password (str): a password provided by someone trying to log in
        claiming to be the given participation.

    return (bool): whether the password matches the expected one.

    """
    if participation.password is None:
        correct_password = participation.user.password
    else:
        correct_password = participation.password

    try:
        password_valid = validate_password(correct_password, password)
    except ValueError as e:
        # This is either a programming or a configuration error.
        logger.warning(
            "Invalid password stored in database for user %s in contest %s: "
            "%s", participation.user.username, participation.contest.name, e)
        return False

    return password_valid


def validate_login(
        sql_session, contest, timestamp, username, password, ip_address):
    """Authenticate a user logging in, with username and password.

    Given the information the user provided (the username and the
    password) and some context information (contest, to determine which
    users are allowed to log in, how and with which restrictions;
    timestamp for cookie creation; IP address to check against) try to
    authenticate the user and return its participation and the cookie
    to set to help authenticate future visits.

    After finding the participation, IP login and hidden users
    restrictions are checked.

    sql_session (Session): the SQLAlchemy database session used to
        execute queries.
    contest (Contest): the contest the user is trying to access.
    timestamp (datetime): the date and the time of the request.
    username (str): the username the user provided.
    password (str): the password the user provided.
    ip_address (IPv4Address|IPv6Address): the IP address the request
        came from.

    return ((Participation, bytes)|(None, None)): if the user couldn't
        be authenticated then return None, otherwise return the
        participation that they wanted to authenticate as; if a cookie
        has to be set return it as well, otherwise return None.

    """
    def log_failed_attempt(msg, *args):
        logger.info("Unsuccessful login attempt from IP address %s, as user "
                    "%r, on contest %s, at %s: " + msg, ip_address,
                    username, contest.name, timestamp, *args)

    if not contest.allow_password_authentication:
        log_failed_attempt("password authentication not allowed")
        return None, None

    participation = sql_session.query(Participation) \
        .join(Participation.user) \
        .options(contains_eager(Participation.user)) \
        .filter(Participation.contest == contest)\
        .filter(User.username == username)\
        .first()

    if participation is None:
        log_failed_attempt("user not registered to contest")
        return None, None

    if not safe_validate_password(participation, password):
        log_failed_attempt("wrong password")
        return None, None

    if contest.ip_restriction and participation.ip is not None \
            and not any(ip_address in network for network in participation.ip):
        log_failed_attempt("unauthorized IP address")
        return None, None

    if contest.block_hidden_participations and participation.hidden:
        log_failed_attempt("participation is hidden and unauthorized")
        return None, None

    logger.info("Successful login attempt from IP address %s, as user %r, on "
                "contest %s, at %s", ip_address, username, contest.name,
                timestamp)

    return (participation,
            json.dumps([username, password, make_timestamp(timestamp)]))


class AmbiguousIPAddress(Exception):
    pass


def authenticate_request(
        sql_session, contest, timestamp, cookie, ip_address):
    """Authenticate a user returning to the site, with a cookie.

    Given the information the user's browser provided (the cookie) and
    some context information (contest, to determine which users are
    allowed to log in, how and with which restrictions; timestamp for
    cookie validation/creation, IP address to either do autologin or to
    check against) try to authenticate the user and return its
    participation and the cookie to refresh to help authenticate future
    visits.

    There are two way a user can authenticate:
    - if IP autologin is enabled, we look for a participation whose IP
      address matches the remote IP address; if a match is found, the
      user is authenticated as that participation;
    - if username/password authentication is enabled, and the cookie
      is valid, the corresponding participation is returned, together
      with a refreshed cookie.

    After finding the participation, IP login and hidden users
    restrictions are checked.

    In case of any error, or of a login by other sources, no new cookie
    is returned and the old one, if any, should be cleared.

    sql_session (Session): the SQLAlchemy database session used to
        execute queries.
    contest (Contest): the contest the user is trying to access.
    timestamp (datetime): the date and the time of the request.
    cookie (bytes|None): the cookie the user's browser provided in the
        request (if any).
    ip_address (IPv4Address|IPv6Address): the IP address the request
        came from.

    return ((Participation, bytes|None)|(None, None)): if the user
        couldn't be authenticated then return None, otherwise return
        the participation that they wanted to authenticate as; if a
        cookie has to be set return it as well, otherwise return None.

    """
    participation = None

    if contest.ip_autologin:
        try:
            participation = _authenticate_request_by_ip_address(
                sql_session, contest, ip_address)
            # If the login is IP-based, the cookie should be cleared.
            if participation is not None:
                cookie = None
        except AmbiguousIPAddress:
            return None, None

    if participation is None \
            and contest.allow_password_authentication:
        participation, cookie = _authenticate_request_from_cookie(
            sql_session, contest, timestamp, cookie)

    if participation is None:
        return None, None

    # Check if user is using the right IP (or is on the right subnet).
    if contest.ip_restriction and participation.ip is not None \
            and not any(ip_address in network for network in participation.ip):
        logger.info(
            "Unsuccessful authentication from IP address %s, on contest %s, "
            "as %s, at %s: unauthorized IP address",
            ip_address, contest.name, participation.user.username, timestamp)
        return None, None

    # Check that the user is not hidden if hidden users are blocked.
    if contest.block_hidden_participations and participation.hidden:
        logger.info(
            "Unsuccessful authentication from IP address %s, on contest %s, "
            "as %s, at %s: participation is hidden and unauthorized",
            ip_address, contest.name, participation.user.username, timestamp)
        return None, None

    return participation, cookie


def _authenticate_request_by_ip_address(sql_session, contest, ip_address):
    """Return the current participation based on the IP address.

    sql_session (Session): the SQLAlchemy database session used to
        execute queries.
    contest (Contest): the contest the user is trying to access.
    ip_address (IPv4Address|IPv6Address): the IP address the request
        came from.

    return (Participation|None): the only participation that is allowed
        to connect from the given IP address, or None if not found.

    raise (AmbiguousIPAddress): if there is more than one participation
        matching the remote IP address.

    """
    # We encode it as a network (i.e., we assign it a /32 or /128 mask)
    # since we're comparing it for equality with other networks.
    ip_network = ipaddress.ip_network((ip_address, ip_address.max_prefixlen))

    participations = sql_session.query(Participation) \
        .options(contains_eager(Participation.user)) \
        .filter(Participation.contest == contest) \
        .filter(Participation.ip.any(ip_network))

    # If hidden users are blocked we ignore them completely.
    if contest.block_hidden_participations:
        participations = participations \
            .filter(Participation.hidden.is_(False))

    participations = participations.all()

    if len(participations) == 0:
        logger.info(
            "Unsuccessful IP authentication from IP address %s, on contest "
            "%s: no user matches the IP address", ip_address, contest.name)
        return None

    # Having more than participation with the same IP, is a mistake and
    # should not happen. In such case, we disallow login for that IP
    # completely, in order to make sure the problem is noticed.
    if len(participations) > 1:
        # This is a configuration error.
        logger.warning(
            "Ambiguous IP address %s, assigned to %d participations.",
            ip_address, len(participations))
        raise AmbiguousIPAddress()

    participation = participations[0]
    logger.info(
        "Successful IP authentication from IP address %s, as user %s, on "
        "contest %s", ip_address, participation.user.username, contest.name)
    return participation


def _authenticate_request_from_cookie(sql_session, contest, timestamp, cookie):
    """Return the current participation based on the cookie.

    If a participation can be extracted, the cookie is refreshed.

    sql_session (Session): the SQLAlchemy database session used to
        execute queries.
    contest (Contest): the contest the user is trying to access.
    timestamp (datetime): the date and the time of the request.
    cookie (bytes|None): the cookie the user's browser provided in the
        request (if any).

    return ((Participation, bytes)|(None, None)): the participation
        extracted from the cookie and the cookie to set/refresh, or
        None in case of errors.

    """
    if cookie is None:
        logger.info("Unsuccessful cookie authentication: no cookie provided")
        return None, None

    # Parse cookie.
    try:
        cookie = json.loads(cookie)
        username = cookie[0]
        password = cookie[1]
        last_update = make_datetime(cookie[2])
    except Exception as e:
        # Cookies are stored securely and thus cannot be tampered with:
        # this is either a programming or a configuration error.
        logger.warning("Invalid cookie (%s): %s", e, cookie)
        return None, None

    def log_failed_attempt(msg, *args):
        logger.info("Unsuccessful cookie authentication as %r, returning from "
                    "%s, at %s: " + msg, username, last_update, timestamp,
                    *args)

    # Check if the cookie is expired.
    if timestamp - last_update > timedelta(seconds=config.cookie_duration):
        log_failed_attempt("cookie expired (lasts %d seconds)",
                           config.cookie_duration)
        return None, None

    # Load participation from DB and make sure it exists.
    participation = sql_session.query(Participation) \
        .join(Participation.user) \
        .options(contains_eager(Participation.user)) \
        .filter(Participation.contest == contest) \
        .filter(User.username == username) \
        .first()
    if participation is None:
        log_failed_attempt("user not registered to contest")
        return None, None

    if not safe_validate_password(participation, password):
        log_failed_attempt("wrong password")
        return None, None

    logger.info("Successful cookie authentication as user %r, on contest %s, "
                "returning from %s, at %s", username, contest.name, last_update,
                timestamp)

    return (participation,
            json.dumps([username, password, make_timestamp(timestamp)]))
