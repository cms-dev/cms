#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
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

"""Scoring service. Its jobs is to handle everything is about
assigning scores and communicating them to the world.

In particular, it takes care of handling the internal way of keeping
the score (i.e., the ranking view) and send to the external ranking
services the scores, via http requests.

"""

from cms import logger
from cms.io import ServiceCoord
from cms.io.GeventLibrary import Service, rpc_method
from cms.db import SessionGen, Submission, Contest, Dataset
from cms.grading.scoretypes import get_score_type
from cms.service import get_submission_results, get_datasets_to_judge


class ScoringService(Service):
    """Scoring service.

    """

    # How often we look for submission not scored/tokened.
    JOBS_NOT_DONE_CHECK_TIME = 347.0

    def __init__(self, shard, contest_id):
        logger.initialize(ServiceCoord("ScoringService", shard))
        Service.__init__(self, shard, custom_logger=logger)

        self.contest_id = contest_id

        self.proxy_service = self.connect_to(ServiceCoord("ProxyService", 0))

        # If for some reason (SS switched off for a while, or broken
        # connection with ES), submissions have been left without
        # score, this is the set where you want to pur their ids. Note
        # that sets != {} if and only if there is an alive timeout for
        # the method "score_old_submission".
        #
        # submission_results_to_score and submission_results_scored
        # contain pairs of (submission_id, dataset_id).
        self.submission_results_to_score = set()
        self.scoring_old_submission = False

        # We need to load every submission at start, but we don't want
        # to invalidate every score so that we can simply load the
        # score-less submissions. So we keep a set of submissions that
        # we analyzed (for scoring and for tokens).
        self.submission_results_scored = set()

        self.add_timeout(self.search_jobs_not_done, None,
                         ScoringService.JOBS_NOT_DONE_CHECK_TIME,
                         immediately=True)

    @rpc_method
    def search_jobs_not_done(self):
        """Look in the database for submissions that have not been
        scored for no good reasons. Put the missing job in the queue.

        """
        # Do this only if we are not still loading old submission
        # (from the start of the service).
        if self.scoring_old_submission:
            return True

        with SessionGen() as session:
            contest = Contest.get_from_id(self.contest_id, session)

            new_submission_results_to_score = set()

            for submission in contest.get_submissions():
                if submission.user.hidden:
                    continue

                for dataset in get_datasets_to_judge(submission.task):
                    sr = submission.get_result(dataset)
                    sr_id = (submission.id, dataset.id)

                    if sr is not None and (sr.evaluated() or
                            sr.compilation_outcome == "fail") and \
                            sr_id not in self.submission_results_scored:
                        new_submission_results_to_score.add(sr_id)

        new_s = len(new_submission_results_to_score)
        old_s = len(self.submission_results_to_score)
        logger.info("Submissions found to score: %d." % new_s)
        if new_s > 0:
            self.submission_results_to_score |= new_submission_results_to_score
            if old_s == 0:
                self.add_timeout(self.score_old_submissions, None,
                                 0.5, immediately=False)

        # Run forever.
        return True

    def score_old_submissions(self):
        """The submissions in the submission_results_to_score set are
        evaluated submissions that we can assign a score to, and this
        method scores a bunch of these at a time. This method keeps
        getting called while the set is non-empty. (Exactly the same
        happens for the submissions to token.)

        Note: doing this way (instead of putting everything in the
        __init__) prevent freezing the service at the beginning in the
        case of many old submissions.

        """
        self.scoring_old_submission = True
        to_score = len(self.submission_results_to_score)
        to_score_now = to_score if to_score < 4 else 4
        logger.info("Old submission yet to score: %s." % to_score)

        for _ in xrange(to_score_now):
            submission_id, dataset_id = self.submission_results_to_score.pop()
            self.new_evaluation(submission_id, dataset_id)
        if to_score - to_score_now > 0:
            return True

        logger.info("Finished loading old submissions.")
        self.scoring_old_submission = False
        return False

    @rpc_method
    def new_evaluation(self, submission_id, dataset_id):
        """This RPC inform ScoringService that ES finished the work on
        a submission (either because it has been evaluated, or because
        the compilation failed).

        submission_id (int): the id of the submission that changed.
        dataset_id (int): the id of the dataset to use.

        """
        with SessionGen() as session:
            submission = Submission.get_from_id(submission_id, session)

            if submission is None:
                logger.error("[new_evaluation] Couldn't find submission %d "
                             "in the database." % submission_id)
                raise ValueError

            if submission.user.hidden:
                logger.info("[new_evaluation] Submission %d not scored "
                            "because user is hidden." % submission_id)
                return

            dataset = Dataset.get_from_id(dataset_id, session)

            if dataset is None:
                logger.error("[new_evaluation] Couldn't find dataset %d "
                             "in the database." % dataset_id)
                raise ValueError

            submission_result = submission.get_result(dataset)

            # We'll accept only submissions that either didn't compile
            # at all or that did evaluate successfully.
            if submission_result is None or not submission_result.compiled():
                logger.warning("[new_evaluation] Submission %d(%d) is "
                               "not compiled." % (submission_id, dataset_id))
                return
            elif submission_result.compilation_outcome == "ok" and \
                    not submission_result.evaluated():
                logger.warning("[new_evaluation] Submission %d(%d) is "
                               "compiled but is not evaluated." %
                               (submission_id, dataset_id))
                return

            # Assign score to the submission.
            score_type = get_score_type(dataset=dataset)
            score, details, public_score, public_details, ranking_details = \
                score_type.compute_score(submission_result)

            # Mark submission as scored.
            self.submission_results_scored.add((submission_id, dataset_id))

            # Filling submission's score info in the db.
            submission_result.score = score
            submission_result.public_score = public_score

            # And details.
            submission_result.score_details = details
            submission_result.public_score_details = public_details
            submission_result.ranking_score_details = ranking_details

            # If dataset is the active one, update RWS.
            if dataset is submission.task.active_dataset:
                self.proxy_service.submission_scored(
                    submission_id=submission.id)

            session.commit()

    @rpc_method
    def invalidate_submission(self,
                              submission_id=None,
                              dataset_id=None,
                              user_id=None,
                              task_id=None):
        """Request for invalidating some scores.

        Invalidate the scores of the SubmissionResults that:
        - belong to submission_id or, if None, to any submission of
          user_id and/or task_id or, if both None, to any submission
          of the contest this service is running for.
        - belong to dataset_id or, if None, to any dataset of task_id
          or, if None, to any dataset of any task of the contest this
          service is running for.

        submission_id (int): id of the submission to invalidate, or
                             None.
        dataset_id (int): id of the dataset to invalidate, or None.
        user_id (int): id of the user to invalidate, or None.
        task_id (int): id of the task to invalidate, or None.

        """
        logger.info("Invalidation request received.")

        # Validate arguments
        # TODO Check that all these objects belong to this contest.

        with SessionGen() as session:
            submission_results = get_submission_results(
                # Give contest_id only if all others are None.
                self.contest_id
                    if {user_id, task_id, submission_id, dataset_id} == {None}
                    else None,
                user_id, task_id, submission_id, dataset_id, session)

            logger.info("Submission results to invalidate scores for: %d." %
                        len(submission_results))
            if len(submission_results) == 0:
                return

            new_submission_results_to_score = set()

            for submission_result in submission_results:
                # If the submission is not evaluated, it does not have
                # a score to invalidate, and, when evaluated,
                # ScoringService will be prompted to score it. So in
                # that case we do not have to do anything.
                if submission_result.evaluated():
                    submission_result.invalidate_score()
                    new_submission_results_to_score.add(
                        (submission_result.submission_id,
                         submission_result.dataset_id))

            session.commit()

        old_s = len(self.submission_results_to_score)
        self.submission_results_to_score |= new_submission_results_to_score
        if old_s == 0:
            self.add_timeout(self.score_old_submissions, None,
                             0.5, immediately=False)
