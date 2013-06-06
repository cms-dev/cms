#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
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

import simplejson as json

from cms import logger, plugin_lookup


def get_score_type_class(name):
    return plugin_lookup(name,
                         "cms.grading.scoretypes", "scoretypes")


def get_score_type(name=None, parameters=None, public_testcases=None,
                   dataset=None):
    """Given a dataset, instantiate the corresponding ScoreType class.

    dataset (Dataset): the Dataset whose ScoreType we want

    return (object): an instance of the correct ScoreType class.

    """
    if dataset is not None:
        if any(x is not None for x in (name, parameters, public_testcases)):
            raise ValueError("Need exactly one way to get the score type.")

        name = dataset.score_type
        parameters = dataset.score_type_parameters
        public_testcases = dict((tc.num, tc.public)
                                for tc in dataset.testcases)

    elif any(x is None for x in (name, parameters, public_testcases)):
        raise ValueError("Need exactly one way to get the score type.")

    class_ = get_score_type_class(name)

    try:
        parameters = json.loads(parameters)
    except json.decoder.JSONDecodeError as error:
        logger.error("Cannot decode score type parameters.\n%r." % error)
        raise

    return class_(parameters, public_testcases)
