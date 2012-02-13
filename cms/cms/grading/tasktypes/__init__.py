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

from cms import config
from cms.service.LogService import logger


def _try_import(task_type, dir_name):
    """Try to import a module called module_name from a directory
    called dir_name.

    task_type (string): name of the module (without extensions).
    dir_name (string): name of the directory where to look.

    return (module): the module if found, None if not found.

    """
    try:
        file_, file_name, description = imp.find_module(task_type, dir_name)
    except ImportError:
        return None

    try:
        module = imp.load_module(task_type,
                                 file_, file_name, description)
    except ImportError as error:
        logger.warning("Unable to use task type %s from plugin in "
                       "directory %s.\n %r" % (task_type, dir_name, error))
        return None
    else:
        return module
    finally:
        file_.close()


def get_task_type(submission=None, file_cacher=None, task=None):
    """Given a submission, istantiate the corresponding TaskType
    class.

    submission (Submission): the submission that needs the task type.
    file_cacher (FileCacher): a file cacher object.
    task (Task): if we don't want to grade, but just to get
                 information, we can provide only the
                 task and not the submission.

    return (object): an instance of the correct TaskType class.

    """
    # If we have info from submission, use those.
    if submission is not None:
        task = submission.task
    elif task is None:
        raise ValueError("Can't have both submission and task None.")

    task_type = task.task_type
    module = None

    # Try first if task_type is provided by CMS by default.
    try:
        module = __import__("cms.grading.tasktypes.%s" % task_type,
                            fromlist=task_type)
    except ImportError:
        pass

    # If not found, try in all possible plugin directories.
    if module is None:
        module = _try_import(task_type,
                             os.path.join(config.data_dir,
                                          "plugins", "tasktypes"))

    if module is None:
        raise KeyError("Module %s not found." % task_type)

    if task_type not in module.__dict__:
        logger.warning("Unable to find class %s in the plugin." % task_type)
        raise KeyError("Class %s not found." % task_type)

    return module.__dict__[task_type](
        submission,
        json.loads(task.task_type_parameters),
        file_cacher)
