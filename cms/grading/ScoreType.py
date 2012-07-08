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


"""In this file there is the basic infrastructure from which we can
build a score type.

A score type is a class that receives all submissions for a task and
assign them a score, keeping the global state of the scoring for the
task.

"""

from cms import logger

from tornado.template import Template


class ScoreType:
    """Base class for all score types, that must implement all methods
    defined here.

    """
    def __init__(self, parameters, public_testcases):
        """Initializer.

        parameters (object): format is specified in the subclasses.
        public_testcases (dict): associate to each testcase's num a
                                 boolean indicating if the testcase is
                                 public.

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
        self.max_score, self.max_public_score = self.max_scores()

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
        evaluations (dict): associate to each evaluation's num a
                            dictionary {'outcome': xxx, 'text': yyy}.
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
        self.pool[submission_id]["score"], \
            self.pool[submission_id]["details"], \
            self.pool[submission_id]["public_score"], \
            self.pool[submission_id]["public_details"] = \
            self.compute_score(submission_id)

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

        returns (float, str, float, str): respectively: the score, the
                                          HTML string with additional
                                          information (e.g.
                                          testcases' and subtasks'
                                          score), and the same
                                          information from the point
                                          of view of a user that did
                                          not play a token.

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


class ScoreTypeGroup(ScoreTypeAlone):
    """Intermediate class to manage tasks whose testcases are
    subdivided in groups (or subtasks). The score type parameters must
    be in the form [[m, t, ...]], where m is the maximum score for the
    given subtask and t is the number of testcases comprising the
    subtask (that are consumed from the first to the last, sorted by
    num).

    A subclass must implement the method 'get_public_outcome' and
    'reduce'.

    """
    TEMPLATE = """\
<table>
 <thead>
  <tr>
   <th>Outcome</th>
   <th>Details</th>
  </tr>
 </thead>
 <tbody>
   {% for subtask in subtasks %}
   <tr>
    <td colspan="2">
     <strong>{{ subtask["title"] }}</strong>
    </td>
   </tr>
     {% for testcase in subtask["testcases"] %}
   <tr>
    <td>{{ testcase["outcome"] }}</td>
    <td>{{ testcase["text"] }}</td>
   </tr>
     {% end %}
   {% end %}
 </tbody>
</table>"""

    def max_scores(self):
        """Compute the maximum score of a submission.

        returns (float, float): maximum score overall and public.

        """
        indices = sorted(self.public_testcases.keys())
        public_score = 0.0
        score = 0.0
        current = 0
        for parameter in self.parameters:
            next_ = current + parameter[1]
            score += parameter[0]
            if all(self.public_testcases[idx]
                   for idx in indices[current:next_]):
                public_score += parameter[0]
            current = next_
        return round(score, 2), round(public_score, 2)

    def compute_score(self, submission_id):
        """Compute the score of a submission.

        submission_id (int): the submission to evaluate.
        returns (float): the score

        """
        indices = sorted(self.public_testcases.keys())
        evaluations = self.pool[submission_id]["evaluations"]
        unowned_testcases = []
        subtasks = []
        public_subtasks = []
        current = 0
        scores = []
        public_scores = []
        for subtask_idx, parameter in enumerate(self.parameters):
            next_ = current + parameter[1]
            scores.append(self.reduce([evaluations[idx]["outcome"]
                                       for idx in indices[current:next_]],
                                      parameter)
                          * parameter[0])
            subtasks.append({
                "title": "Subtask %d: %lg/%lg" % (subtask_idx + 1,
                                                  scores[-1],
                                                  parameter[0]),
                "testcases": [{
                    "outcome": self.get_public_outcome(
                        evaluations[idx]["outcome"], parameter),
                    "text": evaluations[idx]["text"],
                    }
                    for idx in indices[current:next_]],
                })
            if all(self.public_testcases[idx]
                   for idx in indices[current:next_]):
                public_subtasks.append(subtasks[-1])
                public_scores.append(scores[-1])
            else:
                unowned_testcases += [{
                    "outcome": self.get_public_outcome(
                        evaluations[idx]["outcome"], parameter),
                    "text": evaluations[idx]["text"],
                    }
                    for idx in indices[current:next_]
                    if self.public_testcases[idx]]
            current = next_

        if unowned_testcases != []:
            public_subtasks.append({
                "title": "Additional public testcases",
                "testcases": unowned_testcases,
                })

        score = sum(scores)
        public_score = sum(public_scores)

        details = Template(self.TEMPLATE).generate(subtasks=subtasks)
        public_details = \
            Template(self.TEMPLATE).generate(subtasks=public_subtasks)

        return round(score, 2), details, \
               round(public_score, 2), public_details

    def get_public_outcome(self, outcome, parameter):
        """Return a public outcome from an outcome.

        The public outcome is shown to the user, and this method
        return the public outcome associated to the outcome of a
        submission in a testcase contained in the group identified by
        parameter.

        outcome (float): the outcome of the submission in the
                         testcase.
        parameter (list): the parameters of the current group.

        return (float): the public output.

        """
        logger.error("Unimplemented method get_public_outcome.")
        raise NotImplementedError

    def reduce(self, outcomes, parameter):
        """Return the score of a subtask given the outcomes.

        outcomes ([float]): the outcomes of the submission in the
                            testcases of the group.
        parameter (list): the parameters of the group.

        return (float): the public output.

        """
        logger.error("Unimplemented method reduce.")
        raise NotImplementedError
