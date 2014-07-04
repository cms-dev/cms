#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2013 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""A service that assigns a score to submission results.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging

import gevent
from gevent.queue import JoinableQueue
from gevent.event import Event

from cms import ServiceCoord
from cms.io import Service, rpc_method
from cms.db import SessionGen, Submission, Dataset
from cms.grading.scoretypes import get_score_type
from cms.service import get_submission_results
from cmscommon.datetime import monotonic_time


logger = logging.getLogger(__name__)


class ScoringService(Service):
    """A service that assigns a score to submission results.

    A submission result is ready to be scored when its compilation is
    unsuccessful (in this case, no evaluation will be performed) or
    after it has been evaluated. The goal of scoring is to use the
    evaluations to determine score, score_details, public_score,
    public_score_details and ranking_score_details (all non-null).
    Scoring is done by the compute_score method of the ScoreType
    defined by the dataset of the result.

    ScoringService keeps a queue of (submission_id, dataset_id) pairs
    identifying submission results to score. A greenlet is spawned to
    consume this queue, one item at a time. The queue is filled by the
    new_evaluation and the invalidate_submissions RPC methods, and by a
    sweeper greenlet, whose duty is to regularly check all submissions
    in the database and put the unscored ones in the queue (this check
    can also be forced by the search_jobs_not_done RPC method).

    """

    # How often we look for submission results not scored.
    SWEEPER_TIMEOUT = 347.0

    def __init__(self, shard):
        """Initialize the ScoringService.

        """
        Service.__init__(self, shard)

        # Set up communication with ProxyService.
        self.proxy_service = self.connect_to(ServiceCoord("ProxyService", 0))

        # Set up and spawn the scorer.
        # TODO Link to greenlet: when it dies, log CRITICAL and exit.
        self._scorer_queue = JoinableQueue()
        gevent.spawn(self._scorer_loop)

        # Set up and spawn the sweeper.
        # TODO Link to greenlet: when it dies, log CRITICAL and exit.
        self._sweeper_start = None
        self._sweeper_event = Event()
        gevent.spawn(self._sweeper_loop)

    def _scorer_loop(self):
        """Monitor the queue, scoring its top element.

        This is an infinite loop that, at each iteration, gets an item
        from the queue (blocking until there is one, if the queue is
        empty) and scores it. Any error during the scoring is sent to
        the logger and then suppressed, because the loop must go on.

        """
        while True:
            submission_id, dataset_id = self._scorer_queue.get()
            try:
                self._score(submission_id, dataset_id)
            except Exception:
                logger.error("Unexpected error when scoring submission %d on "
                             "dataset %d.", submission_id, dataset_id,
                             exc_info=True)
            finally:
                self._scorer_queue.task_done()

    def _score(self, submission_id, dataset_id):
        """Assign a score to a submission result.

        This is the core of ScoringService: here we retrieve the result
        from the database, check if it is in the correct status,
        instantiate its ScoreType, compute its score, store it back in
        the database and tell ProxyService to update RWS if needed.

        submission_id (int): the id of the submission that has to be
            scored.
        dataset_id (int): the id of the dataset to use.

        """
        with SessionGen() as session:
            # Obtain submission.
            submission = Submission.get_from_id(submission_id, session)
            if submission is None:
                raise ValueError("Submission %d not found in the database." %
                                 submission_id)

            # Obtain dataset.
            dataset = Dataset.get_from_id(dataset_id, session)
            if dataset is None:
                raise ValueError("Dataset %d not found in the database." %
                                 dataset_id)

            # Obtain submission result.
            submission_result = submission.get_result(dataset)

            # It means it was not even compiled (for some reason).
            if submission_result is None:
                raise ValueError("Submission result %d(%d) was not found." %
                                 (submission_id, dataset_id))

            # Check if it's ready to be scored.
            if not submission_result.needs_scoring():
                if submission_result.scored():
                    logger.info("Submission result %d(%d) is already scored.",
                                submission_id, dataset_id)
                    return
                else:
                    raise ValueError("The state of the submission result "
                                     "%d(%d) doesn't allow scoring." %
                                     (submission_id, dataset_id))

            # Instantiate the score type.
            score_type = get_score_type(dataset=dataset)

            # Compute score and fill it in the database.
            submission_result.score, \
                submission_result.score_details, \
                submission_result.public_score, \
                submission_result.public_score_details, \
                submission_result.ranking_score_details = \
                score_type.compute_score(submission_result)

            # Store it.
            session.commit()

            # If dataset is the active one, update RWS.
            if dataset is submission.task.active_dataset:
                self.proxy_service.submission_scored(
                    submission_id=submission.id)

    def _sweeper_loop(self):
        """Regularly check the database for unscored results.

        Try to sweep the database once every SWEEPER_TIMEOUT seconds
        but make sure that no two sweeps run simultaneously. That is,
        start a new sweep SWEEPER_TIMEOUT seconds after the previous
        one started or when the previous one finished, whatever comes
        last.

        The search_jobs_not_done RPC method can interfere with this
        regularity, as it tries to run a sweeper as soon as possible:
        immediately, if no sweeper is running, or as soon as the
        current one terminates.

        Any error during the sweep is sent to the logger and then
        suppressed, because the loop must go on.

        """
        while True:
            self._sweeper_start = monotonic_time()
            self._sweeper_event.clear()

            try:
                self._sweep()
            except Exception:
                logger.error("Unexpected error when searching for unscored "
                             "submissions.", exc_info=True)

            self._sweeper_event.wait(max(self._sweeper_start +
                                         self.SWEEPER_TIMEOUT -
                                         monotonic_time(), 0))

    def _sweep(self):
        """Check the database for unscored submission results.

        Obtain a list of all the submission results in the database,
        check each of them to see if it's still unscored and, in case,
        put it in the queue.

        """
        counter = 0

        with SessionGen() as session:
            for sr in get_submission_results(session=session):
                if sr is not None and sr.needs_scoring():
                    self._scorer_queue.put((sr.submission_id, sr.dataset_id))
                    counter += 1

        if counter > 0:
            logger.info("Found %d unscored submissions.", counter)

    @rpc_method
    def search_jobs_not_done(self):
        """Make the sweeper loop fire the sweeper as soon as possible.

        """
        self._sweeper_event.set()

    @rpc_method
    def new_evaluation(self, submission_id, dataset_id):
        """Schedule the given submission result for scoring.

        Put it in the queue to have it scored, sooner or later. Usually
        called by EvaluationService when it's done with a result.

        submission_id (int): the id of the submission that has to be
            scored.
        dataset_id (int): the id of the dataset to use.

        """
        self._scorer_queue.put((submission_id, dataset_id))

    @rpc_method
    def invalidate_submission(self, submission_id=None, dataset_id=None,
                              user_id=None, task_id=None, contest_id=None):
        """Invalidate (and re-score) some submission results.

        Invalidate the scores of the submission results that:
        - belong to submission_id or, if None, to any submission of
          user_id and/or task_id or, if both None, to any submission
          of contest_id or, if None, to any submission in the database.
        - belong to dataset_id or, if None, to any dataset of task_id
          or, if None, to any dataset of contest_id or, if None, to any
          dataset in the database.

        submission_id (int|None): id of the submission whose results
            should be invalidated, or None.
        dataset_id (int|None): id of the dataset whose results should
            be invalidated, or None.
        user_id (int|None): id of the user whose results should be
            invalidated, or None.
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
                get_submission_results(contest_id, user_id, task_id,
                                       submission_id, dataset_id,
                                       session=session)

            for sr in submission_results:
                if sr.scored():
                    sr.invalidate_score()
                    temp_queue.append((sr.submission_id, sr.dataset_id))

            session.commit()

        for item in temp_queue:
            self._scorer_queue.put(item)

        logger.info("Invalidated %d submissions.", len(temp_queue))
