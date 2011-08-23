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
import codecs
import optparse

from cms.async.AsyncLibrary import Service, logger
from cms.async import ServiceCoord
from cms.service.FileStorage import FileCacher

from cms.db.SQLAlchemyAll import SessionGen, Contest
from cms.db.Utils import ask_for_contest

class SpoolExporter(Service):

    def __init__(self, shard, contest_id, spool_dir):
        self.contest_id = contest_id
        self.spool_dir = spool_dir

        logger.initialize(ServiceCoord("SpoolExporter", shard))
        logger.debug("SpoolExporter.__init__")
        Service.__init__(self, shard)
        self.FS = self.connect_to(
            ServiceCoord("FileStorage", 0))
        if not self.FS.connected:
            logger.error("Please run the FileStorage service.")
            self.exit()
        self.FC = FileCacher(self, self.FS)


    def do_export(self):
        logger.operation = "exporting contest %d" % (self.contest_id)
        logger.info("Starting export")

        logger.info("Creating dir structure")
        try:
            os.mkdir(self.spool_dir)
        except OSError:
            logger.error("The specified directory already exists, I won't overwrite it")
            sys.exit(1)
        queue_file = codecs.open(os.path.join(self.spool_dir, "queue"), 'w', encoding='utf-8')
        upload_dir = os.path.join(self.spool_dir, "upload")
        os.mkdir(upload_dir)

        with SessionGen() as session:

            c = Contest.get_from_id(self.contest_id, session)

            hidden_users = []
            for user in c.users:
                if not user.hidden:
                    user_dir = os.path.join(upload_dir, user.username)
                    os.mkdir(user_dir)
                else:
                    hidden_users.append(user.username)

            # FIXME - The enumeration of submission should be time-increasing
            for submission in c.get_submissions():
                if submission.user.hidden:
                    continue
                logger.info("Exporting submission %s" % (submission.id))
                username = submission.user.username
                task = submission.task.name
                timestamp = int(submission.timestamp)
                checked, language = submission.verify_source()
                if not checked:
                    logger.warning("Could not verify language for submission %s, dropping it" % (submission.id))
                    continue
                user_dir = os.path.join(upload_dir, username)

                file_digest = submission.files["%s.%s" % (task, language)].digest
                upload_filename = os.path.join(user_dir, "%s.%d.%s" % (task, timestamp, language))
                self.FC.get_file_to_path(file_digest, upload_filename, sync=True)
                upload_filename = os.path.join(user_dir, "%s.%s" % (task, language))
                self.FC.get_file_to_path(file_digest, upload_filename, sync=True)
                print >> queue_file, "./upload/%s/%s.%d.%s" % (username, task, timestamp, language)

                if submission.evaluations != []:
                    res_file = codecs.open(os.path.join(self.spool_dir, "%d.%s.%s.%s.res" % (timestamp, username, task, language)), 'w', encoding='utf-8')
                    res2_file = codecs.open(os.path.join(self.spool_dir, "%s.%s.%s.res" % (username, task, language)), 'w', encoding='utf-8')
                    total = 0.0
                    for num, evaluation in enumerate(submission.evaluations):
                        outcome = float(evaluation.outcome)
                        total += outcome
                        line = "Executing on file n. %2d %s (%.4f)" % (num, evaluation.text, outcome)
                        print >> res_file, line
                        print >> res2_file, line
                    line = "Score: %.6f" % (total)
                    print >> res_file, line
                    print >> res2_file, line
                    res_file.close()
                    res2_file.close()

            print >> queue_file
            queue_file.close()

            logger.info("Exporting ranking")
            ranking_file = codecs.open(os.path.join(self.spool_dir, "classifica.txt"), 'w', encoding='utf-8')
            ranking_csv = codecs.open(os.path.join(self.spool_dir, "classifica.csv"), 'w', encoding='utf-8')
            print >> ranking_file, "Classifica finale del contest `%s'" % (c.description)
            users = {}
            for u in c.users:
                if u.username not in hidden_users:
                    users[u.username] = [0, u.username, [None]*len(c.tasks)]
            for (username, task_num), score in c.ranking_view.scores.iteritems():
                if username not in hidden_users:
                    users[username][0] += score.score
                    users[username][2][task_num] = score.score
            users = users.values()
            users.sort(reverse=True)
            print >> ranking_file, ("%20s %10s" + " %10s" * len(c.tasks)) % (("Utente", "Totale") + tuple([t.name for t in c.tasks]))
            print >> ranking_csv, ("%s,%s" + ",%s" * len(c.tasks)) % (("utente", "totale") + tuple([t.name for t in c.tasks]))
            for total, user, problems in users:
                print >> ranking_file, ("%20s %10.3f" + " %10.3f" * len(c.tasks)) % ((user, total) + tuple(problems))
                print >> ranking_csv, ("%s,%.6f" + ",%.6f" * len(c.tasks)) % ((user, total) + tuple(problems))
            ranking_file.close()
            ranking_csv.close()

            logger.info("Export finished")
            logger.operation = ""

def main():
    parser = optparse.OptionParser(usage="usage: %prog [options] contest_dir")
    parser.add_option("-c", "--contest", help="contest ID to export",
                      dest="contest_id", action="store", type="int", default=None)
    parser.add_option("-s", "--shard", help="service shard number",
                      dest="shard", action="store", type="int", default=None)
    options, args = parser.parse_args()
    if len(args) != 1:
        parser.error("I need exactly one parameter, the directory where to export the contest")
    if options.shard is None:
        parser.error("The `-s' option is mandatory!")

    if options.contest_id is None:
        options.contest_id = ask_for_contest()

    spool_exporter = SpoolExporter(shard=options.shard, contest_id=options.contest_id, spool_dir=args[0])
    spool_exporter.do_export()

if __name__ == "__main__":
    main()
