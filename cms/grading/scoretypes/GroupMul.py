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

from functools import reduce

from . import ScoreTypeGroup


# Dummy function to mark translatable string.
def N_(message):
    return message


class GroupMul(ScoreTypeGroup):
    """The score of a submission is the sum of the product of the
    product of the ranges with the multiplier of that range.

    Parameters are [[m, t], ... ] (see ScoreTypeGroup).

    """

    def get_public_outcome(self, outcome, parameter):
        """See ScoreTypeGroup."""
        if outcome <= 0.0:
            return N_("Not correct")
        elif outcome >= 1.0:
            return N_("Correct")
        else:
            return N_("Partially correct")

    def reduce(self, outcomes, parameter):
        """See ScoreTypeGroup."""
        return reduce(lambda x, y: x * y, outcomes)
