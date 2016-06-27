#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015-2016 William Di Luigi <williamdiluigi@gmail.com>
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

from cms import utf8_decoder, LANG_C, LANG_CPP, LANG_JAVA, LANG_PASCAL, \
    LANG_PHP, LANG_PYTHON
from cms.db import Dataset, File, FSObject, Participation, SessionGen, \
    Submission, SubmissionResult, Task, User


logger = logging.getLogger(__name__)


_RAW_TEMPLATE_DATA = """
* user:  %s
* fname: %s
* lname: %s
* task:  %s
* score: %s
* date:  %s
"""


TEMPLATE = {
    LANG_C: "/**%s*/\n" % _RAW_TEMPLATE_DATA,
    LANG_PASCAL: "(**%s*)\n" % _RAW_TEMPLATE_DATA,
    LANG_PYTHON: "\"\"\"%s\"\"\"\n" % _RAW_TEMPLATE_DATA,
    LANG_PHP: "<?php\n/**%s*/\n?>" % _RAW_TEMPLATE_DATA,
}
TEMPLATE[LANG_CPP] = TEMPLATE[LANG_C]
TEMPLATE[LANG_JAVA] = TEMPLATE[LANG_C]


def filter_top_scoring(results, unique):
    """Filter results keeping only the top scoring submissions for each user
    and task

    results ([Submission]): the starting list of submissions
    unique (bool): if True, keep only the first top-scoring submission

    return ([Submission]): the filtered submissions

    """
    usertask = {}
    for row in results:
        key = (row[6], row[10])  # u_id, t_id
        value = (-row[3], row[2], row)  # sr_score, s_timestamp
        if unique:
            if key not in usertask or usertask[key][0] > value:
                usertask[key] = [value]
        else:
            if key not in usertask or usertask[key][0][0] > value[0]:
                usertask[key] = [value]
            elif usertask[key][0][0] == value[0]:
                usertask[key].append(value)

    results = []
    for key, values in usertask.iteritems():
        for value in values:
            results.append(value[2])  # the "old" row

    return results


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
    parser.add_argument("--utf8", action="store_true",
                        help="if set, the files will be encoded in utf8"
                             " when possible")
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

    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--unique", action="store_true",
                       help="if set, only the earliest best submission"
                            " will be exported for each (user, task)")
    group.add_argument("--best", action="store_true",
                       help="if set, only the best submissions will be"
                            " exported for each (user, task)")

    args = parser.parse_args()

    if args.add_info and not args.utf8:
        logger.critical("If --add-info is specified, then --utf8 must be"
                        " specified as well.")
        sys.exit(1)

    if not os.path.exists(args.output_dir):
        os.mkdir(args.output_dir)
    if not os.path.isdir(args.output_dir):
        logger.critical("The output-dir parameter must point to a directory")
        sys.exit(1)

    with SessionGen() as session:
        q = session.query(Submission)\
            .join(Submission.task)\
            .join(Submission.files)\
            .join(Submission.results)\
            .join(SubmissionResult.dataset)\
            .join(Submission.participation)\
            .join(Participation.user)\
            .filter(Dataset.id == Task.active_dataset_id)\
            .filter(SubmissionResult.score >= args.min_score)\
            .with_entities(Submission.id, Submission.language,
                           Submission.timestamp,
                           SubmissionResult.score,
                           File.filename, File.digest,
                           User.id, User.username, User.first_name,
                           User.last_name,
                           Task.id, Task.name)

        if args.contest_id:
            q = q.filter(Participation.contest_id == args.contest_id)

        if args.task_id:
            q = q.filter(Submission.task_id == args.task_id)

        if args.user_id:
            q = q.filter(Participation.user_id == args.user_id)

        if args.submission_id:
            q = q.filter(Submission.id == args.submission_id)

        results = q.all()

        if args.unique or args.best:
            results = filter_top_scoring(results, args.unique)

        print("%s file(s) will be created." % len(results))
        if raw_input("Continue? [Y/n] ").lower() not in ["y", ""]:
            sys.exit(0)

        done = 0
        for row in results:
            s_id, s_language, s_timestamp, sr_score, f_filename, f_digest, \
                u_id, u_name, u_fname, u_lname, t_id, t_name = row

            name = f_filename
            if name.endswith(".%l"):
                name = name[:-3]  # remove last 3 chars

            filename = args.filename.format(id=s_id, name=name, ext=s_language,
                                            time=s_timestamp, user=u_name)
            filename = os.path.join(args.output_dir, filename)
            if os.path.exists(filename):
                logger.warning("Skipping file '%s' because it already exists",
                               filename)

            fso = FSObject.get_from_digest(f_digest, session)
            assert fso is not None
            with fso.get_lobject(mode="rb") as file_obj:
                data = file_obj.read()

                if args.utf8:
                    try:
                        data = utf8_decoder(data)
                    except TypeError:
                        logger.critical("Could not guess encoding of file "
                                        "'%s'. Aborting.",
                                        filename)
                        sys.exit(1)

                    if args.add_info:
                        data = TEMPLATE[s_language] % (
                            u_name,
                            u_fname,
                            u_lname,
                            t_name,
                            sr_score,
                            s_timestamp
                        ) + data

                    # Print utf8-encoded, possibly altered data
                    with codecs.open(filename, "w", encoding="utf-8") as f_out:
                        f_out.write(data)
                else:
                    # Print raw, untouched binary data
                    with open(filename, "wb") as f_out:
                        f_out.write(data)

            done += 1
            print(done, "/", len(results))


if __name__ == "__main__":
    sys.exit(main())
