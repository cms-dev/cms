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

import imp
import os
import simplejson as json

from cms import config, logger


def _try_import(score_type, dir_name):
    """Try to import a module called module_name from a directory
    called dir_name.

    score_type (string): name of the module (without extensions).
    dir_name (string): name of the directory where to look.

    return (module): the module if found, None if not found.

    """
    try:
        file_, file_name, description = imp.find_module(score_type, dir_name)
    except ImportError:
        return None

    try:
        module = imp.load_module(score_type,
                                 file_, file_name, description)
    except ImportError as error:
        logger.warning("Unable to use task type %s from plugin in "
                       "directory %s.\n %r" % (score_type, dir_name, error))
        return None
    else:
        return module
    finally:
        file_.close()


def get_score_type(submission=None, task=None):
    """Given a task, istantiate the corresponding ScoreType class.

    submission (Submission): the submission that needs the task type.
    task (Task): the task we want to score.

    return (object): an instance of the correct ScoreType class.

    """
    # Validate arguments.
    if [x is not None
        for x in [submission, task]].count(True) != 1:
        raise ValueError("Need at most one way to get the score type.")

    if submission is not None:
        task = submission.task

    score_type_name = task.score_type
    # TODO - Manage exceptions when parameters cannot be decoded.
    score_type_parameters = json.loads(task.score_parameters)
    public_testcases = [testcase.public
                        for testcase in task.testcases]

    module = None

    # Try first if score_type_name is provided by CMS by default.
    try:
        module = __import__("cms.grading.scoretypes.%s" % score_type_name,
                            fromlist=score_type_name)
    except ImportError:
        pass

    # If not found, try in all possible plugin directories.
    if module is None:
        module = _try_import(score_type_name,
                             os.path.join(config.data_dir,
                                          "plugins", "scoretypes"))

    if module is None:
        raise KeyError("Module %s not found." % score_type_name)

    if score_type_name not in module.__dict__:
        logger.warning("Unable to find class %s in the plugin." %
                       score_type_name)
        raise KeyError("Class %s not found." % score_type_name)

    return module.__dict__[score_type_name](
        score_type_parameters,
        public_testcases)
