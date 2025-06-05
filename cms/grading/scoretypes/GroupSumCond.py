#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2018 Ahto Truu <ahto.truu@ut.ee>
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

from cms.grading.scoretypes.GroupSum import GroupSum

class GroupSumCond(GroupSum):
    """The score of a submission is the sum of group scores,
    and each group score is the sum of testcase scores in the group,
    except the scores for "conditional" groups are only given if the
    solution gets at least some points for the "unconditional" groups.
    Parameters are [[m, t, f], ... ]. See ScoreTypeGroup for m and t.
    The flag f must be one of "U", "C", "E":
    "U" for unconditional group whose score is always counted,
    "C" for conditional group whose score is only counted
    if the total for unconditional scores is non-zero,
    "E" for examples (these typically don't score points, but even
    if they do, they do not affect the conditional groups).

    """

    def max_scores(self):
        score, public_score, headers = GroupSum.max_scores(self)
        for st_idx, parameter in enumerate(self.parameters):
            if parameter[2] == "C":
                headers[st_idx] += " ***"
        return score, public_score, headers

    def compute_score(self, submission_result):
        score, subtasks, public_score, public_subtasks, ranking_details = GroupSum.compute_score(self, submission_result)
        if len(subtasks) == len(self.parameters):
            u_score = 0
            for st_idx, parameter in enumerate(self.parameters):
                if parameter[2] == "U":
                    u_score += subtasks[st_idx]["score_fraction"] * parameter[0]
            if u_score == 0:
                for st_idx, parameter in enumerate(self.parameters):
                    if parameter[2] == "C":
                        st_score = subtasks[st_idx]["score_fraction"] * parameter[0]
                        score -= st_score
                        if public_subtasks[st_idx] == subtasks[st_idx]:
                            public_score -= st_score
                        ranking_details[st_idx] = "0"
                        subtasks[st_idx]["score_ignore"] = True
        return score, subtasks, public_score, public_subtasks, ranking_details
