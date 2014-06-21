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

"""Create a events file (almost) in the format of ReplayContest from a
filesystem tree. Almost mean that the column containing the task_id is
not included because there is no way this script is able to know
that. Task ids must be filled by hand int the events file after being
imported in CMS.

Let / be the root of the tree in the filesystem, then there are:
* directories /<task_short_name> (not starting with "test_")
* directories /<task_short_name>/<username>
* files /<task_short_name>/<username>/<s_id>.data
* files /<task_short_name>/<username>/<s_id>.zip

In the data file, there are one or two lines. The first line is the
timestamp of the submission in the format %H:%M:%S, the second line
(if present) is the timestamp of the token used on that submission.

The zip file contains all files submitted.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import io
import os
import shutil
import sys
import zipfile

from argparse import ArgumentParser
from glob import glob

from cms import utf8_decoder


def to_timestamp(time_tuple):
    """Translate a tuple (H, M, S) in a timestamp.

    time_tuple ((int)): time formatted as (H, M, S).

    return (int): the corresponding timestamp.

    """
    return time_tuple[2] + \
        time_tuple[1] * 60 + \
        time_tuple[0] * 3600


def main():
    """Main routine for translating. Manage command line arguments and
    walk around the filesystem building the events file.

    """
    parser = ArgumentParser(
        description="Translate from a filesystem format to the Replay format.")
    parser.add_argument("source", action="store", type=utf8_decoder,
                        help="source directory")
    args = parser.parse_args()

    all_events = []

    tasks_short = [os.path.basename(x)
                   for x in glob("%s/*" % args.source)
                   if not os.path.basename(x).startswith("test_")]
    for t_short in tasks_short:
        print(t_short, file=sys.stderr)
        users = [os.path.basename(x)
                 for x in glob("%s/%s/*" % (args.source, t_short))
                 if len(os.path.basename(x)) == 4]
        for user in users:
            userdir = "%s/%s/%s" % (args.source, t_short, user)
            submission_nums = []
            submissions = [os.path.splitext(os.path.basename(x))[0]
                           for x in glob("%s/*.data" % userdir)]
            for sid in submissions:
                content = io.open("%s/%s.data" % (userdir, sid),
                                  "rt", encoding="utf-8").readlines()
                submit = to_timestamp(
                    [int(x)
                     for x in content[0].strip().split()[1].split(":")])

                token = None
                if len(content) >= 2:
                    token = to_timestamp(
                        [int(x)
                         for x in content[1].strip().split()[1].split(":")])

                zip_file = zipfile.ZipFile("%s/%s.zip" % (userdir, sid))
                try:
                    [filename] = [x for x in zip_file.filelist
                                  if x.filename.startswith(t_short + ".")]
                except ValueError:
                    filename = zip_file.filelist[0]
                filename = filename.filename
                extracted = zip_file.extract(filename, "/tmp/")
                _, ext = os.path.splitext(extracted)
                newname = "%s/%s%s" % (userdir, sid, ext)
                shutil.move("/tmp/%s" % filename, newname)

                submission_nums.append((submit, sid, token, newname))

            submission_nums.sort()
            for i, (timestamp, sid, token, filename) \
                    in enumerate(submission_nums):
                all_events.append((timestamp,
                                   user,
                                   t_short,
                                   "submit",
                                   filename))
                if token is not None:
                    all_events.append((timestamp,
                                       user,
                                       t_short,
                                       "token",
                                       i + 1))

    all_events.sort()
    for event in all_events:
        print(" ".join(["%s" % x for x in event]))

    return 0


if __name__ == "__main__":
    sys.exit(main())
