#!/usr/bin/env python2
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

import json
import logging

from tornado.template import Template

from cms.grading.ScoreType import ScoreTypeAlone


logger = logging.getLogger(__name__)


# Dummy function to mark translatable string.
def N_(message):
    return message


# class NamedGroup(ScoreTypeGroup):
#     """The score of a submission is the sum of the product of the
#     minimum of the ranges with the multiplier of that range.
# 
#     Parameters are [[m, t], ... ] (see ScoreTypeGroup).
# 
#     """
# 
#     def get_public_outcome(self, outcome, parameter):
#         """See ScoreTypeGroup."""
#         if outcome <= 0.0:
#             return N_("Not correct")
#         elif outcome >= 1.0:
#             return N_("Correct")
#         else:
#             return N_("Partially correct")
# 
#     def reduce(self, outcomes, parameter):
#         """See ScoreTypeGroup."""
#         return min(outcomes)

class NamedGroup(ScoreTypeAlone):
    """The score of a submission is the sum of the scores of all subtasks.
    The score of each subtask is calculated from the scores of the subtask's
    testcases. The formulae used to calculate the score can be specified for
    each subtask. One testcase can belong to multiple subtasks.

    The score type parameters for a task are in the form
    [subtask1, subtask2, ... ] and the score type parameters for each subtask
    are in the form
    { 'name': n, 'score': s, 'files': [f0, f1, ... ], 'reduce': r },
    where n is the name for the given subtask, s is the maximum score for the
    subtask, f0, f1, ... are the names of the testcases that belong to the
    subtask, and r is a method for score calculation.

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
                    <th>{{ _("Execution time") }}</th>
                    <th>{{ _("Memory used") }}</th>
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
                    <td>{{ _(tc["outcome"]) }}</td>
                    <td>{{ format_status_text(tc["text"], _) }}</td>
                    <td>
            {% if "time" in tc and tc["time"] is not None %}
                        {{ _("%(seconds)0.3f s") % {'seconds': tc["time"]} }}
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
        score = 0.0
        public_score = 0.0
        headers = list()

        for i, parameter in enumerate(self.parameters):
            score += parameter['score']
            if all(self.public_testcases[f]
                   for f in parameter['files']):
                public_score += parameter['score']
            headers += ["%s (%g)" % (parameter['name'], parameter['score'])]

        return score, public_score, headers

    def compute_score(self, submission_result):
        """Compute the score of a submission.

        submission_id (int): the submission to evaluate.
        returns (float): the score

        """
        # Actually, this means it didn't even compile!
        if not submission_result.evaluated():
            return 0.0, "[]", 0.0, "[]", \
                json.dumps(["%lg" % 0.0 for _ in self.parameters])

        evaluations = dict((ev.codename, ev)
                           for ev in submission_result.evaluations)
        subtasks = []
        public_subtasks = []
        ranking_details = []

        for st_idx, parameter in enumerate(self.parameters):
            st_score = self.reduce((float(evaluations[f].outcome)
                                    for f in parameter['files']),
                                   parameter) * parameter['score']
            st_public = all(self.public_testcases[f]
                            for f in parameter['files'])
            tc_outcomes = dict((
                f,
                self.get_public_outcome(
                    float(evaluations[f].outcome), parameter)
                ) for f in parameter['files'])

            testcases = []
            public_testcases = []
            for f in parameter['files']:
                testcases.append({
                    "file": f,
                    "outcome": tc_outcomes[f],
                    "text": evaluations[f].text,
                    "time": evaluations[f].execution_time,
                    "memory": evaluations[f].execution_memory,
                    })
                if self.public_testcases[f]:
                    public_testcases.append(testcases[-1])
                else:
                    public_testcases.append({"f": f})
            subtasks.append({
                "idx": st_idx + 1,
                "score": st_score,
                "max_score": parameter['score'],
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
        # return "Partially correct: " + str(parameter['reduce']) + " !!"
        if parameter['reduce'] in ['min', 'mul']:
            if outcome <= 0.0:
                return N_("Not correct")
            elif outcome >= 1.0:
                return N_("Correct")
            else:
                return N_("Partially correct")
        elif parameter['reduce'] == 'threshold':
            if 0.0 <= outcome <= parameter['threshold']:
                return N_("Correct")
            else:
                return N_("Not correct")
        return None

    def reduce(self, outcomes, parameter):
        """Return the score of a subtask given the outcomes.

        outcomes ([float]): the outcomes of the submission in the
                            testcases of the group.
        parameter (list): the parameters of the group.

        return (float): the public output.

        """
        if parameter['reduce'] == 'min':
            return min(outcomes)
        elif parameter['reduce'] == 'mul':
            return reduce(lambda x, y: x * y, outcomes)
        elif parameter['reduce'] == 'threshold':
            if all(0 <= outcome <= parameter['threshold']
                   for outcome in outcomes):
                return 1.0
            else:
                return 0.0
        return None
