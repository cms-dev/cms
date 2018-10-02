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
from .abc import TaskType
from .util import create_sandbox, delete_sandbox, \
    is_manager_for_compilation, set_configuration_error, \
    check_executables_number, check_files_number, check_manager_present, \
    eval_output


logger = logging.getLogger(__name__)


__all__ = [
    "TASK_TYPES", "get_task_type_class", "get_task_type",
    # abc
    "TaskType",
    # util
    "create_sandbox", "delete_sandbox",
    "is_manager_for_compilation", "set_configuration_error",
    "check_executables_number", "check_files_number", "check_manager_present",
    "eval_output",
]


TASK_TYPES = dict((cls.__name__, cls)
                  for cls in plugin_list("cms.grading.tasktypes"))


def get_task_type_class(name):
    """Load the TaskType class given as parameter."""
    return TASK_TYPES[name]


def get_task_type(name, parameters):
    """Construct the TaskType specified by parameters.

    Load the TaskType class named "name" and instantiate it with the
    data structure obtained by JSON-decoding "parameters".

    name (str): the name of the TaskType class.
    parameters (object): the parameters.

    return (TaskType): an instance of the correct TaskType class.

    raise (ValueError): when the arguments are not consistent or
        cannot be parsed.

    """
    class_ = get_task_type_class(name)
    return class_(parameters)
