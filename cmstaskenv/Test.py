#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2013 Luca Versari <veluca93@gmail.com>
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

import sys
import os

from cmscontrib.YamlLoader import YamlLoader
from cms.db.FileCacher import FileCacher
from cms.grading.Job import EvaluationJob, Testcase
from cms.db.SQLAlchemyAll import Executable
from cms.grading.tasktypes import get_task_type
import simplejson as json

task = None
file_cacher = None


def usage():
    print """%s base_dir executable [assume]"
base_dir:   directory of the task
executable: solution to test (relative to the task's directory)
assume:     if it's y, answer yes to every question
            if it's n, answer no to every question
""" % sys.argv[0]


def mem_human(mem):
    if mem > 2**30:
        return "%4.3gG" % (float(mem)/(2**30))
    if mem > 2**20:
        return "%4.3gM" % (float(mem)/(2**20))
    if mem > 2**10:
        return "%4dK" % (mem/(2**10))
    return "%4d" % mem


def test_testcases(base_dir, soluzione, assume=None):
    global task, file_cacher

    if file_cacher is None:
        file_cacher = FileCacher()

    if task is None:
        loader = YamlLoader(
            os.path.realpath(os.path.join(base_dir, "..")),
            file_cacher)
        taskdata = {}
        taskdata["name"] = os.path.split(os.path.realpath(base_dir))[1]
        taskdata["num"] = 1
        task = loader.get_task(taskdata)

    dataset = task.active_dataset
    digest = file_cacher.put_file(
        path=os.path.join(base_dir, soluzione),
        description="Solution %s for task %s" % (soluzione, task.name))
    executables = {task.name: Executable(filename=task.name, digest=digest)}
    job = EvaluationJob(
        task_type=dataset.task_type,
        task_type_parameters=json.loads(dataset.task_type_parameters),
        managers=dict(dataset.managers),
        executables=executables,
        testcases=dict((t.num, Testcase(t.input, t.output))
                       for t in dataset.testcases),
        time_limit=dataset.time_limit,
        memory_limit=dataset.memory_limit)
    tasktype = get_task_type(job, file_cacher)
    ask_again = True
    last_status = "ok"
    status = "ok"
    stop = False

    info = []
    points = []
    comments = []
    for i in job.testcases.keys():
        print i,
        sys.stdout.flush()
        if stop:
            info.append("Time limit exceeded")
            points.append(0.0)
            comments.append("Timeout.")
            continue
        last_status = status
        tasktype.evaluate_testcase(i)
        # print job.evaluations[i]
        status = job.evaluations[i]["plus"]["exit_status"]
        info.append("Time: %5.3f   Wall: %5.3f   Memory: %s" %
                    (job.evaluations[i]["plus"]["execution_time"],
                    job.evaluations[i]["plus"]["execution_wall_clock_time"],
                    mem_human(job.evaluations[i]["plus"]["memory_used"])))
        points.append(float(job.evaluations[i]["outcome"]))
        comments.append(job.evaluations[i]["text"])
        if ask_again and status == "timeout" and last_status == "timeout":
            print
            print "Want to stop and consider everything to timeout? [y/N]",
            if assume is not None:
                print assume
                tmp = assume
            else:
                tmp = raw_input().lower()
            if tmp in ['y', 'yes']:
                stop = True
            else:
                ask_again = False
    print
    clen = max(len(c) for c in comments)
    ilen = max(len(i) for i in info)
    for i, (p, c, b) in enumerate(zip(points, comments, info)):
        print "%3d) %5.2lf --- %s [%s]" % (i, p, c.ljust(clen), b.center(ilen))

    # Delete the executable we stored before
    file_cacher.delete(digest)

    return zip(points, comments, info)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        usage()
    if len(sys.argv) == 3:
        assume = None
    else:
        assume = sys.argv[3]
    test_testcases(sys.argv[1], sys.argv[2], assume)
