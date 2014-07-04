#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2012 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""
The file with the events has one row per event, with these format
(space separated):
timestamp (seconds relative to the contest)
username
task_id
task_shortname
action (submit|release)

Next, for submit:
comma-separated list of file paths

For token:
submission_num

All users have empty passwords.

TODO: currently only works with tasks with one file per submission
(this is a limitation of SubmitRequest).

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import io
import sys
import time

from argparse import ArgumentParser
from mechanize import Browser
from threading import Thread

from cms import utf8_decoder
from cmstestsuite.web.CWSRequests import \
    LoginRequest, SubmitRequest, TokenRequest


start = None
speed = 1
old_speed = 1


def to_time(seconds):
    """Convert a relative timestamp in seconds to a human-readable
    format.

    seconds (int): timestamp.

    return (string): time formatted as %H:%M:%S.

    """
    hours = seconds // 3600
    minutes = seconds // 60 % 60
    seconds = seconds % 60
    return "%02d:%02d:%02d" % (hours, minutes, seconds)


def recompute_start(start, speed, old_speed):
    """Utility to recompute the start time of a contest passing from a
    speed of old_speed to a speed of speed.

    start (int): old start time of the contest with speed old_speed.
    speed (int): new speed of the replayer.
    old_speed (int): previous speed of the replayer.

    return (int): new start time using the new speed.

    """
    if speed != old_speed:
        start += (time.time() - start) * (speed - old_speed) * 1.0 / speed
        old_speed = speed
    return start, speed, old_speed


def step(request):
    """Prepare and execute the request in a single instruction.

    request (GenericRequest): some request to *WS.

    """
    request.prepare()
    request.execute()


def submit(timestamp, username, t_id, t_short, files, base_url):
    """Execute the request for a submission.

    timestamp (int): seconds from the start.
    username (string): username issuing the submission.
    t_id (string): id of the task.
    t_short (string): short name of the task.
    files ([string]): list of filenames of submitted files.
    base_url (string): http address of CWS.

    """
    print("\n%s - Submitting for %s on task %s" %
          (to_time(timestamp), username, t_short), end='')
    browser = Browser()
    browser.set_handle_robots(False)
    step(LoginRequest(browser, username, "", base_url=base_url))
    step(SubmitRequest(browser,
                       (int(t_id), t_short),
                       filename=files[0],
                       base_url=base_url))


def token(timestamp, username, t_id, t_short, submission_num, base_url):
    """Execute the request for releasing test a submission.

    timestamp (int): seconds from the start.
    username (string): username issuing the submission.
    t_id (string): id of the task.
    t_short (string): short name of the task.
    submission_num (string): id of the submission to release test.
    base_url (string): http address of CWS.

    """
    print("\n%s - Playing token for %s on task %s" %
          (to_time(timestamp), username, t_short), end='')
    browser = Browser()
    browser.set_handle_robots(False)
    step(LoginRequest(browser, username, "", base_url=base_url))
    step(TokenRequest(browser,
                      (int(t_id), t_short),
                      submission_num=submission_num,
                      base_url=base_url))


def replay(base_url, source="./source.txt", start_from=None):
    """Start replaying the events in source on the CWS at the
    specified address.

    base_url (string): http address of CWS.
    source (string): events file.

    """
    global start, speed, old_speed

    content = [x.strip().split() for x in
               io.open(source, "rt", encoding="utf-8").readlines()]
    events = len(content)
    index = 0
    if start_from is not None:
        while index < events and float(content[index][0]) < start_from:
            index += 1
        start = time.time() - start_from
    else:
        start = time.time()

    while index < events:
        next_time = float(content[index][0])
        start, speed, old_speed = recompute_start(start, speed, old_speed)
        to_wait = (next_time / speed - (time.time() - start))
        while to_wait > .5:
            time.sleep(.5)
            start, speed, old_speed = recompute_start(start, speed, old_speed)
            to_wait = (next_time / speed - (time.time() - start))
        if to_wait > 0:
            time.sleep(to_wait)
        start, speed, old_speed = recompute_start(start, speed, old_speed)

        if content[index][4] == "submit":
            submit(timestamp=next_time,
                   username=content[index][1],
                   t_id=content[index][2],
                   t_short=content[index][3],
                   files=content[index][5].split(","),
                   base_url=base_url)
        elif content[index][4] == "token":
            token(timestamp=next_time,
                  username=content[index][1],
                  t_id=content[index][2],
                  t_short=content[index][3],
                  submission_num=int(content[index][5]),
                  base_url=base_url)

        index += 1


def main():
    """Main routine for replaying a contest, handling arguments from
    command line, and managing the speed of the replayer.

    """
    global start, speed, old_speed

    parser = ArgumentParser(description="Replay a contest.")
    parser.add_argument("address", action="store", type=utf8_decoder,
                        default="http://127.0.0.1:8888",
                        help="http address of CWS")
    parser.add_argument("source", action="store", type=utf8_decoder,
                        help="events file")
    parser.add_argument("-r", "--resume", action="store", type=utf8_decoder,
                        help="start from (%%H:%%M:%%S)")
    args = parser.parse_args()
    start_from = None
    if args.resume is not None:
        try:
            start_from = int(args.resume[6:8]) + \
                int(args.resume[3:5]) * 60 + \
                int(args.resume[0:2]) * 3600
        except:
            print("Invalid resume time %s, format is %%H:%%M:%%S" %
                  args.resume)

    thread = Thread(target=replay,
                    args=(args.address, args.source, start_from))
    thread.start()
    print("Wait for data to load...")
    while start is None:
        time.sleep(1)
    while thread.isAlive():
        command = raw_input("\nWrite the speed multiplier "
                            "(time %s, multiplier %s): " %
                            (to_time((time.time() - start) * speed), speed))
        try:
            command = int(command)
        except ValueError:
            print("Speed multiplier could not be parsed.")
        else:
            start, speed, old_speed = \
                recompute_start(start, command, old_speed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
