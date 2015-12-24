#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015 William Di Luigi <williamdiluigi@gmail.com>
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

"""Utility to export submissions to a folder.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import logging
import os
import sys
import codecs

from cms import utf8_decoder
from cms.db import Dataset, File, FSObject, Participation, SessionGen, \
    Submission, SubmissionResult, Task, User

logger = logging.getLogger(__name__)

TEMPLATE = {
    "c": """/**
* user:  %s
* fname: %s
* lname: %s
* task:  %s
* score: %s
* date:  %s
*/
""",
    "pas": """(**
* user:  %s
* fname: %s
* lname: %s
* task:  %s
* score: %s
* date:  %s
*)
"""
}
TEMPLATE["cpp"] = TEMPLATE["c"]


def main():
    """Parse arguments and launch process.

    """
    parser = argparse.ArgumentParser(
        description="Export CMS submissions to a folder.")
    parser.add_argument("-c", "--contest-id", action="store", type=int,
                        help="id of contest (default: all contests)")
    parser.add_argument("-t", "--task-id", action="store", type=int,
                        help="id of task (default: all tasks)")
    parser.add_argument("-u", "--user-id", action="store", type=int,
                        help="id of user (default: all users)")
    parser.add_argument("-s", "--submission-id", action="store", type=int,
                        help="id of submission (default: all submissions)")
    parser.add_argument("--unique", action="store_true",
                        help="if set, only the earliest best submission"
                             " will be exported for each (user, task)")
    parser.add_argument("--best", action="store_true",
                        help="if set, only the best submissions will be"
                             " exported for each (user, task)")
    parser.add_argument("--add-info", action="store_true",
                        help="if set, information on the submission will"
                             " be added in the first lines of each file")
    parser.add_argument("--min-score", action="store", type=float,
                        help="ignore submissions which scored strictly"
                             " less than this (default: 0.0)",
                        default=0.0)
    parser.add_argument("--filename", action="store", type=utf8_decoder,
                        help="the filename format to use"
                             " (default: {id}.{name}.{ext})",
                        default="{id}.{name}.{ext}")
    parser.add_argument("output_dir", action="store", type=utf8_decoder,
                        help="directory where to save the submissions")

    args = parser.parse_args()

    if args.best and args.unique:
        logger.critical("The --best and --unique arguments are not compatible")
        sys.exit(1)

    if not os.path.exists(args.output_dir):
        os.mkdir(args.output_dir)
    if not os.path.isdir(args.output_dir):
        logger.critical("The output-dir parameter must point to a directory")
        sys.exit(1)

    with SessionGen() as session:
        q = session.query(
            Submission.id,
            Submission.language,
            Submission.timestamp,
            SubmissionResult.score,
            File.filename,
            File.digest,
            User.id,
            User.username,
            User.first_name,
            User.last_name,
            Task.id,
            Task.name
        ).join(
            Submission.participation
        ).join(
            Participation.user
        ).join(
            SubmissionResult.dataset
        ).join(
            Submission.task
        ).filter(
            Dataset.id == Task.active_dataset_id
        ).filter(
            File.submission_id == Submission.id
        ).filter(
            SubmissionResult.submission_id == Submission.id
        ).filter(
            SubmissionResult.score >= args.min_score
        )

        if args.contest_id:
            q = q.filter(Participation.contest_id == args.contest_id)

        if args.task_id:
            q = q.filter(Submission.task_id == args.task_id)

        if args.user_id:
            q = q.filter(Participation.user_id == args.user_id)

        if args.submission_id:
            q = q.filter(Submission.id == args.submission_id)

        result = q.all()

        if args.unique or args.best:
            # FIXME: this can be probably rewritten in SQL
            usertask = {}
            for row in result:
                key = (row[6], row[10])  # u_id, t_id
                value = (-row[3], row[2], row)  # sr_score, s_timestamp
                if args.unique:
                    if key not in usertask or usertask[key] > value:
                        usertask[key] = value
                else:
                    if key not in usertask or usertask[key][0][0] > value[0]:
                        usertask[key] = [value]
                    elif usertask[key][0][0] == value[0]:
                        usertask[key].append(value)

            result = []
            for key, value in usertask.iteritems():
                if args.unique:
                    result.append(value[2])  # the "old" row
                else:
                    for v in value:
                        result.append(v[2])  # the "old" row

        print(str(len(result)) + " file(s) will be copied.")
        if raw_input("Continue? [Y/n] ").lower() not in ["y", ""]:
            exit(0)

        done = 0
        for row in result:
            s_id, s_language, s_timestamp, sr_score, f_filename, f_digest, \
                u_id, u_name, u_fname, u_lname, t_id, t_name = row

            name = f_filename
            if name.endswith(".%l"):
                name = name[:-3]  # remove last 3 chars

            filename = args.filename.format(id=s_id, name=name, ext=s_language)
            filename = os.path.join(args.output_dir, filename)
            if os.path.exists(filename):
                logger.warning("Skipping file '%s' because it already exists",
                               filename)

            fso = FSObject.get_from_digest(f_digest, session)
            assert fso is not None
            with fso.get_lobject(mode="rb") as file_obj:
                data = file_obj.read().decode('latin-1')

                if args.add_info:
                    data = TEMPLATE[s_language] % (
                        u_name,
                        u_fname,
                        u_lname,
                        t_name,
                        sr_score,
                        s_timestamp
                    ) + "\n" + data

                with codecs.open(filename, "w", encoding="utf-8") as file_out:
                    file_out.write(data)

            done += 1
            print(done, "/", len(result))
