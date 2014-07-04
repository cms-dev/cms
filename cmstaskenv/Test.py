#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2013 Luca Versari <veluca93@gmail.com>
# Copyright © 2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
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
import os
import sys

from cmscontrib.YamlLoader import YamlLoader
from cms.db import Executable
from cms.db.filecacher import FileCacher
from cms.grading import format_status_text
from cms.grading.Job import EvaluationJob
from cms.grading.tasktypes import get_task_type


# TODO - Use a context object instead of global variables
task = None
file_cacher = None


def usage():
    print("""%s base_dir executable [assume]"
base_dir:   directory of the task
executable: solution to test (relative to the task's directory)
language:   programming language the solution is written in
assume:     if it's y, answer yes to every question
            if it's n, answer no to every question
""" % sys.argv[0])


def mem_human(mem):
    if mem is None:
        return 'None'
    if mem > 2 ** 30:
        return "%4.3gG" % (float(mem) / (2 ** 30))
    if mem > 2 ** 20:
        return "%4.3gM" % (float(mem) / (2 ** 20))
    if mem > 2 ** 10:
        return "%4dK" % (mem / (2 ** 10))
    return "%4d" % mem


def test_testcases(base_dir, soluzione, language, assume=None):
    global task, file_cacher

    # Use a FileCacher with a NullBackend in order to avoid to fill
    # the database with junk
    if file_cacher is None:
        file_cacher = FileCacher(null=True)

    # Load the task
    # TODO - This implies copying a lot of data to the FileCacher,
    # which is annoying if you have to do it continuously; it would be
    # better to use a persistent cache (although local, possibly
    # filesystem-based instead of database-based) and somehow detect
    # when the task has already been loaded
    if task is None:
        loader = YamlLoader(
            os.path.realpath(os.path.join(base_dir, "..")),
            file_cacher)
        # Normally we should import the contest before, but YamlLoader
        # accepts get_task() even without previous get_contest() calls
        task = loader.get_task(os.path.split(os.path.realpath(base_dir))[1])

    # Prepare the EvaluationJob
    dataset = task.active_dataset
    digest = file_cacher.put_file_from_path(
        os.path.join(base_dir, soluzione),
        "Solution %s for task %s" % (soluzione, task.name))
    executables = {task.name: Executable(filename=task.name, digest=digest)}
    jobs = [(t, EvaluationJob(
        language=language,
        task_type=dataset.task_type,
        task_type_parameters=json.loads(dataset.task_type_parameters),
        managers=dict(dataset.managers),
        executables=executables,
        input=dataset.testcases[t].input, output=dataset.testcases[t].output,
        time_limit=dataset.time_limit,
        memory_limit=dataset.memory_limit)) for t in dataset.testcases]
    tasktype = get_task_type(dataset=dataset)

    ask_again = True
    last_status = "ok"
    status = "ok"
    stop = False
    info = []
    points = []
    comments = []
    tcnames = []
    for jobinfo in sorted(jobs):
        print(jobinfo[0], end='')
        sys.stdout.flush()
        job = jobinfo[1]
        # Skip the testcase if we decide to consider everything to
        # timeout
        if stop:
            info.append("Time limit exceeded")
            points.append(0.0)
            comments.append("Timeout.")
            continue

        # Evaluate testcase
        last_status = status
        tasktype.evaluate(job, file_cacher)
        status = job.plus["exit_status"]
        info.append("Time: %5.3f   Wall: %5.3f   Memory: %s" %
                   (job.plus["execution_time"],
                    job.plus["execution_wall_clock_time"],
                    mem_human(job.plus["execution_memory"])))
        points.append(float(job.outcome))
        comments.append(format_status_text(job.text))
        tcnames.append(jobinfo[0])

        # If we saw two consecutive timeouts, ask wether we want to
        # consider everything to timeout
        if ask_again and status == "timeout" and last_status == "timeout":
            print()
            print("Want to stop and consider everything to timeout? [y/N]",
                  end='')
            if assume is not None:
                print(assume)
                tmp = assume
            else:
                tmp = raw_input().lower()
            if tmp in ['y', 'yes']:
                stop = True
            else:
                ask_again = False

    # Result pretty printing
    print()
    clen = max(len(c) for c in comments)
    ilen = max(len(i) for i in info)
    for (i, p, c, b) in zip(tcnames, points, comments, info):
        print("%s) %5.2lf --- %s [%s]" % (i, p, c.ljust(clen), b.center(ilen)))

    return zip(points, comments, info)


def clean_test_env():
    """Clean the testing environment, mostly to reclaim disk space.

    """
    # We're done: since we have no way to reuse this cache, we destroy
    # it to free space. See the TODO above.
    global file_cacher, task
    if file_cacher is not None:
        file_cacher.destroy_cache()
        file_cacher = None
        task = None

if __name__ == "__main__":
    if len(sys.argv) < 4:
        usage()
    if len(sys.argv) == 4:
        assume = None
    else:
        assume = sys.argv[4]
    test_testcases(sys.argv[1], sys.argv[2], sys.argv[3], assume=assume)
