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
from future.builtins.disabled import *
from future.builtins import *
from six import iteritems

import os
import sys
import time
from datetime import tzinfo, timedelta, datetime
from pytz import timezone, all_timezones


__all__ = [
    "make_datetime", "make_timestamp",
    "get_timezone", "get_system_timezone",

    "utc",

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


def get_timezone(user, contest):
    """Return the timezone for the given user and contest

    user (User): the user owning the timezone.
    contest (Contest): the contest in which the user is competing.

    return (tzinfo): the timezone information for the user.

    """
    if user.timezone is not None and user.timezone in all_timezones:
        return timezone(user.timezone)
    if contest.timezone is not None and contest.timezone in all_timezones:
        return timezone(contest.timezone)
    return local


def get_system_timezone():
    """Return the timezone of the system.

    See http://stackoverflow.com/questions/7669938/
        get-the-olson-tz-name-for-the-local-timezone

    return (unicode|None): one among the possible timezone description
        strings in the form Europe/Rome, or None if nothing is found.

    """
    if time.daylight:
        local_offset = time.altzone
        localtz = time.tzname[1]
    else:
        local_offset = time.timezone
        localtz = time.tzname[0]

    local_offset = timedelta(seconds=-local_offset)

    for name in all_timezones:
        tz = timezone(name)
        if not hasattr(tz, '_tzinfos'):
            continue
        for (utcoffset, daylight, tzname), _ in iteritems(tz._tzinfos):
            if utcoffset == local_offset and tzname == localtz:
                return name

    return None


# The following code provides some sample timezone implementations
# (i.e. tzinfo subclasses). It has been copied (almost) verbatim
# from the official datetime module documentation:
# http://docs.python.org/library/datetime.html#tzinfo-objects

ZERO = timedelta(0)
HOUR = timedelta(hours=1)


# A UTC class.

class UTC(tzinfo):
    """UTC"""

    def utcoffset(self, dt):
        return ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return ZERO

utc = UTC()


# A class capturing the platform's idea of local time.

STDOFFSET = timedelta(seconds=-time.timezone)
if time.daylight:
    DSTOFFSET = timedelta(seconds=-time.altzone)
else:
    DSTOFFSET = STDOFFSET

DSTDIFF = DSTOFFSET - STDOFFSET


class LocalTimezone(tzinfo):

    def utcoffset(self, dt):
        if self._isdst(dt):
            return DSTOFFSET
        else:
            return STDOFFSET

    def dst(self, dt):
        if self._isdst(dt):
            return DSTDIFF
        else:
            return ZERO

    def tzname(self, dt):
        return time.tzname[self._isdst(dt)]

    def _isdst(self, dt):
        tt = (dt.year, dt.month, dt.day,
              dt.hour, dt.minute, dt.second,
              dt.weekday(), 0, 0)
        stamp = time.mktime(tt)
        tt = time.localtime(stamp)
        return tt.tm_isdst > 0

local = LocalTimezone()


if sys.version_info >= (3, 3):
    def monotonic_time():
        """Get the number of seconds passed since a fixed past moment.

        A monotonic clock measures the time elapsed since an arbitrary
        but immutable instant in the past. The value itself has no
        direct intrinsic meaning but the difference between two such
        values does, as it is guaranteed to accurately represent the
        amount of time passed between when those two measurements were
        taken, no matter the adjustments to the clock that occurred in
        between. Even NTP adjustments are ignored, meaning that the
        flow of time here is dictated only by the system clock and thus
        subject to any drift it may have.

        return (float): the value of the clock, in seconds.

        """
        return time.clock_gettime(time.CLOCK_MONOTONIC_RAW)

# Taken from http://bugs.python.org/file19461/monotonic.py and
# http://stackoverflow.com/questions/1205722/how-do-i-get-monotonic-time-durations-in-python
# and modified.
else:
    from ctypes import Structure, c_long, CDLL, c_int, get_errno, POINTER, \
        pointer
    from ctypes.util import find_library

    # Raw means it's immune even to NTP time adjustements.
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
