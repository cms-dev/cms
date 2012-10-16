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

import simplejson as json

from cms import logger, plugin_lookup
from cms.grading.Job import Job


def get_task_type(job=None, file_cacher=None, task=None,
                  task_type_name=None):
    """Given a job, istantiate the corresponding TaskType class.

    job (Job): the job to perform.
    file_cacher (FileCacher): a file cacher object.
    task (Task): if we don't want to grade, but just to get
                 information, we can provide only the
                 task and not the submission.
    task_type_name (string): again, if we only need the class, we can
                             give only the task type name.

    return (object): an instance of the correct TaskType class.

    """
    # Validate arguments.
    if [x is not None
        for x in [job, task, task_type_name]].count(True) != 1:
        raise ValueError("Need exactly one way to get the task type.")
    elif [x is not None
          for x in [job, file_cacher]].count(True) not in [0, 2]:
        raise ValueError("Need file cacher to perform a job.")

    # Recover information from the arguments.
    task_type_parameters = None
    if job is not None:
        task_type_name = job.task_type
    if task is not None:
        task_type_name = task.task_type
        try:
            task_type_parameters = json.loads(task.task_type_parameters)
        except json.decoder.JSONDecodeError as error:
            logger.error("Cannot decode task type parameters.\n%r." % error)
            raise
        job = Job()
        job.task_type = task_type_name
        job.task_type_parameters = task_type_parameters

    cls = plugin_lookup(task_type_name,
                        "cms.grading.tasktypes", "tasktypes")

    return cls(job, file_cacher)
