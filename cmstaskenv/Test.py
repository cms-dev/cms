#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2013-2015 Luca Versari <veluca93@gmail.com>
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

import atexit
import json
import os
import sys
import logging

import cmscontrib.YamlLoader
from cms.db import Executable
from cms.db.filecacher import FileCacher
from cms.grading import format_status_text
from cms.grading.Job import EvaluationJob
from cms.grading.tasktypes import get_task_type
from cmscommon.terminal import move_cursor, add_color_to_string, \
    colors, directions


# TODO - Use a context object instead of global variables
task = None
file_cacher = None
tested_something = False

sols = []


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


class NullLogger(object):
    def __init__(self):
        def p(*args):
            pass
        self.info = p
        self.warning = p
        self.critical = print


def print_at_exit():
    print()
    print()
    for s in sols:
        print("%s: %3d" % (
            add_color_to_string("%30s" % s[0], colors.BLACK,
                                bold=True),
            s[1])
        )

logger = logging.getLogger()


def test_testcases(base_dir, solution, language, assume=None):
    global task, file_cacher

    # Use a FileCacher with a NullBackend in order to avoid to fill
    # the database with junk
    if file_cacher is None:
        file_cacher = FileCacher(null=True)

    cmscontrib.YamlLoader.logger = NullLogger()
    # Load the task
    # TODO - This implies copying a lot of data to the FileCacher,
    # which is annoying if you have to do it continuously; it would be
    # better to use a persistent cache (although local, possibly
    # filesystem-based instead of database-based) and somehow detect
    # when the task has already been loaded
    if task is None:
        loader = cmscontrib.YamlLoader.YamlLoader(
            os.path.realpath(os.path.join(base_dir, "..")),
            file_cacher)
        # Normally we should import the contest before, but YamlLoader
        # accepts get_task() even without previous get_contest() calls
        task = loader.get_task(os.path.split(os.path.realpath(base_dir))[1])

    # Prepare the EvaluationJob
    dataset = task.active_dataset
    digest = file_cacher.put_file_from_path(
        os.path.join(base_dir, solution),
        "Solution %s for task %s" % (solution, task.name))
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
        print(jobinfo[0])
        sys.stdout.flush()
        job = jobinfo[1]
        # Skip the testcase if we decide to consider everything to
        # timeout
        if stop:
            info.append("Time limit exceeded")
            points.append(0.0)
            comments.append("Timeout.")
            move_cursor(directions.UP, erase=True)
            continue

        # Evaluate testcase
        last_status = status
        tasktype.evaluate(job, file_cacher)
        status = job.plus["exit_status"]
        info.append((job.plus["execution_time"],
                    job.plus["execution_memory"]))
        points.append(float(job.outcome))
        comments.append(format_status_text(job.text))
        tcnames.append(jobinfo[0])

        # If we saw two consecutive timeouts, ask wether we want to
        # consider everything to timeout
        if ask_again and status == "timeout" and last_status == "timeout":
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
            print()
        move_cursor(directions.UP, erase=True)

    # Subtasks scoring
    try:
        subtasks = json.loads(dataset.score_type_parameters)
        subtasks[0]
    except:
        subtasks = [[100, len(info)]]

    if dataset.score_type == 'GroupMin':
        scoreFun = min
    else:
        if dataset.score_type != 'Sum':
            logger.warning("Score type %s not yet supported! Using Sum"
                           % dataset.score_type)

        def scoreFun(x):
            return sum(x)/len(x)

    pos = 0
    sts = []

    # For each subtask generate a list of testcase it owns, the score gained
    # and the highest time and memory usage.
    for i in subtasks:
        stscores = []
        stsdata = []
        worst = [0, 0]
        try:
            for _ in xrange(i[1]):
                stscores.append(points[pos])
                stsdata.append((tcnames[pos], points[pos],
                                comments[pos], info[pos]))
                if info[pos][0] > worst[0]:
                    worst[0] = info[pos][0]
                if info[pos][1] > worst[1]:
                    worst[1] = info[pos][1]
                pos += 1
            sts.append((scoreFun(stscores)*i[0], i[0], stsdata, worst))
        except:
            sts.append((0, i[0], stsdata, [0, 0]))

    # Result pretty printing
    # Strips sol/ and _EVAL from the solution's name
    solution = solution[4:-5]
    print()
    clen = max(len(c) for c in comments)
    for st, d in enumerate(sts):
        print(
            "Subtask %d:" % st,
            add_color_to_string(
                "%5.2f/%d" % (d[0], d[1]),
                colors.RED if abs(d[0]-d[1]) > 0.01 else colors.GREEN,
                bold=True
            )
        )
        for (i, p, c, w) in d[2]:
            print(
                "%s)" % i,
                add_color_to_string(
                    "%5.2lf" % p,
                    colors.RED if abs(p - 1) > 0.01 else colors.BLACK
                ),
                "--- %s [Time:" % c.ljust(clen),
                add_color_to_string(
                    "%5.3f" % w[0],
                    colors.BLUE if w[0] >= 0.95 * d[3][0] else colors.BLACK
                ),
                "Memory:",
                add_color_to_string(
                    "%5s" % mem_human(w[1]),
                    colors.BLUE if w[1] >= 0.95 * d[3][1] else colors.BLACK,
                ),
                end="]"
            )
            move_cursor(directions.RIGHT, 1000)
            move_cursor(directions.LEFT, len(solution) - 1)
            print(add_color_to_string(solution, colors.BLACK, bold=True))
    print()

    sols.append((solution, sum([st[0] for st in sts])))

    global tested_something
    if not tested_something:
        tested_something = True
        atexit.register(print_at_exit)

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
