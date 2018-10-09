#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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

# FIXME: update to latest database version 15

"""This service creates a tree structure "similar" to the one used in
Italian IOI repository for storing the results of a contest.

"""

# We enable monkey patching to make many libraries gevent-friendly
# (for instance, urllib3, used by requests)
import gevent.monkey
gevent.monkey.patch_all()  # noqa

import argparse
import logging
import os
import sys
import time

from sqlalchemy import not_

from cms import utf8_decoder
from cms.db import SessionGen, Contest, ask_for_contest, Submission, \
    Participation, get_submissions
from cms.db.filecacher import FileCacher
from cms.grading import languagemanager
from cms.grading.scoring import task_score


logger = logging.getLogger(__name__)


# TODO: review this file to avoid print.
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
            logger.critical("The specified directory already exists, "
                            "I won't overwrite it.")
            return False
        os.mkdir(self.upload_dir)

        with SessionGen() as session:
            self.contest = Contest.get_from_id(self.contest_id, session)
            self.submissions = \
                get_submissions(session, contest_id=self.contest_id) \
                .filter(not_(Participation.hidden)) \
                .order_by(Submission.timestamp).all()

            # Creating users' directory.
            for participation in self.contest.participations:
                if not participation.hidden:
                    os.mkdir(os.path.join(
                        self.upload_dir, participation.user.username))

            try:
                self.export_submissions()
                self.export_ranking()
            except Exception:
                logger.critical("Generic error.", exc_info=True)
                return False

        logger.info("Export finished.")
        logger.operation = ""

        return True

    def export_submissions(self):
        """Export submissions' source files.

        """
        logger.info("Exporting submissions.")

        with open(os.path.join(self.spool_dir, "queue"),
                  "wt", encoding="utf-8") as queue_file:
            for submission in sorted(self.submissions,
                                     key=lambda x: x.timestamp):
                logger.info("Exporting submission %s.", submission.id)
                username = submission.participation.user.username
                task = submission.task.name
                timestamp = time.mktime(submission.timestamp.timetuple())

                # Get source files to the spool directory.
                ext = languagemanager.get_language(submission.language)\
                    .source_extension
                submission_dir = os.path.join(
                    self.upload_dir, username,
                    "%s.%d.%s" % (task, timestamp, ext))
                os.mkdir(submission_dir)
                for filename, file_ in submission.files.items():
                    self.file_cacher.get_file_to_path(
                        file_.digest,
                        os.path.join(submission_dir,
                                     filename.replace(".%l", ext)))
                last_submission_dir = os.path.join(
                    self.upload_dir, username, "%s.%s" % (task, ext))
                try:
                    os.unlink(last_submission_dir)
                except OSError:
                    pass
                os.symlink(os.path.basename(submission_dir),
                           last_submission_dir)
                print("./upload/%s/%s.%d.%s" % (username, task, timestamp, ext),
                      file=queue_file)

                # Write results file for the submission.
                active_dataset = submission.task.active_dataset
                result = submission.get_result(active_dataset)
                if result.evaluated():
                    with open(os.path.join(self.spool_dir,
                                           "%d.%s.%s.%s.res"
                                           % (timestamp, username, task, ext)),
                              "wt", encoding="utf-8") as res_file, \
                            open(os.path.join(self.spool_dir,
                                              "%s.%s.%s.res"
                                              % (username, task, ext)),
                                 "wt", encoding="utf-8") as res2_file:
                        total = 0.0
                        for evaluation in result.evaluations:
                            outcome = float(evaluation.outcome)
                            total += outcome
                            line = (
                                "Executing on file with codename '%s' %s (%.4f)"
                                % (evaluation.testcase.codename,
                                   evaluation.text, outcome))
                            print(line, file=res_file)
                            print(line, file=res2_file)
                        line = "Score: %.6f" % total
                        print(line, file=res_file)
                        print(line, file=res2_file)

            print("", file=queue_file)

    def export_ranking(self):
        """Exports the ranking in csv and txt (human-readable) form.

        """
        logger.info("Exporting ranking.")

        # Create the structure to store the scores.
        scores = dict((participation.user.username, 0.0)
                      for participation in self.contest.participations
                      if not participation.hidden)
        task_scores = dict(
            (task.id, dict((participation.user.username, 0.0)
                           for participation in self.contest.participations
                           if not participation.hidden))
            for task in self.contest.tasks)

        is_partial = False
        for task in self.contest.tasks:
            for participation in self.contest.participations:
                if participation.hidden:
                    continue
                score, partial = task_score(participation, task)
                is_partial = is_partial or partial
                task_scores[task.id][participation.user.username] = score
                scores[participation.user.username] += score
        if is_partial:
            logger.warning("Some of the scores are not definitive.")

        sorted_usernames = sorted(scores.keys(),
                                  key=lambda username: (scores[username],
                                                        username),
                                  reverse=True)
        sorted_tasks = sorted(self.contest.tasks,
                              key=lambda task: task.num)

        with open(os.path.join(self.spool_dir, "ranking.txt"),
                  "wt", encoding="utf-8") as ranking_file, \
                open(os.path.join(self.spool_dir, "ranking.csv"),
                     "wt", encoding="utf-8") as ranking_csv:

            # Write rankings' header.
            n_tasks = len(sorted_tasks)
            print("Final Ranking of Contest `%s'" %
                  self.contest.description, file=ranking_file)
            points_line = " %10s" * n_tasks
            csv_points_line = ",%s" * n_tasks
            print(("%20s %10s" % ("User", "Total")) +
                  (points_line % tuple([t.name for t in sorted_tasks])),
                  file=ranking_file)
            print(("%s,%s" % ("user", "total")) +
                  (csv_points_line % tuple([t.name for t in sorted_tasks])),
                  file=ranking_csv)

            # Write rankings' content.
            points_line = " %10.3f" * n_tasks
            csv_points_line = ",%.6f" * n_tasks
            for username in sorted_usernames:
                user_scores = [task_scores[task.id][username]
                               for task in sorted_tasks]
                print(("%20s %10.3f" % (username, scores[username])) +
                      (points_line % tuple(user_scores)),
                      file=ranking_file)
                print(("%s,%.6f" % (username, scores[username])) +
                      (csv_points_line % tuple(user_scores)),
                      file=ranking_csv)


def main():
    """Parse arguments and launch process.

    """
    parser = argparse.ArgumentParser(
        description="Exporter for the Italian repository for CMS.")
    parser.add_argument("-c", "--contest-id", action="store", type=int,
                        help="id of contest to export")
    parser.add_argument("export_directory", action="store", type=utf8_decoder,
                        help="target directory where to export")
    args = parser.parse_args()

    if args.contest_id is None:
        args.contest_id = ask_for_contest()

    exporter = SpoolExporter(contest_id=args.contest_id,
                             spool_dir=args.export_directory)
    success = exporter.run()
    return 0 if success is True else 1


if __name__ == "__main__":
    sys.exit(main())
