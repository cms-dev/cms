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
<table>
 <thead>
  <tr>
   <th>Outcome</th>
   <th>Details</th>
  </tr>
 </thead>
 <tbody>
   {% for testcase in testcases %}
   <tr>
    <td>{% raw testcase["outcome"] %}</td>
    <td>{{ testcase["text"] }}</td>
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
        evaluations = self.pool[submission_id]["evaluations"]
        testcases = []
        public_testcases = []
        public_score = 0.0
        score = 0.0
        for idx in evaluations:
            score += evaluations[idx]["outcome"]
            public_outcomes = dict((idx, self.get_public_outcome(
                evaluations[idx]["outcome"],
                parameter))
                                   for idx in indices[current:next_])
            testcases.append({
                "outcome": "<span class=\"%s\">%s</span>" % (
                    class_score_testcase(public_outcomes[idx]),
                    public_outcomes[idx]),
                "text": evaluations[idx]["text"],
                })
            if self.public_testcases[idx]:
                public_score += evaluations[idx]["outcome"]
                public_testcases.append(testcases[-1])

        details = Template(self.TEMPLATE).generate(testcases=testcases)
        public_details = \
            Template(self.TEMPLATE).generate(testcases=public_testcases)

        return round(score * self.parameters, 2), details, \
               round(public_score * self.parameters, 2), public_details

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
