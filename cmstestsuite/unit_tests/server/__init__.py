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

"""Tests for common server functions.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import unittest
from datetime import date, time, datetime, timedelta

from cms.server import compute_actual_phase


def parse_datetime(value):
    """Convert a string "HH[:MM[:SS]]" into a datetime of 2000-01-01.

    value (string|None): a formatted time, or None.
    return (datetime|None): the datetime, or None if value was None.

    """
    if value is None:
        return None
    return datetime(2000, 1, 1, *[int(v, 10) for v in value.split(":")])


def parse_timedelta(value):
    """Convert a string "HH[:MM[:SS]]" into a timedelta.

    value (string|None): a formatted time, or None.
    return (timedelta|None): the timedelta, or None if value was None.

    """
    if value is None:
        return None
    return timedelta(seconds=sum(int(v, 10) * 60**(2-i)
                                 for i, v in enumerate(value.split(":"))))


TEST_STEPS = \
    [timedelta(seconds=t) for t in (1, 5, 15, 30)] + \
    [timedelta(minutes=t) for t in (1, 5, 15, 30)] + \
    [timedelta(hours=t) for t in (1, 3, 6, 12, 24)]


def test(contest_start, contest_stop, per_user_time, starting_time,
         delay_time, extra_time, intervals):
    """Helper to test compute_actual_phase.

    It takes all the parameters accepted by compute_actual_phase (with
    the same semantic but in a different format: instead of datetimes
    and timedeltas they have to be strings in the form "HH[:MM[:SS]]")
    with the exception of timestamp, which is substituted by intervals.
    This represents the partition into intervals that the first six
    parameters induce on the time. It's a tuple with an odd number of
    elements, the ones having even index being datetimes in the format
    "HH[:MM[:SS]]" and the ones having odd index being integers, i.e.
    "labels" for the time interval delimited by the datetime preceding
    and following the label. Additionally we will also consider the
    intervals [-infty, intervals[0]] (labeled -2) and [intervals[-1],
    +infty] (labeled +2).

    This function selects a sample of datetimes inside each interval
    (more "dense" near the boundaries), calls compute_actual_phase on
    each of them and checks that the label of the interval is returned.

    contest_start (string): the contest's start.
    contest_stop (string): the contest's stop.
    per_user_time (string|None): the amount of time allocated to each
        user; contest is USACO-like if given and traditional if not.
    starting_time (string|None): when the user started his time frame.
    delay_time (string): how much the user's start is delayed.
    extra_time (string): how much extra time is given to the user at
        the end.
    intervals (tuple): see above.

    raise (Exception): if compute_actual_phase doesn't behave as
        expected, or if some arguments weren't properly formatted.

    """
    contest_start = parse_datetime(contest_start)
    contest_stop = parse_datetime(contest_stop)
    per_user_time = parse_timedelta(per_user_time)
    starting_time = parse_datetime(starting_time)
    delay_time = parse_timedelta(delay_time)
    extra_time = parse_timedelta(extra_time)

    assert len(intervals) % 2 == 1
    parsed = list()
    valid_begin = None
    valid_end = None
    parsed.append((-2, None, parse_datetime(intervals[0])))
    for i in range(1, len(intervals), 2):
        status = intervals[i]
        begin = parse_datetime(intervals[i-1])
        end = parse_datetime(intervals[i+1])

        parsed.append((status, begin, end))

        if status == 0:
            valid_begin, valid_end = begin, end
    parsed.append((+2, parse_datetime(intervals[-1]), None))

    for status, begin, end in parsed:
        if begin is None:
            for step in TEST_STEPS:
                res = compute_actual_phase(
                    end - step, contest_start, contest_stop,
                    per_user_time, starting_time, delay_time, extra_time)
                assert res == (status, begin, end, valid_begin, valid_end), \
                    "Check on %s returned %s instead of %s" % (
                        end - step, res, (status, begin, end,
                                          valid_begin, valid_end))
        elif end is None:
            for step in TEST_STEPS:
                res = compute_actual_phase(
                    begin + step, contest_start, contest_stop,
                    per_user_time, starting_time, delay_time, extra_time)
                assert res == (status, begin, end, valid_begin, valid_end), \
                    "Check on %s returned %s instead of %s" % (
                        begin + step, res, (status, begin, end,
                                            valid_begin, valid_end))
        else:
            for step in TEST_STEPS:
                if begin + step > end - step:
                    break
                res = compute_actual_phase(
                    begin + step, contest_start, contest_stop,
                    per_user_time, starting_time, delay_time, extra_time)
                assert res == (status, begin, end, valid_begin, valid_end), \
                    "Check on %s returned %s instead of %s" % (
                        begin + step, res, (status, begin, end,
                                            valid_begin, valid_end))
                res = compute_actual_phase(
                    end - step, contest_start, contest_stop,
                    per_user_time, starting_time, delay_time, extra_time)
                assert res == (status, begin, end, valid_begin, valid_end), \
                    "Check on %s returned %s instead of %s" % (
                        end - step, res, (status, begin, end,
                                          valid_begin, valid_end))


class TestComputeActualPhase(unittest.TestCase):

    @staticmethod
    def test_traditional():
        # Test "traditional" contests. There's not much variability, so
        # we just test different delay_time/extra_time combinations.
        test("6", "18", None, None, "0", "0", ("6", 0, "18"))
        test("6", "18", None, None, "0", "2", ("6", 0, "20"))
        test("6", "18", None, None, "2", "0", ("6", -1, "8", 0, "20"))
        test("6", "18", None, None, "2", "2", ("6", -1, "8", 0, "22"))

        # Almost identical, with starting_time set to make sure it
        # doesn't affect anything.
        test("6", "18", None, "9", "0", "0", ("6", 0, "18"))
        test("6", "18", None, "9", "0", "2", ("6", 0, "20"))
        test("6", "18", None, "9", "2", "0", ("6", -1, "8", 0, "20"))
        test("6", "18", None, "9", "2", "2", ("6", -1, "8", 0, "22"))

    @staticmethod
    def test_usaco_like():
        # Test "USACO-like" contests, with known starting_time.
        # Consider cases where the active phase is entirely inside the
        # contest time as well as cases where it oversteps the end and
        # (absurdly) the start of the contest. Also try different
        # delay_time/extra_time combinations.
        test("6", "18", "6", "9", "0", "0", ("6", -1, "9", 0, "15", +1, "18"))
        test("6", "18", "6", "3", "0", "0", ("6", 0, "9", +1, "18"))
        test("6", "18", "6", "15", "0", "0", ("6", -1, "15", 0, "18"))
        test("6", "18", "6", "9", "0", "1", ("6", -1, "9", 0, "16", +1, "18"))
        test("6", "18", "6", "3", "0", "1", ("6", 0, "10", +1, "18"))
        test("6", "18", "6", "15", "0", "1", ("6", -1, "15", 0, "19"))
        test("6", "18", "6", "9", "1", "0", ("6", -1, "10", 0, "16", +1, "18"))
        test("6", "18", "6", "3", "1", "0", ("6", -1, "7", 0, "10", +1, "18"))
        test("6", "18", "6", "15", "1", "0", ("6", -1, "16", 0, "19"))
        test("6", "18", "6", "9", "1", "1", ("6", -1, "10", 0, "17", +1, "18"))
        test("6", "18", "6", "3", "1", "1", ("6", -1, "7", 0, "11", +1, "18"))
        test("6", "18", "6", "15", "1", "1", ("6", -1, "16", 0, "20"))

        # Test "USACO-like" contests, with unknown starting_time. Just
        # make sure delay_time/extra_time don't affect anything.
        test("6", "18", "6", None, "0", "0", ("6", -1, "18"))
        test("6", "18", "6", None, "0", "1", ("6", -1, "18"))
        test("6", "18", "6", None, "1", "0", ("6", -1, "18"))
        test("6", "18", "6", None, "1", "1", ("6", -1, "18"))

        # Test ridiculous corner cases.
        test("6", "18", "3", "2", "0", "0", ("6", 0, "6", +1, "18"))
        test("6", "18", "3", "2", "0", "1", ("6", 0, "7", +1, "18"))
        test("6", "18", "3", "2", "1", "0", ("6", -1, "7", 0, "7", +1, "18"))
        test("6", "18", "3", "2", "1", "1", ("6", -1, "7", 0, "8", +1, "18"))
        test("6", "18", "3", "19", "0", "0", ("6", -1, "18", 0, "18"))
        test("6", "18", "3", "19", "0", "1", ("6", -1, "18", 0, "19"))
        # These are plainly absurd.
        test("6", "18", "3", "19", "1", "0", ("6", -1, "19", 0, "19"))
        test("6", "18", "3", "19", "1", "1", ("6", -1, "19", 0, "20"))


if __name__ == "__main__":
    unittest.main()
