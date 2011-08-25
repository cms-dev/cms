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

from cms.async.AsyncLibrary import logger

class ScoreTypes:
    """Contains constants for all defined score types.

    """
    # TODO: if we really want to do plugins, this class should look up
    # score types in some given path.

    # The evaluation is the sum of the outcome for all testcases.
    SCORE_TYPE_SUM = "ScoreTypeSum"

    # The evaluation is the sum over some specified ranges of the
    # minimum outcome amongst the testcases in that range.
    SCORE_TYPE_GROUP_MIN = "ScoreTypeGroupMin"

    # The same, with multiplication substituting minimum.
    SCORE_TYPE_GROUP_MUL = "ScoreTypeGroupMul"

    # The evaluation is the sum over all testcases of the ratio
    # between the outcome and the maximum amongst all outcomes for
    # that testcase and a given value.
    SCORE_TYPE_RELATIVE = "ScoreTypeRelative"

    @staticmethod
    def get_score_type(score_type, score_parameters):
        """Returns the right score type class for a given string.

        """
        if score_type == ScoreTypes.SCORE_TYPE_SUM:
            return ScoreTypeSum(score_parameters)
        elif score_type == ScoreTypes.SCORE_TYPE_GROUP_MIN:
            return ScoreTypeGroupMin(score_parameters)
        elif score_type == ScoreTypes.SCORE_TYPE_GROUP_MUL:
            return ScoreTypeGroupMul(score_parameters)
        elif score_type == ScoreTypes.SCORE_TYPE_RELATIVE:
            return ScoreTypeRelative(score_parameters)
        else:
            raise KeyError


class ScoreType:
    """Base class for all score types, that must implement all methods
    defined here.

    """
    def __init__(self, parameters):
        """Initializer.

        parameters (object): format is specified in the subclasses.

        """
        self.parameters = parameters

        # Dict that associate to a username the list of its
        # submission_ids - sorted by timestamp.
        self.submissions = {}

        # Dict that associate to every submission_id its data:
        # timestamp, username, evaluations, tokened, score.
        self.pool = {}

        # Dict that associate to a username the maximum score amongst
        # its tokened submissions and the last one.
        self.scores = {}

    def add_submission(self, submission_id, timestamp, username,
                       evaluations, tokened):
        """To call in order to add a submission to the computation of
        all scores.

        submission_id (int): id of the new submission.
        timestamp (int): time of submission.
        username (string): username of the owner of the submission.
        evaluations (list): list of objects representing the evaluations.
        tokened (bool): if the user played a token on submission.

        """
        self.pool[submission_id] = {
            "timestamp": timestamp,
            "username": username,
            "evaluations": evaluations,
            "tokened": tokened,
            "score": None
            }
        self.pool[submission_id]["score"] = self.compute_score(submission_id)
        if username not in self.submissions or \
            self.submissions[username] is None:
            self.submissions[username] = [submission_id]
        else:
            self.submissions[username].append(submission_id)

        # We expect submissions to arrive more or less in the right
        # order, so we insert-sort the new one.
        i = len(self.submissions[username])-1
        while i > 0 and \
            self.pool[self.submissions[username][i-1]]["timestamp"] > \
            self.pool[self.submissions[username][i]]["timestamp"]:
            self.submissions[username][i-1], self.submissions[username][i] = \
                self.submissions[username][i], self.submissions[username][i-1]
            i -= 1

        self.update_scores(submission_id)

    def add_token(self, submission_id):
        """To call when a token is played, so that the scores updates.

        submission_id (int): id of the tokened submission.

        """
        try:
            self.pool[submission_id]["tokened"] = True
        except KeyError:
            logger.error("Submission %d not found in ScoreType's pool." %
                         submission_id)

        self.update_scores(submission_id)

    def compute_all_scores(self):
        """Recompute all scores, usually needed only in case of
        problems.

        """
        for submissions in self.submissions.itervalues():
            # We recompute score for all submissions of user...
            for submission_id in submissions:
                self.compute_score(submission_id)
            # and update the score of the user (only once).
            if submissions != []:
                self.update_scores(submissions[-1])

    def update_scores(self, new_submission_id):
        """Update the scores of the users assuming that only this
        submission appeared or was modified (i.e., tokened). The way
        to do this depends on the subclass, so we leave this
        unimplemented.

        new_submission_id (int): id of the newly added submission.

        """
        logger.error("Unimplemented method update_scores.")
        self.scores[username] = 0.0

    def compute_score(self, submission_id):
        """Computes a score of a single submission. We don't know here
        how to for it, but our subclasses will.

        submission_id (int): the submission to evaluate.
        returns (float): the score

        """
        logger.error("Unimplemented method compute_score.")
        return 0.0


class ScoreTypeAlone(ScoreType):
    """Intermediate class to manage tasks where the score of a
    submission depends only on the submission itself and not on the
    other submissions' outcome. Remains to implement compute_score to
    obtain the score of a single submission.

    """
    def update_scores(self, new_submission_id):
        """Update the scores of the user assuming that only this
        submission appeared.

        new_submission_id (int): id of the newly added submission.

        """
        username = self.pool[new_submission_id]["username"]
        submission_ids = self.submissions[username]
        score = 0.0

        # We find the best amongst all tokened submissions...
        for submission_id in submission_ids:
            if self.pool[submission_id]["tokened"]:
                score = max(score, self.pool[submission_id]["score"])
        # and the last one.
        if submission_ids != []:
            score = max(score, self.pool[submission_ids[-1]]["score"])

        # Finally we update the score table.
        self.scores[username] = score


class ScoreTypeSum(ScoreTypeAlone):
    """The score of a submission is the sum of the outcomes,
    multiplied by the integer parameter.

    """
    def compute_score(self, submission_id):
        """Compute the score of a submission.

        submission_id (int): the submission to evaluate.
        returns (float): the score

        """
        evaluations = self.pool[submission_id]["evaluations"]
        return sum(evaluations) * self.parameters


class ScoreTypeGroupMin(ScoreTypeAlone):
    """The score of a submission is the sum of the product of the
    minimum of the ranges with the multiplier of that range.

    Parameters are [{'multiplier': m, 'testcases': t}, ... ] and this
    means that the first group consists of the first t testcases and
    the min will be multiplied by m.

    """
    def compute_score(self, submission_id):
        """Compute the score of a submission.

        submission_id (int): the submission to evaluate.
        returns (float): the score

        """
        evaluations = self.pool[submission_id]["evaluations"]
        current = 0
        score = 0.0
        for parameter in self.parameters:
            next_ = current + parameter[1]
            score += min(evaluations[current:next_]) * parameter[0]
            current = next_
        return score


class ScoreTypeGroupMul(ScoreTypeAlone):
    """Similar to ScoreTypeGroupMin, but with the product instead of
    the minimum.

    """
    def compute_score(self, submission_id):
        """Compute the score of a submission.

        submission_id (int): the submission to evaluate.
        returns (float): the score

        """
        evaluations = self.pool[submission_id]["evaluations"]
        current = 0
        score = 0.0
        for parameter in self.parameters:
            next_ = current + parameter[1]
            score += reduce(lambda x, y: x * y,
                            evaluations[current:next_]) * parameter[0]
            current = next_
        return score


class ScoreTypeRelative(ScoreType):
    """Scoring systems where the score of a submission is the sum of
    the scores for each testcase, and the score of a testcase is the
    ratio between the outcome of that testcase and the best outcome of
    all others submissions (also in the future) that are going to
    contribute to the final score (i.e., the last submission for all
    users, and the submissions where the user used a token). Also
    compared with a 'basic' outcome given as a parameter. Finally, the
    score is multiplied by a multiplier given as parameter.

    """
    def __init__(self, parameters):
        """Init.

        parameters (couple): the first element is a float, the
                             multiplier; the second is a list of
                             length eval_num, whose elements are the
                             'basic' outcomes, or None for no basic
                             outcome.

        """
        ScoreType.__init__(self, parameters)

        # We keep the best outcome that is gonna stay (i.e., not
        # amongst the last submissions, but only tokened and basic
        # outcomes. Elements may be None.
        self.best_tokenized_outcomes = []
        for p in self.parameters[1]:
            self.best_tokenized_outcomes.append(p)

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
        submission_details = self.pool[new_submission_id]
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

    def compute_score(self, submission_id):
        """Compute the score of a submission.

        submission_id (int): the submission to evaluate.
        returns (float): the score

        """
        self.best_outcomes = self.compute_best_outcomes()
        score = sum([float(x) / y for x, y
                     in zip(self.pool[submission_id]["evaluations"],
                            self.best_outcomes)]) * self.parameters[0]
        return score
