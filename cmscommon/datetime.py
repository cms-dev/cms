#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa

import os
import time
import sys
from datetime import datetime

import babel.dates


__all__ = [
    "make_datetime", "make_timestamp",
    "get_timezone", "get_system_timezone",

    "utc", "local_tz",

    "monotonic_time",
    ]


def make_datetime(timestamp=None):
    """Return the datetime object associated with the given timestamp.

    timestamp (int|float|None): a POSIX timestamp, or None to use now.

    return (datetime): the datetime representing the UTC time of the
        given timestamp.

    """
    if timestamp is None:
        return datetime.utcnow()
    else:
        return datetime.utcfromtimestamp(timestamp)


EPOCH = datetime(1970, 1, 1)


def make_timestamp(_datetime=None):
    """Return the timestamp associated with the given datetime object.

    _datetime (datetime|None): a datetime object, or None to use now.

    return (float): the POSIX timestamp corresponding to the given
        datetime ("read" in UTC).

    """
    if _datetime is None:
        return time.time()
    else:
        return (_datetime - EPOCH).total_seconds()


utc = babel.dates.UTC
local_tz = babel.dates.LOCALTZ


def get_timezone(user, contest):
    """Return the timezone for the given user and contest

    user (User): the user owning the timezone.
    contest (Contest): the contest in which the user is competing.

    return (tzinfo): the timezone information for the user.

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


def get_system_timezone():
    """Return the name of the system timezone.

    return (unicode): the "best" description of the timezone of the
        local system clock that we were able to find, in a format like
        "Europe/Rome", "CET", etc.

    """
    if hasattr(local_tz, 'zone'):
        return local_tz.zone
    return local_tz.tzname(make_datetime())


if sys.version_info >= (3, 3):
    def monotonic_time():
        """Get the number of seconds passed since a fixed past moment.

        A monotonic clock measures the time elapsed since an arbitrary
        but immutable instant in the past. The value itself has no
        direct intrinsic meaning but the difference between two such
        values does, as it is guaranteed to accurately represent the
        amount of time passed between when those two measurements were
        taken, no matter the adjustments to the clock that occurred in
        between.

        return (float): the value of the clock, in seconds.

        """
        return time.monotonic()

# Taken from http://bugs.python.org/file19461/monotonic.py and
# http://stackoverflow.com/questions/1205722/how-do-i-get-monotonic-time-durations-in-python
# and modified.
else:
    from ctypes import Structure, c_long, CDLL, c_int, get_errno, POINTER, \
        pointer
    from ctypes.util import find_library

    # Raw means it's immune even to NTP time adjustments.
    CLOCK_MONOTONIC_RAW = 4

    class timespec(Structure):
        _fields_ = [
            ('tv_sec', c_long),
            ('tv_nsec', c_long)
            ]

    librt_filename = find_library('rt')
    if not librt_filename:
        # On Debian Lenny (Python 2.5.2), find_library() is unable
        # to locate /lib/librt.so.1
        librt_filename = 'librt.so.1'
    librt = CDLL(librt_filename, use_errno=True)
    _clock_gettime = librt.clock_gettime
    _clock_gettime.argtypes = (c_int, POINTER(timespec))

    def monotonic_time():
        """Get the number of seconds passed since a fixed past moment.

        return (float): the value of a monotonic clock, in seconds.

        """
        t = timespec()
        if _clock_gettime(CLOCK_MONOTONIC_RAW, pointer(t)) != 0:
            errno_ = get_errno()
            raise OSError(errno_, os.strerror(errno_))
        return t.tv_sec + t.tv_nsec / 1e9
