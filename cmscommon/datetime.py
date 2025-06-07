#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2012-2017 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Stefano Maggiolo <s.maggiolo@gmail.com>
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

import os
import sys
import time
from datetime import datetime, tzinfo
import typing

if typing.TYPE_CHECKING:
    from cms.db import User, Contest

import babel.dates


__all__ = [
    "make_datetime", "make_timestamp",
    "get_timezone", "get_system_timezone",

    "utc", "local_tz",
    ]


def make_datetime(timestamp: int | float | None = None) -> datetime:
    """Return the datetime object associated with the given timestamp.

    timestamp: a POSIX timestamp, or None to use now.

    return: the datetime representing the UTC time of the
        given timestamp.

    """
    if timestamp is None:
        return datetime.utcnow()
    else:
        return datetime.utcfromtimestamp(timestamp)


EPOCH = datetime(1970, 1, 1)


def make_timestamp(_datetime: datetime | None = None) -> float:
    """Return the timestamp associated with the given datetime object.

    _datetime: a datetime object, or None to use now.

    return: the POSIX timestamp corresponding to the given
        datetime ("read" in UTC).

    """
    if _datetime is None:
        return time.time()
    else:
        return (_datetime - EPOCH).total_seconds()


utc = babel.dates.UTC
local_tz = babel.dates.LOCALTZ


def get_timezone(user: "User", contest: "Contest") -> tzinfo:
    """Return the timezone for the given user and contest

    user: the user owning the timezone.
    contest: the contest in which the user is competing.

    return: the timezone information for the user.

    """
    if user.timezone is not None:
        try:
            return babel.dates.get_timezone(user.timezone)
        except LookupError:
            pass
    if contest.timezone is not None:
        try:
            return babel.dates.get_timezone(contest.timezone)
        except LookupError:
            pass
    return local_tz


def get_system_timezone() -> str:
    """Return the name of the system timezone.

    return: the "best" description of the timezone of the
        local system clock that we were able to find, in a format like
        "Europe/Rome", "CET", etc.

    """
    if hasattr(local_tz, 'zone'):
        return local_tz.zone
    return local_tz.tzname(make_datetime())
