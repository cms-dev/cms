#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2013 Stefano Maggiolo <s.maggiolo@gmail.com>
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

import simplejson as json

from cms import logger

from tornado.template import Template


class ScoreType:
    """Base class for all score types, that must implement all methods
    defined here.

    """
    TEMPLATE = ""

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

    def add_submission(self, submission_id, timestamp, username, evaluated,
                       evaluations, tokened):
        """To call in order to add a submission to the computation of
        all scores.

        submission_id (int): id of the new submission.
        timestamp (int): time of submission.
        username (string): username of the owner of the submission.
        evaluated (bool): if the submission compiled correctly.
        evaluations (dict): associate to each evaluation's num a
                            dictionary {'outcome': xxx, 'text': yyy}.
        tokened (bool): if the user played a token on submission.

        """
        self.pool[submission_id] = {
            "timestamp": timestamp,
            "username": username,
            "evaluated": evaluated,
            "evaluations": evaluations,
            "tokened": tokened,
            "score": None,
            "details": None,
            "public_score": None,
            "public_details": None,
            "ranking_details": None,
            }
        self.pool[submission_id]["score"], \
            self.pool[submission_id]["details"], \
            self.pool[submission_id]["public_score"], \
            self.pool[submission_id]["public_details"], \
            self.pool[submission_id]["ranking_details"] = \
            self.compute_score(submission_id)

        if username not in self.submissions or \
            self.submissions[username] is None:
            self.submissions[username] = [submission_id]
        else:
            self.submissions[username].append(submission_id)

        # We expect submissions to arrive more or less ordered by
        # timestamp, so we insert-sort the new one.
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

    def update_scores(self, new_submission_id):
        """Update the scores of the users assuming that only this
        submission appeared or was modified (i.e., tokened). The way
        to do this depends on the subclass, so we leave this
        unimplemented.

        new_submission_id (int): id of the newly added submission.

        """
        logger.error("Unimplemented method update_scores.")
        raise NotImplementedError

    def get_html_details(self, score_details, translator=None):
        """Return an HTML string representing the score details of a
        submission.

        score_details (dict): the data saved by the score type itself
                              in the database; can be public or
                              private.
        translator (function): the function to localize strings.
        return (string): an HTML string representing score_details.

        """
        if translator is None:
            translator = lambda string: string
        try:
            score_details = json.loads(score_details)
        except (json.decoder.JSONDecodeError, TypeError):
            # TypeError raised if score_details is None
            logger.error("Found a null or non-JSON score details string. "
                         "Try invalidating scores.")
            return translator("Score details temporarily unavailable.")
        else:
            return Template(self.TEMPLATE).generate(details=score_details,
                                                    _=translator)

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

        returns (float, str, float, str, [str]): respectively: the
            score, the HTML string with additional information (e.g.
            testcases' and subtasks' score), and the same information
            from the point of view of a user that did not play a
            token, the list of strings to send to RWS.

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
    be in the form [[m, t, ...], [...], ...], where m is the maximum
    score for the given subtask and t is the number of testcases
    comprising the subtask (that are consumed from the first to the
    last, sorted by num).

    A subclass must implement the method 'get_public_outcome' and
    'reduce'.

    """
    TEMPLATE = """\
{% from cms.server import format_size %}
{% for st in details %}
    {% if "score" in st and "max_score" in st %}
        {% if st["score"] >= st["max_score"] %}
<div class="subtask correct">
        {% elif st["score"] <= 0.0 %}
<div class="subtask notcorrect">
        {% else %}
<div class="subtask partiallycorrect">
        {% end %}
    {% else %}
<div class="subtask undefined">
    {% end %}
    <div class="subtask-head">
        <span class="title">
            {{ _("Subtask %d") % st["idx"] }}
        </span>
    {% if "score" in st and "max_score" in st %}
        <span class="score">
            {{ '%g' % round(st["score"], 2) }} / {{ st["max_score"] }}
        </span>
    {% else %}
        <span class="score">
            {{ _("N/A") }}
        </span>
    {% end %}
    </div>
    <div class="subtask-body">
        <table class="testcase-list">
            <thead>
                <tr>
                    <th>{{ _("Outcome") }}</th>
                    <th>{{ _("Details") }}</th>
                    <th>{{ _("Time") }}</th>
                    <th>{{ _("Memory") }}</th>
                </tr>
            </thead>
            <tbody>
    {% for tc in st["testcases"] %}
        {% if "outcome" in tc and "text" in tc %}
            {% if tc["outcome"] == "Correct" %}
                <tr class="correct">
            {% elif tc["outcome"] == "Not correct" %}
                <tr class="notcorrect">
            {% else %}
                <tr class="partiallycorrect">
            {% end %}
                    <td>{{ tc["outcome"] }}</td>
                    <td>{{ tc["text"] }}</td>
                    <td>
            {% if "time" in tc and tc["time"] is not None %}
                        {{ "%(seconds)0.3f s" % {'seconds': tc["time"]} }}
            {% else %}
                        {{ _("N/A") }}
            {% end %}
                    </td>
                    <td>
            {% if "memory" in tc and tc["memory"] is not None %}
                        {{ format_size(tc["memory"]) }}
            {% else %}
                        {{ _("N/A") }}
            {% end %}
                    </td>
        {% else %}
                <tr class="undefined">
                    <td colspan="4">
                        {{ _("N/A") }}
                    </td>
                </tr>
        {% end %}
    {% end %}
            </tbody>
        </table>
    </div>
</div>
{% end %}"""

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
        return score, public_score

    def compute_score(self, submission_id):
        """Compute the score of a submission.

        submission_id (int): the submission to evaluate.
        returns (float): the score

        """
        if not self.pool[submission_id]["evaluated"]:
            return 0.0, "[]", 0.0, "[]", ["%lg" % 0.0 for _ in self.parameters]

        indices = sorted(self.public_testcases.keys())
        evaluations = self.pool[submission_id]["evaluations"]
        subtasks = []
        public_subtasks = []
        ranking_details = []
        tc_start = 0
        tc_end = 0

        for st_idx, parameter in enumerate(self.parameters):
            tc_end = tc_start + parameter[1]
            st_score = self.reduce([float(evaluations[idx]["outcome"])
                                    for idx in indices[tc_start:tc_end]],
                                   parameter) * parameter[0]
            st_public = all(self.public_testcases[idx]
                            for idx in indices[tc_start:tc_end])
            tc_outcomes = dict((
                idx,
                self.get_public_outcome(
                    float(evaluations[idx]["outcome"]), parameter)
                ) for idx in indices[tc_start:tc_end])

            testcases = []
            public_testcases = []
            for idx in indices[tc_start:tc_end]:
                testcases.append({
                    "idx": idx,
                    "outcome": tc_outcomes[idx],
                    "text": evaluations[idx]["text"],
                    "time": evaluations[idx]["time"],
                    "memory": evaluations[idx]["memory"],
                    })
                if self.public_testcases[idx]:
                    public_testcases.append(testcases[-1])
                else:
                    public_testcases.append({"idx": idx})
            subtasks.append({
                "idx": st_idx + 1,
                "score": st_score,
                "max_score": parameter[0],
                "testcases": testcases,
                })
            if st_public:
                public_subtasks.append(subtasks[-1])
            else:
                public_subtasks.append({
                    "idx": st_idx + 1,
                    "testcases": public_testcases,
                    })

            ranking_details.append("%g" % round(st_score, 2))

            tc_start = tc_end

        score = sum(st["score"] for st in subtasks)
        public_score = sum(st["score"] for st in public_subtasks
                                       if "score" in st)

        return score, json.dumps(subtasks), \
               public_score, json.dumps(public_subtasks), \
               ranking_details

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
