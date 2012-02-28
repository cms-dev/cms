#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
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

"""This service creates a tree structure "similar" to the one used in
Italian IOI repository for storing the results of a contest.

"""

import os
import codecs
import argparse

from cms import logger
from cms.db.FileCacher import FileCacher
from cms.db.SQLAlchemyAll import SessionGen, Contest
from cms.db.Utils import ask_for_contest


class SpoolExporter:
    """This service creates a tree structure "similar" to the one used
    in Italian IOI repository for storing the results of a contest.

    """
    def __init__(self, contest_id, spool_dir):
        self.contest_id = contest_id
        self.spool_dir = spool_dir
        self.upload_dir = os.path.join(self.spool_dir, "upload")
        self.contest = None

        self.file_cacher = FileCacher()

    def run(self):
        """Interface to make the class do its job."""
        return self.do_export()

    def do_export(self):
        """Run the actual export code.

        """
        logger.operation = "exporting contest %s" % self.contest_id
        logger.info("Starting export.")

        logger.info("Creating dir structure.")
        try:
            os.mkdir(self.spool_dir)
        except OSError:
            logger.error("The specified directory already exists, "
                         "I won't overwrite it.")
            return False
        os.mkdir(self.upload_dir)

        with SessionGen(commit=False) as session:
            self.contest = Contest.get_from_id(self.contest_id, session)

            # Creating users' directory.
            for user in self.contest.users:
                if not user.hidden:
                    os.mkdir(os.path.join(self.upload_dir, user.username))

            self.export_submissions()
            self.export_ranking()

        logger.info("Export finished.")
        logger.operation = ""

        return True

    def export_submissions(self):
        """Export submissions' source files.

        """
        logger.info("Exporting submissions.")

        queue_file = codecs.open(os.path.join(self.spool_dir, "queue"), "w",
                                 encoding="utf-8")
        # FIXME - The enumeration of submission should be time-increasing
        for submission in self.contest.get_submissions():
            if submission.user.hidden:
                continue
            logger.info("Exporting submission %s." % submission.id)
            username = submission.user.username
            task = submission.task.name
            timestamp = submission.timestamp

            # Get source files to the spool directory.
            file_digest = submission.files["%s.%s" % (task, "%l")].digest
            upload_filename = os.path.join(
                self.upload_dir, username, "%s.%d.%s" %
                (task, timestamp, submission.language))
            self.file_cacher.get_file(file_digest, path=upload_filename)
            upload_filename = os.path.join(
                self.upload_dir, username, "%s.%s" %
                (task, submission.language))
            self.file_cacher.get_file(file_digest, path=upload_filename)
            print >> queue_file, "./upload/%s/%s.%d.%s" % \
                (username, task, timestamp, submission.language)

            # Write results file for the submission.
            if submission.evaluated():
                res_file = codecs.open(os.path.join(
                    self.spool_dir,
                    "%d.%s.%s.%s.res" % (timestamp, username,
                                         task, submission.language)),
                                       "w", encoding="utf-8")
                res2_file = codecs.open(os.path.join(
                    self.spool_dir,
                    "%s.%s.%s.res" % (username, task,
                                      submission.language)),
                                        "w", encoding="utf-8")
                total = 0.0
                for num, evaluation in enumerate(submission.evaluations):
                    outcome = float(evaluation.outcome)
                    total += outcome
                    line = "Executing on file n. %2d %s (%.4f)" % \
                        (num, evaluation.text, outcome)
                    print >> res_file, line
                    print >> res2_file, line
                line = "Score: %.6f" % total
                print >> res_file, line
                print >> res2_file, line
                res_file.close()
                res2_file.close()

        print >> queue_file
        queue_file.close()

    def export_ranking(self):
        """Exports the ranking in csv and txt (human-readable) form.

        """
        logger.info("Exporting ranking.")

        # Create a list of (points, usernames, [task_points]) to write
        # to the rankings.
        users = {}
        hidden_users = {}
        for user in self.contest.users:
            # Avoid hidden users.
            if not user.hidden:
                users[user.username] = [0.0, user.username,
                                        [0.0] * len(self.contest.tasks)]
            else:
                hidden_users[user.username] = True
        for (username, task_num), score in \
                self.contest.ranking_view.scores.iteritems():
            if username not in hidden_users:
                users[username][0] += score.score
                users[username][2][task_num] = score.score
        users = users.values()
        users.sort(reverse=True)

        ranking_file = codecs.open(
            os.path.join(self.spool_dir, "classifica.txt"),
            "w", encoding="utf-8")
        ranking_csv = codecs.open(
            os.path.join(self.spool_dir, "classifica.csv"),
            "w", encoding="utf-8")

        # Write rankings' header.
        print >> ranking_file, "Classifica finale del contest `%s'" % \
            self.contest.description
        points_line = " %10s" * len(self.contest.tasks)
        csv_points_line = ",%s" * len(self.contest.tasks)
        print >> ranking_file, ("%20s %10s" % ("Utente", "Totale")) + \
              (points_line % tuple([t.name for t in self.contest.tasks]))
        print >> ranking_csv, ("%s,%s" % ("utente", "totale")) + \
              (csv_points_line % tuple([t.name for t in self.contest.tasks]))

        # Write rankings' content.
        points_line = " %10.3f" * len(self.contest.tasks)
        csv_points_line = ",%.6f" * len(self.contest.tasks)
        for total, user, problems in users:
            print >> ranking_file, ("%20s %10.3f" % (user, total)) + \
                  (points_line % tuple(problems))
            print >> ranking_csv, ("%s,%.6f" % (user, total)) + \
                  (csv_points_line % tuple(problems))

        ranking_file.close()
        ranking_csv.close()


def main():
    """Parse arguments and launch process.

    """
    parser = argparse.ArgumentParser(
        description="Exporter for the Italian repository for CMS.")
    parser.add_argument("-c", "--contest-id", help="id of contest to export",
                      action="store", type=int)
    parser.add_argument("export_directory",
                        help="target directory where to export")
    args = parser.parse_args()

    if args.contest_id is None:
        args.contest_id = ask_for_contest()

    SpoolExporter(contest_id=args.contest_id,
                  spool_dir=args.export_directory).run()


if __name__ == "__main__":
    main()
