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


def get_task_type_class(name):
    """Load the TaskType class given as parameter."""
    return plugin_lookup(name,
                         "cms.grading.tasktypes", "tasktypes")


def get_task_type(name=None, parameters=None,
                  dataset=None):
    """Construct the TaskType specified by parameters.

    Load the TaskType class named "name" and instantiate it with the
    data structure obtained by JSON-decoding "parameters".
    If "dataset" is given then all other arguments should be omitted as
    they are obtained from the dataset.

    name (unicode|None): the name of the TaskType class.
    parameters (unicode|None): the JSON-encoded parameters.
    dataset (Dataset|None): the dataset whose TaskType we want (if
        None, use the other parameters to find the task type).

    return (TaskType): an instance of the correct TaskType class.

    raise (ValueError): when the arguments are not consistent or
        cannot be parsed.

    """
    if dataset is not None:
        if any(x is not None for x in (name, parameters)):
            raise ValueError("Need exactly one way to get the task type.")

        name = dataset.task_type
        parameters = dataset.task_type_parameters

    elif any(x is None for x in (name, parameters)):
        raise ValueError("Need exactly one way to get the task type.")

    class_ = get_task_type_class(name)

    try:
        parameters = json.loads(parameters)
    except ValueError as error:
        logger.error("Cannot decode task type parameters.\n%r.", error)
        raise

    return class_(parameters)
