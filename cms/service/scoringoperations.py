#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2016 Stefano Maggiolo <s.maggiolo@gmail.com>
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

"""The ScoringService operation class, and related functions to
compute sets of operations to do.

"""

import logging

from cms.db import Dataset, Submission, SubmissionResult, \
    Task
from cms.io import QueueItem


logger = logging.getLogger(__name__)


FILTER_DATASETS_TO_JUDGE = (
    (Dataset.id == Task.active_dataset_id) |
    (Dataset.autojudge.is_(True))
)
FILTER_SUBMISSION_RESULTS_TO_SCORE = (
    (~SubmissionResult.filter_scored()) & (
        (SubmissionResult.filter_compilation_failed()) |
        (SubmissionResult.filter_evaluated()))
)


def get_operations(session):
    """Return all the operations to do for all submissions.

    session (Session): the database session to use.

    return ([ScoringOperation, float]): a list of operations and
        timestamps.

    """
    # Retrieve all the compilation operations for submissions
    # already having a result for a dataset to judge.
    results = session.query(Submission)\
        .join(Submission.task)\
        .join(Submission.results)\
        .join(SubmissionResult.dataset)\
        .filter(
            (FILTER_DATASETS_TO_JUDGE) &
            (FILTER_SUBMISSION_RESULTS_TO_SCORE))\
        .with_entities(Submission.id, Dataset.id, Submission.timestamp)\
        .all()

    return [(ScoringOperation(result[0], result[1]), result[2])
            for result in results]


class ScoringOperation(QueueItem):
    """The operation for the scoring service executor.

    It represent the operation of scoring a submission result,
    therefore it only contains the data identifying it: the ids for
    the submission and the dataset.

    """

    def __init__(self, submission_id, dataset_id):
        self.submission_id = submission_id
        self.dataset_id = dataset_id

    def __eq__(self, other):
        if self.__class__ != other.__class__:
            return False
        return self.submission_id == other.submission_id \
            and self.dataset_id == other.dataset_id

    def __hash__(self):
        return hash((self.submission_id, self.dataset_id))

    def __str__(self):
        return "scoring submission %d on dataset %d" % (
            self.submission_id, self.dataset_id)

    def __repr__(self):
        return "(%s, %s)" % (
            self.submission_id,
            self.dataset_id)

    def to_dict(self):
        return {"submission_id": self.submission_id,
                "dataset_id": self.dataset_id}
