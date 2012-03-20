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

from cms.grading.ScoreType import ScoreType


class Relative(ScoreType):
    """Scoring systems where the score of a submission is the sum of
    the scores for each testcase, and the score of a testcase is the
    ratio between the outcome of that testcase and the best outcome of
    all others submissions (also in the future) that are going to
    contribute to the final score (i.e., the last submission for all
    users, and the submissions where the user used a token). Also
    compared with a 'basic' outcome given as a parameter. Finally, the
    score is multiplied by a multiplier given as parameter.

    """
    def initialize(self):
        """Init.

        parameters (couple): the first element is a float, the
                             multiplier; the second is a list of
                             length eval_num, whose elements are the
                             'basic' outcomes, or None for no basic
                             outcome.

        """
        # We keep the best outcome that is gonna stay (i.e., not
        # amongst the last submissions, but only tokened and basic
        # outcomes. Elements may be None.
        self.best_tokenized_outcomes = []
        for par in self.parameters[1]:
            self.best_tokenized_outcomes.append(par)

        # Temporary store the best outcomes for every evaluation as
        # computed in compute_score, to use them in update_scores.
        self.best_outcomes = None

    def compute_best_outcomes(self):
        """Merge best_tokenized_outcomes with the last submissions of
        every user to return the current best outcome for every
        evaluation.

        returns (list): a list of one float for every evaluation, the
                        best outcome.

        """
        best_outcomes = self.best_tokenized_outcomes[:]
        for username in self.submissions:
            submissions = self.submissions[username]
            if submissions == []:
                continue
            for i, outcome in \
                enumerate(self.pool[submissions[-1]]["evaluations"]):
                best_outcomes[i] = max(best_outcomes[i], outcome)

        return best_outcomes

    def update_scores(self, new_submission_id):
        """Update the scores of the contest assuming that only this
        submission appeared.

        new_submission_id (int): id of the newly added submission.

        best_outcomes (list):

        """
        # If we just computed best_outcomes in compute_score, we don't
        # compute it again.
        if self.best_outcomes is None:
            best_outcomes = self.compute_best_outcomes()
        else:
            best_outcomes = self.best_outcomes
            self.best_outcomes = None

        # Then, we update the score for each submission, and we update
        # the users' scores.
        for username in self.submissions:
            submissions = self.submissions[username]
            score = 0.0
            for submission_id in submissions:
                self.pool[submission_id]["score"] = \
                    sum([float(x) / y for x, y
                         in zip(self.pool[submission_id]["evaluations"],
                                best_outcomes)]) * self.parameters[0]
                if self.pool[submission_id]["tokened"] is not None:
                    score = max(score, self.pool[submission_id]["score"])
            if submissions != []:
                score = max(score, self.pool[submissions[-1]]["score"])
            self.scores[username] = score

    def max_scores(self):
        """Compute the maximum score of a submission. FIXME: this
        suppose that the outcomes are in [0, 1].

        returns (float, float): maximum score overall and public.

        """
        public_score = 0.0
        score = 0.0
        for public in self.public_testcases:
            score += self.parameters[0]
            if public:
                public_score += self.parameters[0]
        return round(score, 2), round(public_score, 2)

    def compute_score(self, submission_id):
        """Compute the score of a submission.

        submission_id (int): the submission to evaluate.
        returns (float): the score

        """
        self.best_outcomes = self.compute_best_outcomes()
        score = 0.0
        public_score = 0.0
        for public, evaluation, best in zip(
            self.public_testcases,
            self.pool[submission_id]["evaluations"],
            self.best_outcomes):
            to_add = float(evaluation) / best * self.parameters[0]
            score += to_add
            if public:
                public_score += to_add
        return round(score, 2), None, round(public_score, 2), None
