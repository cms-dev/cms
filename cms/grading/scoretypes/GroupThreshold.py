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

from cms.grading.ScoreType import ScoreTypeGroup


class GroupThreshold(ScoreTypeGroup):
    """The score of a submission is the sum of: the multiplier of the
    range if all outcomes are between 0.0 and the threshold, or 0.0.

    Parameters are [[m, t, T], ... ] (see ScoreTypeGroup), where T is
    the threshold for the group.

    """

    def get_public_outcome(self, outcome, parameter):
        """See ScoreTypeGroup."""
        threshold = parameter[2]
        if 0.0 <= outcome <= threshold:
            return "Correct"
        else:
            return "Not correct"

    def reduce(self, outcomes, parameter):
        """See ScoreTypeGroup."""
        threshold = parameter[2]
        if all(0 <= outcome <= threshold
               for outcome in outcomes):
            return 1.0
        else:
            return 0.0
