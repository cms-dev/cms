#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from cms.grading.ScoreType import ScoreType

import simplejson as json
import logging


logger = logging.getLogger(__name__)


# Dummy function to mark translatable string.
def N_(message):
    return message


class AIOCCodebreakerScoreType(ScoreType):
    """The score of a submission is 20 - sum(penalties) from previous
    submissions. These are passed into __init__ as parameters

    Parameters are a list of integers, containing the results of previous
    evaluations. The evaluator returns -1 if the provided files do not break the
    code, -2 if the provided input file doesn't produce the provided output
    file, -3 if the provided input file is insane, and 1 if the input breaks the
    code. These can be used to implement a custom score based on previous
    evaluation results.

    """
    TEMPLATE = """\
{% from cms.grading import format_status_text %}
{% for st in details %}
    <div>
    {{ format_status_text(st['text'], _) }}
    </div>
{% end %}
"""

    def get_public_outcome(self, score):
        if score == 1:
            return "Broken"
        else:
            return "Not broken"

    def max_scores(self):
        """See ScoreType.max_scores"""
        return (20., 20., [])

    def compute_score(self, submission_result):
        """See ScoreType.compute_score"""
        indices = self.public_testcases.keys()
        evaluations = dict((ev.codename, ev)
                           for ev in submission_result.evaluations)

        assert(len(indices) == 1)
        score = 0
        public_score = 0
        testcases = []
        public_testcases = []
        correct = False

        for idx in indices:
            this_score = float(evaluations[idx].outcome)
            if this_score == 1:
                correct = True
                for s in self.parameters:
                    s = float(s)
                    if s <= -2:
                        score -= 2
                    elif s == -1:
                        score -= 1
                    elif s == 1:
                        break
                score += 20
            tc_outcome = self.get_public_outcome(this_score)
            testcases.append({
                "idx": idx,
                "outcome": tc_outcome,
                "text": evaluations[idx].text,
            })
            public_testcases.append(testcases[-1])
        if not correct:
            score = 0
        public_score = score

        return score, json.dumps(testcases), \
            public_score, json.dumps(public_testcases), \
            json.dumps([])
