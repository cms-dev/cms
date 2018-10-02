#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
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

from . import ScoreTypeAlone


# Dummy function to mark translatable string.
def N_(message):
    return message


class Sum(ScoreTypeAlone):
    """The score of a submission is the sum of the outcomes,
    multiplied by the integer parameter.

    """
    # Mark strings for localization.
    N_("#")
    N_("Outcome")
    N_("Details")
    N_("Execution time")
    N_("Memory used")
    N_("N/A")
    TEMPLATE = """\
<table class="testcase-list">
    <thead>
        <tr>
            <th class="idx">
                {% trans %}#{% endtrans %}
            </th>
            <th class="outcome">
                {% trans %}Outcome{% endtrans %}
            </th>
            <th class="details">
                {% trans %}Details{% endtrans %}
            </th>
    {% if feedback_level == FEEDBACK_LEVEL_FULL %}
            <th class="execution-time">
                {% trans %}Execution time{% endtrans %}
            </th>
            <th class="memory-used">
                {% trans %}Memory used{% endtrans %}
            </th>
    {% endif %}
        </tr>
    </thead>
    <tbody>
    {% for tc in details %}
        {% if "outcome" in tc and "text" in tc %}
            {% if tc["outcome"] == "Correct" %}
        <tr class="correct">
            {% elif tc["outcome"] == "Not correct" %}
        <tr class="notcorrect">
            {% else %}
        <tr class="partiallycorrect">
            {% endif %}
            <td class="idx">{{ loop.index }}</td>
            <td class="outcome">{{ _(tc["outcome"]) }}</td>
            <td class="details">{{ tc["text"]|format_status_text }}</td>
            {% if feedback_level == FEEDBACK_LEVEL_FULL %}
            <td class="execution-time">
                {% if tc["time"] is not none %}
                {{ tc["time"]|format_duration }}
                {% else %}
                {% trans %}N/A{% endtrans %}
                {% endif %}
            </td>
            <td class="memory-used">
                {% if tc["memory"] is not none %}
                {{ tc["memory"]|format_size }}
                {% else %}
                {% trans %}N/A{% endtrans %}
                {% endif %}
            </td>
            {% endif %}
        {% else %}
        <tr class="undefined">
            <td colspan="5">
                {% trans %}N/A{% endtrans %}
            </td>
        </tr>
        {% endif %}
    {% endfor %}
    </tbody>
</table>"""

    def max_scores(self):
        """See ScoreType.max_score."""
        public_score = 0.0
        score = 0.0
        for public in self.public_testcases.values():
            if public:
                public_score += self.parameters
            score += self.parameters
        return score, public_score, []

    def compute_score(self, submission_result):
        """See ScoreType.compute_score."""
        # Actually, this means it didn't even compile!
        if not submission_result.evaluated():
            return 0.0, [], 0.0, [], []

        # XXX Lexicographical order by codename
        indices = sorted(self.public_testcases.keys())
        evaluations = dict((ev.codename, ev)
                           for ev in submission_result.evaluations)
        testcases = []
        public_testcases = []
        score = 0.0
        public_score = 0.0

        for idx in indices:
            this_score = float(evaluations[idx].outcome) * self.parameters
            tc_outcome = self.get_public_outcome(this_score)
            score += this_score
            testcases.append({
                "idx": idx,
                "outcome": tc_outcome,
                "text": evaluations[idx].text,
                "time": evaluations[idx].execution_time,
                "memory": evaluations[idx].execution_memory,
                })
            if self.public_testcases[idx]:
                public_score += this_score
                public_testcases.append(testcases[-1])
            else:
                public_testcases.append({"idx": idx})

        return score, testcases, public_score, public_testcases, []

    def get_public_outcome(self, outcome):
        """Return a public outcome from an outcome.

        outcome (float): the outcome of the submission.

        return (float): the public output.

        """
        if outcome <= 0.0:
            return N_("Not correct")
        elif outcome >= self.parameters:
            return N_("Correct")
        else:
            return N_("Partially correct")
