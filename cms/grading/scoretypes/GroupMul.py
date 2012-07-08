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


class GroupMul(ScoreTypeAlone):
    """Similar to GroupMin, but with the product instead of the
    minimum.

    """
    def max_scores(self):
        """Compute the maximum score of a submission. FIXME: this
        suppose that the outcomes are in [0, 1].

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
        current = 0
        scores = []
        public_scores = []
        public_index = []
        for parameter in self.parameters:
            next_ = current + parameter[1]
            scores.append(reduce(lambda x, y: x * y,
                                 (evaluations[idx]
                                  for idx in indices[current:next_]))
                            * parameter[0])
            if all(self.public_testcases[idx]
                   for idx in indices[current:next_]):
                public_scores.append(scores[-1])
                public_index.append(len(scores) - 1)
            current = next_
        details = ["Subtask %d: %lg" % (i + 1, round(score, 2))
                   for i, score in scores]
        public_details = ["Subtask %d: %lg" % (i + 1, round(score, 2))
                          for i, score in zip(public_index, public_scores)]
        score = sum(scores)
        public_score = sum(public_scores)
        return round(score, 2), details, \
               round(public_score, 2), public_details, \
               dict((num, float(evaluations[num])) for num in evaluations)


