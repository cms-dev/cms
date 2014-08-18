#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

import json
import logging

from cms import plugin_lookup


logger = logging.getLogger(__name__)


def get_score_type_class(name):
    """Load the ScoreType class given as parameter."""
    return plugin_lookup(name,
                         "cms.grading.scoretypes", "scoretypes")


def get_score_type(name=None, parameters=None, public_testcases=None,
                   dataset=None):
    """Construct the ScoreType specified by parameters.

    Load the ScoreType class named "name" and instantiate it with the
    data structure obtained by JSON-decoding "parameters" and with the
    dict "public_testcases".
    If "dataset" is given then all other arguments should be omitted as
    they are obtained from the dataset.

    name (unicode|None): the name of the ScoreType class.
    parameters (unicode|None): the JSON-encoded parameters.
    public_testcases ({str: bool}|None): for each testcase (identified
        by its codename) a flag telling whether it's public or not.
    dataset (Dataset|None): the dataset whose ScoreType we want.

    return (ScoreType): an instance of the correct ScoreType class.

    """
    if dataset is not None:
        if any(x is not None for x in (name, parameters, public_testcases)):
            raise ValueError("Need exactly one way to get the score type.")

        name = dataset.score_type
        parameters = dataset.score_type_parameters
        public_testcases = dict((k, tc.public)
                                for k, tc in dataset.testcases.iteritems())

    elif any(x is None for x in (name, parameters, public_testcases)):
        raise ValueError("Need exactly one way to get the score type.")

    class_ = get_score_type_class(name)

    try:
        parameters = json.loads(parameters)
    except ValueError as error:
        logger.error("Cannot decode score type parameters.\n%r.", error)
        raise

    return class_(parameters, public_testcases)
