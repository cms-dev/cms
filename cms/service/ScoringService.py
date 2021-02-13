#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2016 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2017 Amir Keivan Mohtashami <akmohtashami97@gmail.com>
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

"""A service that assigns a score to submission results.

"""

import logging

from cms import ServiceCoord, config
from cms.db import SessionGen, Submission, Dataset, get_submission_results
from cms.io import Executor, TriggeredService, rpc_method
from cmscommon.datetime import make_datetime
from .scoringoperations import ScoringOperation, get_operations


logger = logging.getLogger(__name__)


class ScoringExecutor(Executor):
    def __init__(self, proxy_service):
        super().__init__()
        self.proxy_service = proxy_service

    def execute(self, entry):
        """Assign a score to a submission result.

        This is the core of ScoringService: here we retrieve the result
        from the database, check if it is in the correct status,
        instantiate its ScoreType, compute its score, store it back in
        the database and tell ProxyService to update RWS if needed.

        entry (QueueEntry): entry containing the operation to perform.

        """
        operation = entry.item
        with SessionGen() as session:
            # Obtain submission.
            submission = Submission.get_from_id(operation.submission_id,
                                                session)
            if submission is None:
                raise ValueError("Submission %d not found in the database." %
                                 operation.submission_id)

            # Obtain dataset.
            dataset = Dataset.get_from_id(operation.dataset_id, session)
            if dataset is None:
                raise ValueError("Dataset %d not found in the database." %
                                 operation.dataset_id)

            # Obtain submission result.
            submission_result = submission.get_result(dataset)

            # It means it was not even compiled (for some reason).
            if submission_result is None:
                raise ValueError("Submission result %d(%d) was not found." %
                                 (operation.submission_id,
                                  operation.dataset_id))

            # Check if it's ready to be scored.
            if not submission_result.needs_scoring():
                if submission_result.scored():
                    logger.info("Submission result %d(%d) is already scored.",
                                operation.submission_id, operation.dataset_id)
                    return
                else:
                    raise ValueError("The state of the submission result "
                                     "%d(%d) doesn't allow scoring." %
                                     (operation.submission_id,
                                      operation.dataset_id))

            # Instantiate the score type.
            score_type = dataset.score_type_object

            # Compute score and fill it in the database.
            submission_result.score, \
                submission_result.score_details, \
                submission_result.public_score, \
                submission_result.public_score_details, \
                submission_result.ranking_score_details = \
                score_type.compute_score(submission_result)

            if submission_result.scored_at is None:
                submission_result.scored_at = make_datetime()

            # Store it.
            session.commit()

            # If dataset is the active one, update RWS.
            if dataset is submission.task.active_dataset:
                logger.info(
                    "Submission scored %.1f seconds after submission",
                    (make_datetime() - submission.timestamp).total_seconds())
                self.proxy_service.submission_scored(
                    submission_id=submission.id)


class ScoringService(TriggeredService):
    """A service that assigns a score to submission results.

    A submission result is ready to be scored when its compilation is
    unsuccessful (in this case, no evaluation will be performed) or
    after it has been evaluated. The goal of scoring is to use the
    evaluations to determine score, score_details, public_score,
    public_score_details and ranking_score_details (all non-null).
    Scoring is done by the compute_score method of the ScoreType
    defined by the dataset of the result.

    """

    def __init__(self, shard):
        """Initialize the ScoringService.

        """
        super().__init__(shard)

        # Set up communication with ProxyService.
        ranking_enabled = len(config.rankings) > 0
        self.proxy_service = self.connect_to(
            ServiceCoord("ProxyService", 0),
            must_be_present=ranking_enabled)

        self.add_executor(ScoringExecutor(self.proxy_service))
        self.start_sweeper(347.0)

    def _missing_operations(self):
        """Return a generator of unscored submission results.

        Obtain a list of all the submission results in the database,
        check each of them to see if it's still unscored and if so
        enqueue them.

        """
        counter = 0
        with SessionGen() as session:
            for operation, timestamp in get_operations(session):
                self.enqueue(operation, timestamp=timestamp)
                counter += 1
        return counter

    @rpc_method
    def new_evaluation(self, submission_id, dataset_id):
        """Schedule the given submission result for scoring.

        Put it in the queue to have it scored, sooner or later. Usually
        called by EvaluationService when it's done with a result.

        submission_id (int): the id of the submission that has to be
            scored.
        dataset_id (int): the id of the dataset to use.

        """
        self.enqueue(ScoringOperation(submission_id, dataset_id))

    @rpc_method
    def invalidate_submission(self, submission_id=None, dataset_id=None,
                              participation_id=None, task_id=None,
                              contest_id=None):
        """Invalidate (and re-score) some submission results.

        Invalidate the scores of the submission results that:
        - belong to submission_id or, if None, to any submission of
          participation_id and/or task_id or, if both None, to any
          submission of contest_id or, if None, to any submission in
          the database.
        - belong to dataset_id or, if None, to any dataset of task_id
          or, if None, to any dataset of contest_id or, if None, to any
          dataset in the database.

        submission_id (int|None): id of the submission whose results
            should be invalidated, or None.
        dataset_id (int|None): id of the dataset whose results should
            be invalidated, or None.
        participation_id (int|None): id of the participation whose results
            should be invalidated, or None.
        task_id (int|None): id of the task whose results should be
            invalidated, or None.
        contest_id (int|None): id of the contest whose results should
            be invalidated, or None.

        """
        logger.info("Invalidation request received.")

        # We can put results in the scorer queue only after they have
        # been invalidated (and committed to the database). Therefore
        # we temporarily save them somewhere else.
        temp_queue = list()

        with SessionGen() as session:
            submission_results = \
                get_submission_results(session, contest_id,
                                       participation_id, task_id,
                                       submission_id, dataset_id).all()

            for sr in submission_results:
                if sr.scored():
                    sr.invalidate_score()
                    # We also save the timestamp of the submission, to
                    # rescore them in order (for fairness, not for a
                    # specific need).
                    temp_queue.append((
                        ScoringOperation(sr.submission_id, sr.dataset_id),
                        sr.submission.timestamp))

            session.commit()

        for item, timestamp in temp_queue:
            self.enqueue(item, timestamp=timestamp)

        logger.info("Invalidated %d submission results.", len(temp_queue))
