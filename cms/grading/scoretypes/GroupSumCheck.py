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

from cms.grading.scoretypes.GroupSum import GroupSum

class GroupSumCheck(GroupSum):
    """The score of a submission is the sum of group scores,
    and each group score is the sum of testcase scores in the group,
    except when any testcase scores is negative, the total for the
    whole group is zero.
    """

    def reduce(self, outcomes, parameter):
        """See ScoreTypeGroup."""
        if min(outcomes) < 0: return 0.0
        return sum(outcomes) / len(outcomes)

