#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2013-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

import logging

from cms import plugin_list
from .abc import ScoreType, ScoreTypeAlone, ScoreTypeGroup


logger = logging.getLogger(__name__)


__all__ = [
    "SCORE_TYPES", "get_score_type", "get_score_type_class",
    # abc
    "ScoreType", "ScoreTypeAlone", "ScoreTypeGroup",
]


SCORE_TYPES = dict((cls.__name__, cls)
                   for cls in plugin_list("cms.grading.scoretypes"))


def get_score_type_class(name):
    """Load the ScoreType class given as parameter."""
    return SCORE_TYPES[name]


def get_score_type(name, parameters, public_testcases):
    """Construct the ScoreType specified by parameters.

    Load the ScoreType class named "name" and instantiate it with the
    data structure obtained by JSON-decoding "parameters" and with the
    dict "public_testcases".

    name (str): the name of the ScoreType class.
    parameters (object): the parameters.
    public_testcases ({str: bool}): for each testcase (identified by
        its codename) a flag telling whether it's public or not.

    return (ScoreType): an instance of the correct ScoreType class.

    """
    class_ = get_score_type_class(name)
    return class_(parameters, public_testcases)
