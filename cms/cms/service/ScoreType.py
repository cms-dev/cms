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


class ScoreTypeAlone:
    """Base class for scoring systems where the score of a submission
    depends only on the submission.
    """

    def __init__(self, parameters):
        self.scores = {}
        self.submission_scores = {}
        self.parameters = parameters
        self.submissions = {}

    def add_submission(self, submission):
        """To call in order to add a submission to the computation of
        all scores.
        """
        self._insert_submission(submission)
        self._sort_submissions(submission.user.username)
        self._insert_submission_score(submission,
                                      self.compute_score(submission))
        self.update_scores(submission)

    def add_token(self, submission):
        """To call when a token is played, so that the scores updates.
        """
        self.update_scores(submission)

    def compute_all_scores(self):
        """Recompute all scores, usually needed only in case of
        problems.
        """
        for submissions in self.submissions.itervalues():
            for submission in submissions:
                self.compute_score(submission)

    def _insert_submission(self, submission):
        """Utility internal method to add a submission to the
        dictionary.
        """
        username = submission.user.username
        if username not in self.submissions or \
                self.submissions[username] == None:
            self.submissions[username] = [submission]
        else:
            self.submissions[username].append(submission)

    def _insert_submission_score(self, submission, score):
        """Utility internal method to add a score to a submission.
        """
        username = submission.user.username
        if username not in self.submission_scores or \
                self.submission_scores[username] == None:
            self.submission_scores[username] = {submission.couch_id: score}
        else:
            self.submission_scores[username][submission.couch_id] = score

    def _sort_submissions(self, username):
        """Utility internal method to sort submissions of a user by
        time.
        """
        self.submissions[username].sort(
            lambda x, y: int(x.timestamp) - int(y.timestamp))

    def update_scores(self, submission):
        """Update the scores of the contest assuming that only this
        submission appeared.
        """
        score = 0.0
        username = submission.user.username
        submissions = self.submissions[username]
        for s in submissions:
            if s.token_timestamp != None:
                score = max(score,
                            self.submission_scores[username][s.couch_id])
        if submissions != []:
            score = \
                max(score,
                    self.submission_scores[username][submissions[-1].couch_id])
        self.scores[username] = score

    def compute_score(self, submission):
        """We don't know here how to compute a score, but our
        subclasses will.

        submission (Submission): the submission to evaluate

        returns (float): the score
        """
        return 0.0


class ScoreTypeSum(ScoreTypeAlone):
    """The score of a submission is the sum of the outcomes.
    """

    def compute_score(self, submission):
        """Compute the score of a submission.

        submission (Submission): the submission to evaluate

        returns (float): the score
        """
        if submission.evaluation_outcome == None:
            logger.error("Evaluated submission without outcome!")
        else:
            return sum(submission.evaluation_outcome)


class ScoreTypeGroupMin(ScoreTypeAlone):
    """The score of a submission is the sum of the product of the
    minimum of the ranges with the multiplier of that range.

    Parameters are [{'multiplier': m, 'testcases': t}, ... ] and this
    means that the first group consists of the first t testcases and
    the min will be multiplied by m.
    """

    def compute_score(self, submission):
        """Compute the score of a submission.

        submission (Submission): the submission to evaluate

        returns (float): the score
        """
        if submission.evaluation_outcome == None:
            logger.error("Evaluated submission without outcome!")
        else:
            current = 0
            score = 0.0
            for parameter in submission.task.score_parameters:
                next_ = current + parameter[1]
                score += min(submission.evaluation_outcome[current:next_]) * \
                    parameter[0]
                current = next_
            return score


class ScoreTypeGroupMul(ScoreTypeAlone):
    """Similar to ScoreTypeGroupMin, but with the product instead of
    the minimum.
    """

    def compute_score(self, submission):
        """Compute the score of a submission.

        submission (Submission): the submission to evaluate

        returns (float): the score
        """
        if submission.evaluation_outcome == None:
            logger("Evaluated submission without outcome!")
        else:
            current = 0
            score = 0.0
            for parameter in submission.task.score_parameters:
                next_ = current + parameter[1]
                score += \
                    reduce(lambda x, y: x * y,
                           submission.evaluation_outcome[current:next_]) * \
                           parameter[0]
                current = next_
            return score


class ScoreTypeRelative:
    """Scoring systems where the score of a submission is the sum of
    the scores for each testcase, and the score of a testcase is the
    ratio between the outcome of that testcase and the best outcome of
    all others submissions (also in the future) that are going to
    contribute to the final score (i.e., the last submission for all
    users, and the submissions where the user used a token). Also
    compared with a "basic" outcome given as a parameter.
    """

    def __init__(self, parameters):
        """Parameters are a list with the best outcomes found by the
        contest managers.
        """
        self.scores = {}
        self.parameters = parameters
        self.best_tokenized_outcomes = []
        for p in self.parameters:
            self.best_tokenized_outcomes.append(p)
        self.submissions = {}

    def add_submission(self, submission):
        """To call in order to add a submission to the computation of
        all scores.
        """
        self._insert_submission(submission)
        self._sort_submissions(submission.user.username)
        self.update_scores(submission)

    def add_token(self, submission):
        """To call when a token is played, so that the scores updates.
        """
        self.update_scores(submission)

    def compute_all_scores(self):
        """Recompute all scores, usually needed only in case of
        problems.
        """
        pass

    def _insert_submission(self, submission):
        """Utility internal method to add a submission to the
        dictionary.
        """
        username = submission.user.username
        if self.submissions[username] == None:
            self.submissions[username] = [submission]
        else:
            self.submissions[username].append(submission)

    def _sort_submissions(self, username):
        """Utility internal method to sort submissions of a user by
        time.
        """
        self.submissions[username].sort(lambda x, y:
                                            x.timestamp - y.timestamp)

    def update_scores(self, submission):
        """Update the scores of the contest assuming that only this
        submission appeared.
        """
        # We find the best outcome for each testcase: first looking
        # the tokenized submission, that are already stored
        best_outcomes = []
        for i, outcome in enumerate(self.best_tokenized_outcomes):
            # Also, if the currently updated submission is tokenized,
            # we update also the best tokenized outcomes.
            if submission.token_timestamp != None:
                self.best_tokenized_outcomes[i] = \
                    max(outcome, submission.evaluation_outcome[i])
            best_outcomes.append(outcome)

        # Then looking at all last submissions.
        for username in self.submissions:
            submissions = self.submissions[username]
            if submissions == []:
                continue
            for i, outcome in enumerate(submissions[-1].evaluation_outcome):
                best_outcomes[i] = max(best_outcomes[i], outcome)

        # Finally, we update the score for each tokenized or last
        # submission, and we update the users' scores.
        for username in self.submissions:
            submissions = self.submissions[username]
            score = 0.0
            for s in submissions:
                s.score = sum([x / y for x, y in zip(s.evaluation_outcome,
                                                     best_outcomes)])
                if s.token_timestamp != None:
                    score = max(score, s.score)
            if submissions != []:
                score = max(score, submissions[-1])
            self.scores[username] = score
