#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2017 Peyman Jabbarzade Ganje <peyman.jabarzade@gmail.com>
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

"""Utility to remove a contest.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import os
import sys
import logging
import time
import tempfile
import shutil

from cms import config, utf8_decoder
from cms.db import Contest, Task, Submission, SessionGen,\
    File, ask_for_contest, FSObject
from cmstestsuite import Browser
from cmstestsuite.web.CWSRequests import \
    LoginRequest, SubmitRequest


logger = logging.getLogger(__name__)
NUMBER_OF_SUBMISSION_IN_RAM = 100


# TODO: filter(, usertest, token)
def to_time(seconds):
    hours = seconds // 3600
    minutes = seconds // 60 % 60
    seconds = seconds % 60
    return "%02d:%02d:%02d" % (hours, minutes, seconds)


def submit(timestamp, username, password, t_id, t_short,
           files, language, session, cws_address):
    """Execute the request for a submission.

    timestamp (int): seconds from the start.
    username (string): username issuing the submission.
    password (string): password of username.
    t_id (string): id of the task.
    t_short (string): short name of the task.
    files ([dict]): list of files.
    language (string): the extension the files should have.
    cws_address (string): http address of CWS.
    """
    logger.info("%s - Submitting for %s on task %s.",
                to_time(timestamp), username, t_short)

    # Copying submission files into a temporary directory with the
    # correct name. Otherwise, SubmissionRequest does not know how
    # to interpret the file (and which language are they in).
    temp_dir = tempfile.mkdtemp(dir=config.temp_dir)
    file_name = []
    submission_format = []
    for file_ in files:
        name = file_.filename
        filename = os.path.join(temp_dir,
                                name)
        fso = FSObject.get_from_digest(file_.digest, session)
        assert fso is not None
        with fso.get_lobject(mode="rb") as file_obj:
            data = file_obj.read()
            with open(filename, "wb") as f_out:
                f_out.write(data)
        file_name.append(filename)
        submission_format.append(name)

    browser = Browser()
    lr = LoginRequest(browser, username, password,
                      base_url=cws_address)
    browser.login(lr)
    SubmitRequest(browser=browser,
                  task=(int(t_id), t_short),
                  submission_format=submission_format,
                  filenames=file_name,
                  language=language,
                  base_url=cws_address).execute()
    shutil.rmtree(temp_dir)


def convert_to_float(time):
    h, m, s = str(time).split(':')
    return float(h)*3600 + float(m)*60 + float(s)


def replay_contest(contest_id, start_from, duration, cws_address,
                   speed, task_id, user_id, submission_id):
    with SessionGen() as session:
        contest = session.query(Contest)\
            .filter(Contest.id == contest_id).first()
        if not contest:
            print("No contest with id %s found." % contest_id)
            return False
        valid_submission = session.query(Submission).join(Task)\
            .filter(Task.contest == contest)
        if task_id is not None:
            valid_submission = valid_submission.filter(Task.id == task_id)
        if user_id is not None:
            valid_submission = valid_submission.\
                filter(Submission.participation_id == user_id)
        if submission_id is not None:
            valid_submission = valid_submission.\
                filter(Submission.id == submission_id)
        submissions_number = valid_submission.count()

        start = None
        for index in range(submissions_number):
            ind = index % NUMBER_OF_SUBMISSION_IN_RAM
            if ind == 0:
                if __name__ == '__main__':
                    submissions = valid_submission.\
                        order_by(Submission.timestamp).\
                        slice(index, index + NUMBER_OF_SUBMISSION_IN_RAM)
            timestamp = convert_to_float(
                submissions[ind].timestamp - contest.start)
            if start_from is not None and timestamp < start_from:
                continue
            end_time = duration
            if start_from is not None:
                end_time += start_from
            if duration is not None and timestamp > end_time:
                break
            if start is None:
                if start_from is not None:
                    start = time.time() - start_from
                else:
                    start = time.time()
            username = submissions[ind].participation.user.username
            if submissions[ind].participation.password is not None:
                password = submissions[ind].participation.password[10:]
            elif submissions[ind].participation.user.password is not None:
                password = submissions[ind].participation.user.password[10:]
            else:
                password = ""
            task = submissions[ind].task
            files = session.query(File)\
                .filter(File.submission == submissions[ind]).all()
            language = submissions[ind].language

            to_wait = (timestamp / speed - (time.time() - start))
            while to_wait > .5:
                if 0 < to_wait % 10 <= .5:
                    logger.info("Next event in %d seconds.", to_wait)
                time.sleep(.5)
                to_wait = (timestamp / speed - (time.time() - start))
            if to_wait > 0:
                time.sleep(to_wait)

            submit(timestamp=timestamp,
                   username=username,
                   password=password,
                   t_id=task.id,
                   t_short=task.name,
                   files=files,
                   language=language,
                   session=session,
                   cws_address=cws_address)

        print("Replay of contest %s finished." % contest.name)
    return True


def main():
    """Parse arguments and launch process.

    """
    parser = argparse.ArgumentParser(
        description="Replay a contest in CMS.")
    parser.add_argument("-c", "--contest-id", action="store", type=int,
                        help="id of the contest")
    parser.add_argument("-t", "--task-id", action="store", type=int,
                        help="id of task (default: all tasks)")
    parser.add_argument("-u", "--user-id", action="store", type=int,
                        help="id of user (default: all users)")
    parser.add_argument("-sid", "--submission-id", action="store", type=int,
                        help="id of submission (default: all submissions)")
    parser.add_argument("--cws_address", action="store", type=utf8_decoder,
                        default="http://127.0.0.1:8888",
                        help="http address of CWS")
    parser.add_argument("-r", "--resume", action="store", type=utf8_decoder,
                        help="start from (%%H:%%M:%%S)")
    parser.add_argument("-d", "--duration", action="store", type=utf8_decoder,
                        help="duration is (%%H:%%M:%%S)")
    parser.add_argument("-s", "--speed", action="store", type=int, default=1,
                        help="speed of replaying")
    args = parser.parse_args()
    if args.contest_id is None:
        args.contest_id = ask_for_contest()
    start_from = None
    if args.resume is not None:
        try:
            start_from = int(args.resume[6:8]) + \
                         int(args.resume[3:5]) * 60 + \
                         int(args.resume[0:2]) * 3600
        except:
            msg = "Invalid resume time %s, format is %%H:%%M:%%S" % args.resume
            logger.critical(msg)
            return 1

    duration = None
    if args.duration is not None:
        try:
            duration = int(args.duration[6:8]) + \
                         int(args.duration[3:5]) * 60 + \
                         int(args.duration[0:2]) * 3600
        except:
            msg = "Invalid duration %s, format is %%H:%%M:%%S" % args.duration
            logger.critical(msg)
            return 1

    success = replay_contest(contest_id=args.contest_id, start_from=start_from,
                             duration=duration, cws_address=args.cws_address,
                             speed=args.speed, task_id=args.task_id,
                             user_id=args.user_id,
                             submission_id=args.submission_id)
    return 0 if success is True else 1


if __name__ == "__main__":
    sys.exit(main())
