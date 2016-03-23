#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2013 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013-2015 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2015 wafrelka <wafrelka@gmail.com>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import json
import logging
import re

from tornado.template import Template


logger = logging.getLogger(__name__)


# Dummy function to mark translatable string.
def N_(message):
    return message


class ScoreType(object):
    """Base class for all score types, that must implement all methods
    defined here.

    """
    TEMPLATE = ""

    def __init__(self, parameters, public_testcases):
        """Initializer.

        parameters (object): format is specified in the subclasses.
        public_testcases (dict): associate to each testcase's codename
                                 a boolean indicating if the testcase
                                 is public.

        """
        self.parameters = parameters
        self.public_testcases = public_testcases

        # Preload the maximum possible scores.
        self.max_score, self.max_public_score, self.ranking_headers = \
            self.max_scores()

    def get_html_details(self, score_details, translator=None):
        """Return an HTML string representing the score details of a
        submission.

        score_details (unicode): the data saved by the score type
            itself in the database; can be public or private.
        translator (function|None): the function to localize strings,
            or None to use the identity.

        return (string): an HTML string representing score_details.

        """
        if translator is None:
            translator = lambda string: string
        try:
            score_details = json.loads(score_details)
        except (TypeError, ValueError):
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
        of a user that did not play the token. And the headers of the
        columns showing extra information (e.g. subtasks) in RWS.
        Depend on the subclass.

        return (float, float, [string]): maximum score and maximum
            score with only public testcases; ranking headers.

        """
        logger.error("Unimplemented method max_scores.")
        raise NotImplementedError("Please subclass this class.")

    def compute_score(self, unused_submission_result):
        """Computes a score of a single submission.

        unused_submission_result (SubmissionResult): the submission
            result of which we want the score

        returns (float, str, float, str, [str]): respectively: the
            score, the HTML string with additional information (e.g.
            testcases' and subtasks' score), and the same information
            from the point of view of a user that did not play a
            token, the list of strings to send to RWS.

        """
        logger.error("Unimplemented method compute_score.")
        raise NotImplementedError("Please subclass this class.")


class ScoreTypeAlone(ScoreType):
    """Intermediate class to manage tasks where the score of a
    submission depends only on the submission itself and not on the
    other submissions' outcome. Remains to implement compute_score to
    obtain the score of a single submission and max_scores.

    """
    pass


class ScoreTypeGroup(ScoreTypeAlone):
    """Intermediate class to manage tasks whose testcases are
    subdivided in groups (or subtasks). The score type parameters must
    be in the form [[m, t, ...], [...], ...], where m is the maximum
    score for the given subtask and t is the parameter for specifying
    testcases.

    If t is int, it is interpreted as the number of testcases
    comprising the subtask (that are consumed from the first to the
    last, sorted by num). If t is unicode, it is interpreted as the regular
    expression of the names of target testcases. All t must have the same type.

    A subclass must implement the method 'get_public_outcome' and
    'reduce'.

    """
    # Mark strings for localization.
    N_("Subtask %d")
    N_("Outcome")
    N_("Details")
    N_("Execution time")
    N_("Memory used")
    N_("N/A")
    TEMPLATE = """\
{% from cms.grading import format_status_text %}
{% from cms.server import format_size %}
{% set idx = 0 %}
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
            ({{ '%g' % round(st["score"], 2) }} / {{ st["max_score"] }})
        </span>
    {% else %}
        <span class="score">
            ({{ _("N/A") }})
        </span>
    {% end %}
    </div>
    <div class="subtask-body">
        <table class="testcase-list">
            <thead>
                <tr>
                    <th class="idx">{{ _("#") }}</th>
                    <th class="outcome">{{ _("Outcome") }}</th>
                    <th class="details">{{ _("Details") }}</th>
                    <th class="execution-time">{{ _("Execution time") }}</th>
                    <th class="memory-used">{{ _("Memory used") }}</th>
                </tr>
            </thead>
            <tbody>
    {% for tc in st["testcases"] %}
        {% set idx = idx + 1 %}
        {% if "outcome" in tc and "text" in tc %}
            {% if tc["outcome"] == "Correct" %}
                <tr class="correct">
            {% elif tc["outcome"] == "Not correct" %}
                <tr class="notcorrect">
            {% else %}
                <tr class="partiallycorrect">
            {% end %}
                    <td class="idx">{{ idx }}</td>
                    <td class="outcome">{{ _(tc["outcome"]) }}</td>
                    <td class="details">
                      {{ format_status_text(tc["text"], _) }}
                    </td>
                    <td class="execution-time">
            {% if "time" in tc and tc["time"] is not None %}
                        {{ _("%(seconds)0.3f s") % {'seconds': tc["time"]} }}
            {% else %}
                        {{ _("N/A") }}
            {% end %}
                    </td>
                    <td class="memory-used">
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

    def retrieve_target_testcases(self):
        """Return the list of the target testcases for each subtask.

        Each element of the list consist of multiple strings.
        Each string represents the testcase name which should be included
        to the corresponding subtask.
        The order of the list is the same as 'parameters'.

        return ([[unicode]]): the list of the target testcases for each task.

        """

        t_params = [p[1] for p in self.parameters]

        if all(isinstance(t, int) for t in t_params):

            # XXX Lexicographical order by codename
            indices = sorted(self.public_testcases.keys())
            current = 0
            targets = []

            for t in t_params:
                next_ = current + t
                targets.append(indices[current:next_])
                current = next_

            return targets

        elif all(isinstance(t, unicode) for t in t_params):

            indices = sorted(self.public_testcases.keys())
            targets = []

            for t in t_params:
                regexp = re.compile(t)
                target = [tc for tc in indices if regexp.match(tc)]
                if not target:
                    raise StandardError(
                        "No testcase matches against the regexp '%s'" % t)
                targets.append(target)

            return targets

        raise StandardError(
            "In the score type parameters, the second value of each element "
            "must have the same type (int or unicode)")

    def max_scores(self):
        """See ScoreType.max_score."""
        score = 0.0
        public_score = 0.0
        headers = list()

        targets = self.retrieve_target_testcases()

        for i, parameter in enumerate(self.parameters):
            target = targets[i]
            score += parameter[0]
            if all(self.public_testcases[idx] for idx in target):
                public_score += parameter[0]
            headers += ["Subtask %d (%g)" % (i + 1, parameter[0])]

        return score, public_score, headers

    def compute_score(self, submission_result):
        """See ScoreType.compute_score."""
        # Actually, this means it didn't even compile!
        if not submission_result.evaluated():
            return 0.0, "[]", 0.0, "[]", \
                json.dumps(["%lg" % 0.0 for _ in self.parameters])

        targets = self.retrieve_target_testcases()
        evaluations = dict((ev.codename, ev)
                           for ev in submission_result.evaluations)
        subtasks = []
        public_subtasks = []
        ranking_details = []

        for st_idx, parameter in enumerate(self.parameters):
            target = targets[st_idx]
            st_score = self.reduce([float(evaluations[idx].outcome)
                                    for idx in target],
                                   parameter) * parameter[0]
            st_public = all(self.public_testcases[idx] for idx in target)
            tc_outcomes = dict((
                idx,
                self.get_public_outcome(
                    float(evaluations[idx].outcome), parameter)
                ) for idx in target)

            testcases = []
            public_testcases = []
            for idx in target:
                testcases.append({
                    "idx": idx,
                    "outcome": tc_outcomes[idx],
                    "text": evaluations[idx].text,
                    "time": evaluations[idx].execution_time,
                    "memory": evaluations[idx].execution_memory,
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

        score = sum(st["score"] for st in subtasks)
        public_score = sum(st["score"]
                           for st in public_subtasks
                           if "score" in st)

        return score, json.dumps(subtasks), \
            public_score, json.dumps(public_subtasks), \
            json.dumps(ranking_details)

    def get_public_outcome(self, unused_outcome, unused_parameter):
        """Return a public outcome from an outcome.

        The public outcome is shown to the user, and this method
        return the public outcome associated to the outcome of a
        submission in a testcase contained in the group identified by
        parameter.

        unused_outcome (float): the outcome of the submission in the
            testcase.
        unused_parameter (list): the parameters of the current group.

        return (float): the public output.

        """
        logger.error("Unimplemented method get_public_outcome.")
        raise NotImplementedError("Please subclass this class.")

    def reduce(self, unused_outcomes, unused_parameter):
        """Return the score of a subtask given the outcomes.

        unused_outcomes ([float]): the outcomes of the submission in
            the testcases of the group.
        unused_parameter (list): the parameters of the group.

        return (float): the public output.

        """
        logger.error("Unimplemented method reduce.")
        raise NotImplementedError("Please subclass this class.")
