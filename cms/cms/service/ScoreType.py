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

from cms.service.LogService import logger


class ScoreTypes:
    """Contain constants for all defined score types.

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
    def get_score_type(score_type, score_parameters, public_testcases):
        """Returns the right score type class for a given string.

        score_type (string): the name of the score type class.
        score_parameters (dict): the parameters for the new object.

        """
        if score_type == ScoreTypes.SCORE_TYPE_SUM:
            return ScoreTypeSum(score_parameters, public_testcases)
        elif score_type == ScoreTypes.SCORE_TYPE_GROUP_MIN:
            return ScoreTypeGroupMin(score_parameters, public_testcases)
        elif score_type == ScoreTypes.SCORE_TYPE_GROUP_MUL:
            return ScoreTypeGroupMul(score_parameters, public_testcases)
        elif score_type == ScoreTypes.SCORE_TYPE_RELATIVE:
            return ScoreTypeRelative(score_parameters, public_testcases)
        else:
            raise KeyError


class ScoreType:
    """Base class for all score types, that must implement all methods
    defined here.

    """
    def __init__(self, parameters, public_testcases):
        """Initializer.

        parameters (object): format is specified in the subclasses.
        public_testcases (list): list of booleans indicating if the
                                 testcases are pulic or not
        """
        self.parameters = parameters
        self.public_testcases = public_testcases

        # Dict that associate to a username the list of its
        # submission_ids - sorted by timestamp.
        self.submissions = {}

        # Dict that associate to every submission_id its data:
        # timestamp, username, evaluations, tokened, score.
        self.pool = {}

        # Dict that associate to a username the maximum score amongst
        # its tokened submissions and the last one.
        self.scores = {}

        # Preload the maximum possible scores.
        self.max_score, self.max_public_score = \
            self.max_scores()

        # Initialization method that can be overwritten by subclass.
        self.initialize()

    def initialize(self):
        """Intended to be overwritten by subclasses.

        """
        pass

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
            "score": None,
            "details": None,
            "public_score": None,
            "public_details": None
            }
        (score, details, public_score, public_details) = \
                self.compute_score(submission_id)
        self.pool[submission_id]["score"] = score
        self.pool[submission_id]["details"] = details
        self.pool[submission_id]["public_score"] = public_score
        self.pool[submission_id]["public_details"] = public_details

        if username not in self.submissions or \
            self.submissions[username] is None:
            self.submissions[username] = [submission_id]
        else:
            self.submissions[username].append(submission_id)

        # We expect submissions to arrive more or less in the right
        # order, so we insert-sort the new one.
        i = len(self.submissions[username]) - 1
        while i > 0 and \
            self.pool[self.submissions[username][i - 1]]["timestamp"] > \
            self.pool[self.submissions[username][i]]["timestamp"]:
            self.submissions[username][i - 1], \
                self.submissions[username][i] = \
                self.submissions[username][i], \
                self.submissions[username][i - 1]
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
        raise NotImplementedError

    def max_scores(self):
        """Returns the maximum score that one could aim to in this
        problem. Also return the maximum score from the point of view
        of a user that did not play the token. Depend on the subclass.

        return (float, float): maximum score and maximum score with
                               only public testcases.

        """
        logger.error("Unimplemented method max_scores.")
        raise NotImplementedError

    def compute_score(self, submission_id):
        """Computes a score of a single submission. We don't know here
        how to do it, but our subclasses will.

        submission_id (int): the submission to evaluate.

        returns (float, list, float, list): respectively: the score,
                                            the list of additional
                                            information (e.g.
                                            subtasks' score), and the
                                            same information from the
                                            point of view of a user
                                            that did not play a token.

        """
        logger.error("Unimplemented method compute_score.")
        raise NotImplementedError


class ScoreTypeAlone(ScoreType):
    """Intermediate class to manage tasks where the score of a
    submission depends only on the submission itself and not on the
    other submissions' outcome. Remains to implement compute_score to
    obtain the score of a single submission and max_scores.

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
    def max_scores(self):
        """Compute the maximum score of a submission. FIXME: this
        suppose that the outcomes are in [0, 1].

        returns (float, float): maximum score overall and public.

        """
        public_score = 0.0
        score = 0.0
        for public in self.public_testcases:
            if public:
                public_score += self.parameters
            score += self.parameters
        return score, public_score

    def compute_score(self, submission_id):
        """Compute the score of a submission.

        submission_id (int): the submission to evaluate.
        returns (float): the score

        """
        evaluations = self.pool[submission_id]["evaluations"]
        public_score = 0.0
        score = 0.0
        for evaluation, public in zip(evaluations, self.public_testcases):
            if public:
                public_score += evaluation
            score += evaluation
        return score * self.parameters, None, \
               public_score * self.parameters, None


class ScoreTypeGroupMin(ScoreTypeAlone):
    """The score of a submission is the sum of the product of the
    minimum of the ranges with the multiplier of that range.

    Parameters are [{'multiplier': m, 'testcases': t}, ... ] and this
    means that the first group consists of the first t testcases and
    the min will be multiplied by m.

    """
    def max_scores(self):
        """Compute the maximum score of a submission. FIXME: this
        suppose that the outcomes are in [0, 1].

        returns (float, float): maximum score overall and public.

        """
        public_score = 0.0
        score = 0.0
        current = 0
        for parameter in self.parameters:
            next_ = current + parameter[1]
            score += parameter[0]
            if all(self.public_testcases[current:next_]):
                public_score += parameter[0]
            current = next_
        return score, public_score

    def compute_score(self, submission_id):
        """Compute the score of a submission.

        submission_id (int): the submission to evaluate.
        returns (float): the score

        """
        evaluations = self.pool[submission_id]["evaluations"]
        current = 0
        scores = []
        public_scores = []
        public_index = []
        for parameter in self.parameters:
            next_ = current + parameter[1]
            scores.append(min(evaluations[current:next_]) * parameter[0])
            if all(self.public_testcases[current:next_]):
                public_scores.append(scores[-1])
                public_index.append(len(scores) - 1)
            current = next_
        score = sum(scores)
        public_score = sum(public_scores)
        details = ["Subtask %d: %lg" % (i + 1, sc)
                   for i, sc in enumerate(scores)]
        public_details = ["Subtask %d: %lg" % (i + 1, sc)
                          for i, sc in zip(public_index, public_scores)]
        return score, details, public_score, public_details


class ScoreTypeGroupMul(ScoreTypeAlone):
    """Similar to ScoreTypeGroupMin, but with the product instead of
    the minimum.

    """
    def max_scores(self):
        """Compute the maximum score of a submission. FIXME: this
        suppose that the outcomes are in [0, 1].

        returns (float, float): maximum score overall and public.

        """
        public_score = 0.0
        score = 0.0
        current = 0
        for parameter in self.parameters:
            next_ = current + parameter[1]
            score += parameter[0]
            if all(self.public_testcases[current:next_]):
                public_score += parameter[0]
            current = next_
        return score, public_score

    def compute_score(self, submission_id):
        """Compute the score of a submission.

        submission_id (int): the submission to evaluate.
        returns (float): the score

        """
        evaluations = self.pool[submission_id]["evaluations"]
        current = 0
        scores = []
        public_scores = []
        public_index = []
        for parameter in self.parameters:
            next_ = current + parameter[1]
            scores.append(reduce(lambda x, y: x * y,
                                 evaluations[current:next_]) * parameter[0])
            if all(self.public_testcases[current:next_]):
                public_scores.append(scores[-1])
                public_index.append(len(scores) - 1)
            current = next_
        score = sum(scores)
        public_score = sum(public_scores)
        details = ["Subtask %d: %lg" % (i + 1, score)
                   for i, score in scores]
        public_details = ["Subtask %d: %lg" % (i + 1, score)
                          for i, score in zip(public_index, public_scores)]
        return score, details, public_score, public_details


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
        return score, public_score

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
        return score, None, public_score, None
