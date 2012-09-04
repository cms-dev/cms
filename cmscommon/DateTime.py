#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2012 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

import time
from datetime import tzinfo, timedelta, datetime
from pytz import timezone, all_timezones


def make_datetime(timestamp=None):
    """Return the datetime object associated with the given timestamp

    timestamp (int or float): a POSIX timestamp
    returns (datetime): the datetime representing the UTC time of the
                        given timestamp, or now if timestamp is None.

    """
    if timestamp is None:
        return datetime.utcnow()
    else:
        return datetime.utcfromtimestamp(timestamp)


EPOCH = datetime(1970, 1, 1)

def make_timestamp(_datetime=None):
    """Return the timestamp associated with the given datetime object

    _datetime (datetime): a datetime object
    returns (float): the POSIX timestamp corresponding to the given
                     datetime ("read" in UTC), or now if datetime is
                     None.

    """
    if _datetime is None:
        return time.time()
    else:
        return (_datetime - EPOCH).total_seconds()


def get_timezone(user, contest):
    """Return the timezone for the given user and contest

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

    return (string): one among the possible timezone description
                     strings in the form Europe/Rome, or None if
                     nothing is found.

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
        for (utcoffset, daylight, tzname), _ in tz._tzinfos.items():
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

# A class building tzinfo objects for fixed-offset time zones.
# Note that FixedOffset(0, "UTC") is a different way to build a
# UTC tzinfo object.

class FixedOffset(tzinfo):
    """Fixed offset in minutes east from UTC."""

    def __init__(self, offset, name):
        self.__offset = timedelta(minutes = offset)
        self.__name = name

    def utcoffset(self, dt):
        return self.__offset

    def tzname(self, dt):
        return self.__name

    def dst(self, dt):
        return ZERO

# A class capturing the platform's idea of local time.

STDOFFSET = timedelta(seconds = -time.timezone)
if time.daylight:
    DSTOFFSET = timedelta(seconds = -time.altzone)
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
