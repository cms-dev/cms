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
from cms.db import ask_for_contest
from cms.db.FileCacher import FileCacher
from cms.db.SQLAlchemyAll import SessionGen, Contest
from cms.grading.scoretypes import get_score_type


class SpoolExporter:
    """This service creates a tree structure "similar" to the one used
    in Italian IOI repository for storing the results of a contest.

    """
    def __init__(self, contest_id, spool_dir):
        self.contest_id = contest_id
        self.spool_dir = spool_dir
        self.upload_dir = os.path.join(self.spool_dir, "upload")
        self.contest = None
        self.submissions = None

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
            self.submissions = sorted(
                (submission
                 for submission in self.contest.get_submissions()
                 if not submission.user.hidden),
                key=lambda submission: submission.timestamp)

            # Creating users' directory.
            for user in self.contest.users:
                if not user.hidden:
                    os.mkdir(os.path.join(self.upload_dir, user.username))

            try:
                self.export_submissions()
                self.export_ranking()
            except Exception as error:
                logger.error("Generic error. %r" % error)
                return False

        logger.info("Export finished.")
        logger.operation = ""

        return True

    def export_submissions(self):
        """Export submissions' source files.

        """
        logger.info("Exporting submissions.")

        queue_file = codecs.open(os.path.join(self.spool_dir, "queue"), "w",
                                 encoding="utf-8")
        for submission in self.submissions:
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

        # Create the structure to store the scores.
        scores = dict((user.username, 0.0)
                      for user in self.contest.users
                      if not user.hidden)
        task_scores = dict((task.id, dict((user.username, 0.0)
                                          for user in self.contest.users
                                          if not user.hidden))
                           for task in self.contest.tasks)
        last_scores = dict((task.id, dict((user.username, 0.0)
                                          for user in self.contest.users
                                          if not user.hidden))
                           for task in self.contest.tasks)

        # Make the score type compute the scores.
        scorers = {}
        for task in self.contest.tasks:
            scorers[task.id] = get_score_type(task=task)

        for submission in self.submissions:
            scorers[submission.task_id].add_submission(
                submission.id, submission.timestamp,
                submission.user.username,
                dict((ev.num, float(ev.outcome))
                     for ev in submission.evaluations),
                submission.tokened())

        # Put together all the scores.
        for submission in self.submissions:
            task_id = submission.task_id
            username = submission.user.username
            details = scorers[task_id].pool[submission.id]
            last_scores[task_id][username] = details["score"]
            if details["tokened"]:
                task_scores[task_id][username] = max(
                    task_scores[task_id][username],
                    details["score"])

        # Merge tokened and last submissions.
        for username in scores:
            for task_id in task_scores:
                task_scores[task_id][username] = max(
                    task_scores[task_id][username],
                    last_scores[task_id][username]
                    )
            print username, [task_scores[task_id][username]
                                    for task_id in task_scores]
            scores[username] = sum(task_scores[task_id][username]
                                   for task_id in task_scores)

        sorted_usernames = sorted(scores.keys(),
                                  key=lambda username: (scores[username],
                                                        username),
                                  reverse=True)
        sorted_tasks = sorted(self.contest.tasks,
                              key=lambda task: task.num)

        ranking_file = codecs.open(
            os.path.join(self.spool_dir, "classifica.txt"),
            "w", encoding="utf-8")
        ranking_csv = codecs.open(
            os.path.join(self.spool_dir, "classifica.csv"),
            "w", encoding="utf-8")

        # Write rankings' header.
        n_tasks = len(sorted_tasks)
        print >> ranking_file, "Classifica finale del contest `%s'" % \
            self.contest.description
        points_line = " %10s" * n_tasks
        csv_points_line = ",%s" * n_tasks
        print >> ranking_file, ("%20s %10s" % ("Utente", "Totale")) + \
              (points_line % tuple([t.name for t in sorted_tasks]))
        print >> ranking_csv, ("%s,%s" % ("utente", "totale")) + \
              (csv_points_line % tuple([t.name for t in sorted_tasks]))

        # Write rankings' content.
        points_line = " %10.3f" * n_tasks
        csv_points_line = ",%.6f" * n_tasks
        for username in sorted_usernames:
            user_scores = [task_scores[task.id][username]
                           for task in sorted_tasks]
            print >> ranking_file, ("%20s %10.3f" % (username,
                                                     scores[username])) + \
                  (points_line % tuple(user_scores))
            print >> ranking_csv, ("%s,%.6f" % (username,
                                                scores[username])) + \
                  (csv_points_line % tuple(user_scores))

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
