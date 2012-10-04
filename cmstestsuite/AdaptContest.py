#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
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


# The file source has rows with these data, space separated:
# timestamp (relative to the contest)
# username
# task_id
# task_shortname
# action (submit|release)

# Next, for submit:
# comma-separated list of file paths

# For token:
# submission_num

import os
import shutil
import sys
import zipfile

from argparse import ArgumentParser
from glob import glob


def to_timestamp(l):
    return l[2] + l[1] * 60 + l[0] * 3600

def main():
    parser = ArgumentParser(
        description="Translate from a filesystem format to the Replay format.")
    parser.add_argument("source", type=str, help="source directory")
    args = parser.parse_args()

    all_events = []

    tasks_short = [os.path.basename(x)
                   for x in glob("%s/*" % args.source)
                   if not os.path.basename(x).startswith("test_")]
    for t_short in tasks_short:
        print >> sys.stderr, t_short
        users = [os.path.basename(x)
                 for x in glob("%s/%s/*" % (args.source, t_short))
                 if len(os.path.basename(x)) == 4]
        for user in users:
            userdir = "%s/%s/%s" % (args.source, t_short, user)
            submission_nums = []
            submissions = [os.path.splitext(os.path.basename(x))[0]
                           for x in glob("%s/*.data" % userdir)]
            for sid in submissions:
                content = open("%s/%s.data" % (userdir, sid)).readlines()
                submit = to_timestamp(
                    [int(x)
                     for x in content[0].strip().split()[1].split(":")])

                token = None
                if len(content) >= 2:
                    token = to_timestamp(
                        [int(x)
                         for x in content[1].strip().split()[1].split(":")])

                z = zipfile.ZipFile("%s/%s.zip" % (userdir, sid))
                filename = z.filelist[0].filename
                extracted = z.extract(filename, "/tmp/")
                base, ext = os.path.splitext(extracted)
                newname = "%s/%s%s" % (userdir, sid, ext)
                shutil.move("/tmp/%s" % filename, newname)

                submission_nums.append((submit, sid, token, newname))

            submission_nums.sort()
            for i, (timestamp, sid, token, filename) in enumerate(submission_nums):
                all_events.append((timestamp, user, t_short, "submit", filename))
                if token is not None:
                    all_events.append((timestamp, user, t_short, "token", i + 1))

    all_events.sort()
    for event in all_events:
        print " ".join([str(x) for x in event])


    return 0

if __name__ == "__main__":
    sys.exit(main())
