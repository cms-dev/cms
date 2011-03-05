#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2011 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2011 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2011 Matteo Boscariol <boscarim@hotmail.com>
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

import sys
import os

import CouchObject
import Utils
import FileStorageLib

def main():
    if len(sys.argv) < 2:
        print "Use: %s dir [contest]"
        sys.exit(1)
    c = Utils.ask_for_contest(skip = 1)
    spool_dir = sys.argv[1]
    try:
        os.mkdir(spool_dir)
    except OSError:
        print "The specified directory already exists, I won't overwrite it"
        sys.exit(1)
    queue_file = open(os.path.join(spool_dir, "queue"), 'w')
    upload_dir = os.path.join(spool_dir, "upload")
    os.mkdir(upload_dir)

    fsl = FileStorageLib.FileStorageLib()

    for user in c.users:
        user_dir = os.path.join(upload_dir, user.username)
        os.mkdir(user_dir)

    for submission in c.submissions:
        print "Exporting submission %s" % (submission.couch_id)
        username = submission.user.username
        task = submission.task.name
        timestamp = int(submission.timestamp)
        checked, language = submission.verify_source()
        if not checked:
            print "Could not verify language for submission %s, dropping it" % (submission.couch_id)
            continue
        user_dir = os.path.join(upload_dir, username)

        file_digest = submission.files["%s.%s" % (task, language)]
        upload_filename = os.path.join(user_dir, "%s.%d.%s" % (task, timestamp, language))
        fsl.get(file_digest, upload_filename)
        upload_filename = os.path.join(user_dir, "%s.%s" % (task, language))
        fsl.get(file_digest, upload_filename)
        print >> queue_file, "./upload/%s/%s.%d.%s" % (username, task, timestamp, language)

        if submission.evaluation_outcome != None:
            res_file = open(os.path.join(spool_dir, "%d.%s.%s.%s.res" % (timestamp, username, task, language)), 'w')
            res2_file = open(os.path.join(spool_dir, "%s.%s.%s.res" % (username, task, language)), 'w')
            sum = 0.0
            for num in xrange(len(submission.evaluation_outcome)):
                sum += submission.evaluation_outcome[num]
                line = "Executing on file n. %2d %s (%.4f)" % (num, submission.evaluation_text[num],
                                                               submission.evaluation_outcome[num])
                print >> res_file, line
                print >> res2_file, line
            line = "Score: %.6f" % (sum)
            print >> res_file, line
            print >> res2_file, line
            res_file.close()
            res2_file.close()

    print >> queue_file
    queue_file.close()

if __name__ == "__main__":
    main()
