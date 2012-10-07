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

from cms.grading.ScoreType import ScoreTypeAlone

from tornado.template import Template


class Sum(ScoreTypeAlone):
    """The score of a submission is the sum of the outcomes,
    multiplied by the integer parameter.

    """
    TEMPLATE = """\
{% from cms.server import format_size %}
<table class="testcase-list">
    <thead>
        <tr>
            <th>Outcome</th>
            <th>Details</th>
            <th>Time</th>
            <th>Memory</th>
        </tr>
    </thead>
    <tbody>
    {% for tc in testcases %}
        <tr class="{{ tc["class"] if (tc["public"] or show_private) else "undefined" }}">
        {% if tc["public"] or show_private %}
            <td>{{ tc["outcome"] }}</td>
            <td>{{ tc["text"] }}</td>
            <td>
            {% if tc["time"] is not None %}
                {{ "%(seconds)0.3f s" % {'seconds': tc["time"]} }}
            {% else %}
                N/A
            {% end %}
            </td>
            <td>
            {% if tc["memory"] is not None %}
                {{ format_size(tc["memory"]) }}
            {% else %}
                N/A
            {% end %}
            </td>
        {% else %}
            <td colspan="4">
                N/A
            </td>
        {% end %}
        </tr>
    {% end %}
    </tbody>
</table>"""

    def max_scores(self):
        """Compute the maximum score of a submission.

        returns (float, float): maximum score overall and public.

        """
        public_score = 0.0
        score = 0.0
        for public in self.public_testcases.itervalues():
            if public:
                public_score += self.parameters
            score += self.parameters
        return round(score, 2), round(public_score, 2)

    def compute_score(self, submission_id):
        """Compute the score of a submission.

        See the same method in ScoreType for details.

        """
        def class_score_testcase(word):
            if word == "Correct":
                return "correct"
            elif word == "Not correct":
                return "notcorrect"
            else:
                return "partiallycorrect"

        evaluations = self.pool[submission_id]["evaluations"]
        testcases = []
        for idx in evaluations:
            tc_outcome = self.get_public_outcome(
                evaluations[idx]["outcome"])
            testcases.append({
                "idx": idx,
                "public": self.public_testcases[idx],
                "score": evaluations[idx]["outcome"],
                "max_score": 1.0,
                "outcome": tc_outcome,
                "class": class_score_testcase(tc_outcome),
                "text": evaluations[idx]["text"],
                "time": evaluations[idx]["time"],
                "memory": evaluations[idx]["memory"],
                })

        score = sum(tc["score"] for tc in testcases)
        public_score = sum(tc["score"] for tc in testcases if tc["public"])

        details = \
            Template(self.TEMPLATE).generate(testcases=testcases,
                                             show_private=True)
        public_details = \
            Template(self.TEMPLATE).generate(testcases=testcases,
                                             show_private=False)

        return round(score * self.parameters, 2), details, \
               round(public_score * self.parameters, 2), public_details, \
               []

    def get_public_outcome(self, outcome):
        """Return a public outcome from an outcome.

        outcome (float): the outcome of the submission.

        return (float): the public output.

        """
        if outcome <= 0.0:
            return "Not correct"
        elif outcome >= 1.0:
            return "Correct"
        else:
            return "Partially correct"
