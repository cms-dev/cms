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


class Multiply(ScoreTypeAlone):
    """The score of a submission is the product of the outcomes,
    multiplied by the integer parameter.

    """
    def max_scores(self):
        """Compute the maximum score of a submission. FIXME: this
        suppose that the outcomes are in [0, 1].

        returns (float, float): maximum score overall and public.

        """
        return round(self.parameters, 2), round(self.parameters, 2)

    def compute_score(self, submission_id):
        """Compute the score of a submission.

        submission_id (int): the submission to evaluate.
        returns (float): the score

        """
        evaluations = self.pool[submission_id]["evaluations"]
        public_score = 1.0
        score = 1.0
        for evaluation, public in zip(evaluations, self.public_testcases):
            if public:
                public_score *= evaluation
            score *= evaluation
        return round(score * self.parameters, 2), None, \
               round(public_score * self.parameters, 2), None
