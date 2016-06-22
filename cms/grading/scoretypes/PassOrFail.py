#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import json

from cms.grading.ScoreType import ScoreTypeAlone


# Dummy function to mark translatable string.
def N_(message):
    return message


class PassOrFail(ScoreTypeAlone):
    """The score of a submission is the sum of the outcomes,
    multiplied by the integer parameter.

    """
    # Mark strings for localization.
    N_("Outcome")
    N_("Details")
    N_("Execution time")
    N_("Memory used")
    N_("N/A")
    TEMPLATE = """\
{% from cms.grading import format_status_text %}
{% from cms.server import format_size %}
{% set correct = True %}
{% for tc in details %}
    {% if "outcome" in tc and "text" in tc and tc["outcome"] != "Correct" %}
        {% set correct = False %}
    {% end %}
{% end %}
{% if not correct %}
        <table class="testcase-list">
            <thead>
                <tr>
                    <th class="outcome">{{ _("Outcome") }}</th>
                    <th class="details">{{ _("Details") }}</th>
                    <th class="execution-time">{{ _("Execution time") }}</th>
                    <th class="memory-used">{{ _("Memory used") }}</th>
                </tr>
            </thead>
            <tbody>
        {% for tc in details %}
            {% if "outcome" in tc and "text" in tc and tc["outcome"] != "Correct" %}
                <tr class="notcorrect">
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
                </tr>
                {% break %}
            {% end %}
        {% end %}
            </tbody>
        </table>
{% end %}"""

    @staticmethod
    def format_score(score, max_score, unused_score_details,
                     score_precision, unused_translator=None):
        """See ScoreType.format_score."""
        if score < max_score:
            return N_("Rejected")
        else:
            return N_("Accepted")

    def max_scores(self):
        """See ScoreType.max_score."""
        public_score = self.parameters
        score = self.parameters
        return score, public_score, []

    def compute_score(self, submission_result):
        """See ScoreType.compute_score."""
        # Actually, this means it didn't even compile!
        if not submission_result.evaluated():
            return 0.0, "[]", 0.0, "[]", []

        # XXX Lexicographical order by codename
        indices = sorted(self.public_testcases.keys())
        evaluations = dict((ev.codename, ev)
                           for ev in submission_result.evaluations)
        testcases = []
        public_testcases = []
        score = self.parameters
        public_score = self.parameters

        for idx in indices:
            outcome = float(evaluations[idx].outcome)
            if outcome <= 0.0:
                if self.public_testcases[idx]:
                    public_score = 0
                score = 0
            tc_outcome = self.get_public_outcome(outcome)
            testcases.append({
                "idx": idx,
                "outcome": tc_outcome,
                "text": evaluations[idx].text,
                "time": evaluations[idx].execution_time,
                "memory": evaluations[idx].execution_memory,
                })
            if self.public_testcases[idx]:
                public_testcases.append(testcases[-1])
            else:
                public_testcases.append({"idx": idx})

        return score, json.dumps(testcases), \
            public_score, json.dumps(public_testcases), \
            []

    def get_public_outcome(self, outcome):
        """Return a public outcome from an outcome.

        outcome (float): the outcome of the submission.

        return (float): the public output.

        """
        if outcome <= 0.0:
            return N_("Not correct")
        else:
            return N_("Correct")
