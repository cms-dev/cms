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
ReplayContest takes as input a contest exported with ContestExported
(in the extracted form), and replays the contest, meaning that it asks
CWS for all submissions and tokens asked by the contestants, at the
right timing. The time can be increased in order to stress-test CMS.

TODO:
- currently only works with tasks with one file per submission (this
  is a limitation of SubmitRequest).
- implement handling of user tests.
- handle KeyboardInterrupt and notify of the correct commandline to
  resume the contest.
- set the correct parameters for the contest and tasks automatically.
- use a nicer graphics (ncurses based?).

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import io
import os
import shutil
import json
import sys
import tempfile
import time

from argparse import ArgumentParser
from mechanize import Browser
from threading import Thread, RLock

from cms import config, logger, utf8_decoder
from cmscontrib.ContestImporter import ContestImporter
from cmstestsuite.web.CWSRequests import \
    LoginRequest, SubmitRequest, TokenRequest


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


def step(request):
    """Prepare and execute the request in a single instruction.

    request (GenericRequest): some request to *WS.

    """
    request.prepare()
    request.execute()


class ContestReplayer(object):

    def __init__(self, import_source, cws_address, no_import=False,
                 start_from=0):
        self.import_source = import_source
        self.cws_address = cws_address
        self.no_import = no_import
        self.start_from = start_from

        self.start = None
        self.speed = 1
        self.speed_lock = RLock()
        self.events = []

        self.importer = ContestImporter(drop=False,
                                        import_source=import_source,
                                        only_files=False, no_files=False,
                                        no_submissions=True)

    def run(self):
        """Main routine for replaying a contest, handling arguments from
        command line, and managing the speed of the replayer.

        """
        if not self.no_import:
            logger.info("Importing contest...")
            self.importer.run()
            logger.info("Contest imported.")

        logger.info("Please run CMS against the contest (with ip_lock=False).")
        logger.info("Please ensure that:")
        logger.info("- the contest is active (we are between start and stop);")
        logger.info("- the minimum interval for submissions and usertests ")
        logger.info("  (contest- and task-wise) is None.")
        logger.info("Then press enter to start.")
        raw_input()

        with io.open(os.path.join(self.import_source, "contest.json"),
                     "rt", encoding="utf-8") as fin:
            self.compute_events(json.load(fin))

        thread = Thread(target=self.replay)
        thread.daemon = True
        thread.start()

        logger.info("Loading submission data...")
        while self.start is None:
            time.sleep(1)
        while thread.isAlive():
            new_speed = raw_input("Write the speed multiplier or q to quit "
                                  "(time %s, multiplier %s):\n" %
                                  (to_time((time.time() - self.start) *
                                           self.speed),
                                   self.speed))
            if new_speed == "q":
                return 0
            elif new_speed != "":
                try:
                    new_speed = int(new_speed)
                except ValueError:
                    logger.warning("Speed multiplier could not be parsed.")
                else:
                    self.recompute_start(new_speed)
        return 0

    def compute_events(self, contest):
        tasks = dict((task["name"], task["num"]) for task in contest["tasks"])
        for user in contest["users"]:
            tasks_num = dict((task["name"], 1) for task in contest["tasks"])
            for submission in sorted(user["submissions"],
                                     key=lambda x: x["timestamp"]):
                num = tasks_num[submission["task"]]
                tasks_num[submission["task"]] += 1
                self.events.append([
                    submission["timestamp"] - contest["start"],
                    user["username"],
                    user["password"],
                    tasks[submission["task"]],
                    submission["task"],
                    "s",  # For submit events.
                    (submission["files"], submission["language"]),
                    ])
                if submission["token"] is not None:
                    self.events.append([
                        submission["token"]["timestamp"] - contest["start"],
                        user["username"],
                        user["password"],
                        tasks[submission["task"]],
                        submission["task"],
                        "t",  # For token events.
                        num,
                        ])
        # TODO: add user test events.
        self.events.sort()

    def recompute_start(self, new_speed):
        """Utility to recompute the start time of a contest passing
        from a speed of self.speed to a speed of new_speed.

        new_speed(int): the new speed for the contest replayer.

        """
        with self.speed_lock:
            if self.speed != new_speed:
                self.start = self.start \
                    + (time.time() - self.start) * (new_speed - self.speed) \
                    * 1.0 / new_speed
                self.speed = new_speed

    def submit(self, timestamp, username, password, t_id, t_short,
               files, language):
        """Execute the request for a submission.

        timestamp (int): seconds from the start.
        username (string): username issuing the submission.
        password (string): password of username.
        t_id (string): id of the task.
        t_short (string): short name of the task.
        files ([dict]): list of dictionaries with keys 'filename' and
                        'digest'.
        language (string): the extension the files should have.

        """
        logger.info("%s - Submitting for %s on task %s."
                    % (to_time(timestamp), username, t_short))
        if len(files) != 1:
            logger.error("We cannot submit more than one file.")
            return

        # Copying submission files into a temporary directory with the
        # correct name. Otherwise, SubmissionRequest does not know how
        # to interpret the file (and which language are they in).
        temp_dir = tempfile.mkdtemp(dir=config.temp_dir)
        for file_ in files:
            temp_filename = os.path.join(temp_dir,
                                         file_["filename"].replace("%l",
                                                                   language))
            shutil.copy(
                os.path.join(self.import_source, "files", files[0]["digest"]),
                temp_filename
                )
            file_["filename"] = temp_filename

        filename = os.path.join(files[0]["filename"])
        browser = Browser()
        browser.set_handle_robots(False)
        step(LoginRequest(browser, username, password,
                          base_url=self.cws_address))
        step(SubmitRequest(browser,
                           (int(t_id), t_short),
                           filename=filename,
                           base_url=self.cws_address))
        shutil.rmtree(temp_dir)

    def token(self, timestamp, username, password, t_id, t_short,
              submission_num):
        """Execute the request for releasing test a submission.

        timestamp (int): seconds from the start.
        username (string): username issuing the submission.
        password (string): password of username.
        t_id (string): id of the task.
        t_short (string): short name of the task.
        submission_num (string): id of the submission to release test.

        """
        logger.info("%s - Playing token for %s on task %s"
                    % (to_time(timestamp), username, t_short))
        browser = Browser()
        browser.set_handle_robots(False)
        step(LoginRequest(browser, username, password,
                          base_url=self.cws_address))
        step(TokenRequest(browser,
                          (int(t_id), t_short),
                          submission_num=submission_num,
                          base_url=self.cws_address))

    def replay(self):
        """Start replaying the events in source on the CWS at the
        specified address.

        """
        with self.speed_lock:
            index = 0
            if self.start_from is not None:
                while index < len(self.events) \
                        and float(self.events[index][0]) < self.start_from:
                    index += 1
                self.start = time.time() - self.start_from
            else:
                self.start = time.time()

        while index < len(self.events):
            timestamp, username, password, task_id, task_name, type_, data \
                = self.events[index]
            to_wait = (timestamp / self.speed - (time.time() - self.start))
            while to_wait > .5:
                if 0 < to_wait % 10 <= .5:
                    logger.info("Next event in %d seconds." % int(to_wait))
                time.sleep(.5)
                to_wait = (timestamp / self.speed - (time.time() - self.start))
            if to_wait > 0:
                time.sleep(to_wait)

            if type_ == "s":  # Submit.
                files, language = data
                self.submit(timestamp=timestamp,
                            username=username,
                            password=password,
                            t_id=task_id,
                            t_short=task_name,
                            files=files,
                            language=language)
            elif type_ == "t":  # Token.
                self.token(timestamp=timestamp,
                           username=username,
                           password=password,
                           t_id=task_id,
                           t_short=task_name,
                           submission_num=data)
            else:
                logger.warning("Unexpected type `%s', ignoring." % type_)

            index += 1


def main():
    parser = ArgumentParser(description="Replayer of CMS contests.")
    parser.add_argument("cws_address", action="store", type=utf8_decoder,
                        default="http://127.0.0.1:8888",
                        help="http address of CWS")
    parser.add_argument("import_source", action="store", type=utf8_decoder,
                        help="source directory or compressed file")
    parser.add_argument("-i", "--no-import", action="store_true",
                        help="assume the contest is already in the database")
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
            logger.critical("Invalid resume time %s, format is %%H:%%M:%%S"
                            % args.resume)
            return 1

    if not os.path.isdir(args.import_source):
        logger.critical("Please extract the contest "
                        "before using ReplayContest.")
        return 1

    ContestReplayer(
        import_source=args.import_source,
        no_import=args.no_import,
        start_from=start_from,
        cws_address=args.cws_address
        ).run()

    return 0


if __name__ == "__main__":
    sys.exit(main())
