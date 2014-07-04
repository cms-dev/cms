#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
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

"""A class to update a dump created by CMS.

Used by ContestImporter and DumpUpdater.

This adapts the dump to some changes in the model introduced in the
commit that created this same file and in commit
af2338b9a22df8a19671c7fee78d9dc4b35c49ea.

"""

from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

import json


def parse_compilation_text(s):
    if s is None:
        return None, None, None, None, None
    if s == "No compilation needed.":
        return "[\"No compilation needed\"]", None, None, None, None
    s = s.split('\n')
    if s[0].startswith('Killed with signal '):
        del s[1]
    status, stats = s[0].split(' [')
    time, memory = stats.rstrip(']').split(' - ')
    stdout, _, stderr = "\n".join(s[1:])[len("Compiler standard output:\n"):]\
                        .partition("\nCompiler standard error:\n")
    status = status.split(' ')
    text = [{'OK': "Compilation succeeded",
             'Failed': "Compilation failed",
             'Time': "Compilation timed out",
             'Killed': "Compilation killed with signal %d (could be triggered "
                       "by violating memory limits)"}[status[0]]]
    if status[0] == "Killed":
        text += [int(status[-1])]
    if time == "(time unknown)":
        time = None
    else:
        time = float(time.partition(' ')[0])
    if memory == "(memory usage unknown)":
        memory = None
    else:
        memory = int(float(memory.partition(' ')[0]) * 1024 * 1024)
    if stdout == "(empty)\n":
        stdout = ""
    if stderr == "(empty)\n":
        stderr = ""
    return json.dumps(text), time, memory, stdout, stderr


def parse_evaluation_text(s):
    if s is None:
        return None
    # Catch both "Evaluation" and "Execution".
    if "tion didn't produce file " in s:
        res = ["Evaluation didn't produce file %s", ' '.join(s.split(' ')[4:])]
    elif s.startswith("Execution killed with signal "):
        res = ["Execution killed with signal %d (could be triggered by "
               "violating memory limits)", int(s.rpartition(' ')[2][:-1])]
    elif s.startswith("Execution killed because of forbidden syscall "):
        res = ["Execution killed because of forbidden syscall %s",
               s.rpartition(' ')[2][:-1]]
    elif s in ["Execution failed because the return code was nonzero.",
               "Execution killed because of forbidden file access.",
               "Execution timed out."]:
        res = [s.rstrip('.')]
    else:
        res = [s]
    return json.dumps(res)


def parse_tc_details(s):
    for i in s:
        if "text" in i:
            i["text"] = parse_evaluation_text(i["text"])
    return s


def parse_st_details(s):
    for i in s:
        parse_tc_details(i["testcases"])
    return s


class Updater(object):

    def __init__(self, data):
        assert data["_version"] == 5
        self.objs = data

    def run(self):
        for k, v in self.objs.iteritems():
            if k.startswith("_"):
                continue

            # Compilation
            if v["_class"] in ("SubmissionResult", "UserTestResult"):
                # Parse compilation_text
                v["compilation_text"], v["compilation_time"], \
                    v["compilation_memory"], v["compilation_stdout"], \
                    v["compilation_stderr"] = \
                    parse_compilation_text(v["compilation_text"])
                v["compilation_wall_clock_time"] = None

            # Evaluation
            if v["_class"] == "Evaluation":
                v["text"] = parse_evaluation_text(v["text"])
                v["execution_memory"] = v["memory_used"]
                del v["memory_used"]

            if v["_class"] == "UserTestResult":
                v["evaluation_text"] = \
                    parse_evaluation_text(v["evaluation_text"])
                v["evaluation_memory"] = v["memory_used"]
                del v["memory_used"]

            # Scoring
            if v["_class"] == "SubmissionResult":
                s = v.get("score")
                sd = v.get("score_details")
                ps = v.get("public_score")
                psd = v.get("public_score_details")
                rsd = v.get("ranking_score_details")

                if self.objs[v["dataset"]]["score_type"] == "Sum":
                    if sd is not None:
                        sd = json.dumps(parse_tc_details(json.loads(sd)))
                    if psd is not None:
                        psd = json.dumps(parse_tc_details(json.loads(psd)))
                else:  # Group*
                    if sd is not None:
                        sd = json.dumps(parse_st_details(json.loads(sd)))
                    if psd is not None:
                        psd = json.dumps(parse_st_details(json.loads(psd)))

                if rsd is not None:
                    rsd = json.dumps(
                        list(i.strip() for i in rsd[1:-1].split(',')))

                v["score"] = s
                v["score_details"] = sd
                v["public_score"] = ps
                v["public_score_details"] = psd
                v["ranking_score_details"] = rsd

        return self.objs
