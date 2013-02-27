#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
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

from shutil import rmtree, copy
import tempfile
import sys
import subprocess
import os

from os.path import join
from glob import glob


def log(m, exitval=None):
    if exitval == None:
        print >> sys.stderr, m
    else:
        print >> sys.stderr, "ERRORE: " + m
        sys.exit(exitval)


def usage():
    log("%s mo-box soluzione timeout memlimit Batch|Communication Empty|Diff|Comp|Grad|GradComp [correttore] [manager]" % \
            os.path.basename(sys.argv[0]), exitval=1)


def get_box_status(sandbox):
    _file = open("%s/run.log" % sandbox).readlines()
    for f in _file:
        if f.split(":")[0] == "status":
            return f.split(":")[1].strip()
    return "OK"


def get_points(file_):
    content = open(file_).read().strip()
    try:
        return float(content)
    except ValueError:
        print "WARNING: Unable to extract points from the string `%s'." \
              "Using 0.0." % content
        return 0


def analyze_status(status):
    if status == "XX":
        log("Sandbox error.", exitval=1)
    elif status == "OK":
        log("Please analyze OK status as you wish.", exitval=1)
    elif status == "FO":
        return 0.0, "Forbidden syscall."
    elif status == "FA":
        return 0.0, "Forbidden file access."
    elif status == "TO":
        return 0.0, "Timeout."
    elif status == "SG":
        return 0.0, "Some signal."
    elif status == "RE":
        return 0.0, "Exited with error status"
    else:
        log("Unrecognized sandbox status %s." % status, exitval=1)


def diff(a, b):
    try:
        devnull = open("/dev/null", "w")
        subprocess.check_call(["diff", a, b, "-q", "-B", "-b"], stdout=devnull)
        devnull.close()
    except Exception:
        return "0.0", "Not correct."
    return "1.0", "Correct."


def test_testcases(base_dir, numinput, driver, soluzione, timeout, memlimit, tt1, tt2, cormgr=""):
    points = []
    comments = []
    box_outs = []
    statuses = []

    status = "OK"
    prev_status = "OK"
    stop = False
    ask_again = True
    if not os.path.exists(os.path.join(base_dir, "result")):
        os.mkdir(os.path.join(base_dir, "result"))
    for i in xrange(numinput):
        print i,
        if stop:
            box_outs.append("Time limit exceeded")
            points.append(0.0)
            comments.append("Timeout.")
            statuses.append("TO")
            continue
        prev_status = status
        sys.stdout.flush()
        sandbox = tempfile.mkdtemp()
        copy(os.path.join(base_dir, soluzione), sandbox)
        if tt1 == "Communication":
            mgr_sandbox = tempfile.mkdtemp()
            copy(os.path.join(base_dir, cormgr), mgr_sandbox)
            copy(os.path.join(base_dir, "input/input%s.txt" % i), "%s/input.txt" % mgr_sandbox)
            os.mkfifo("%s/in" % sandbox)
            os.mkfifo("%s/out" % sandbox)
            mgr_command = "%s -c %s " \
                          "-i input.txt -o output.txt -r comment.txt " \
                          "-t %lg -w %lg -M run.log -- ./%s %s/in %s/out" % (
                driver, mgr_sandbox, timeout, timeout * 3, os.path.basename(cormgr), sandbox, sandbox)
            devnull = open("/dev/null")
            mgr = subprocess.Popen(mgr_command.split(), stderr=devnull)
            command = "%s -a 1 -c %s -ff -m %d " \
                      "-p in -p out -p /proc/self/exe -p /proc/meminfo " \
                      "-s getrlimit -s rt_sigaction -s ugetrlimit " \
                      "-t %lg -w %lg -M %s/run.log -- ./%s out in" % (
                driver, sandbox, memlimit * 1024, timeout, timeout * 3, sandbox, os.path.basename(soluzione))
            box_out = open("%s/box_out.txt" % sandbox, "w")
            sol = subprocess.Popen(command.split(), stderr=box_out)
            sol.wait()

            mgr.wait()
            devnull.close()
            box_out.close()
            try:
                copy("%s/output.txt" % mgr_sandbox, os.path.join("result/result%d.txt" % i))
            except IOError:  # output doesn't exist
                open("result/result%d.txt" % i, "wt").close()
            status = get_box_status(sandbox)
            statuses.append(status)
            box_outs.append(open("%s/box_out.txt" % sandbox, "r").read().strip())
            if status == "OK":
                points.append(get_points("%s/output.txt" % mgr_sandbox))
                comments.append(open("%s/comment.txt" % mgr_sandbox).read().strip())
            else:
                tmp_p, tmp_c = analyze_status(status)
                points.append(tmp_p)
                comments.append(tmp_c)
            rmtree(mgr_sandbox)

        elif tt1 == "Batch":
            copy(os.path.join(base_dir, "input/input%s.txt" % i), "%s/input.txt" % sandbox)
            command = "%s -a 1 -c %s -ff -m %d -o %s/output.txt " \
                      "-i %s/input.txt " \
                      "-p input.txt -p output.txt " \
                      "-p /proc/self/exe -p /proc/meminfo " \
                      "-s getrlimit -s rt_sigaction -s rt_sigprocmask -s ugetrlimit " \
                      "-t %lg -w %lg -M %s/run.log -- ./%s" % (
                driver, sandbox, memlimit * 1024, sandbox, sandbox, timeout, timeout * 1.5, sandbox, os.path.basename(soluzione))
            box_out = open("%s/box_out.txt" % sandbox, "w")
            subprocess.Popen(command.split(), stderr=box_out).wait()
            box_out.close()
            copy(os.path.join(base_dir, soluzione), sandbox)
            copy("%s/output.txt" % sandbox, os.path.join(base_dir, "result/result%d.txt" % i))

            status = get_box_status(sandbox)
            statuses.append(status)
            box_outs.append(open("%s/box_out.txt" % sandbox, "r").read().strip())
            if status != "OK":
                tmp_p, tmp_c = analyze_status(status)
                points.append(tmp_p)
                comments.append(tmp_c)
            else:
                if tt2 == "Diff" or tt2 == "Grad":
                    tmp = diff("%s/output.txt" % sandbox, "output/output%s.txt" % i)

                    points.append(float(tmp[0].strip()))
                    comments.append(tmp[1].strip())

                elif tt2 == "Comp" or tt2 == "GradComp":
                    copy(os.path.join(base_dir, cormgr), sandbox)
                    copy(os.path.join(base_dir, "output/output%s.txt" % i), "%s/correct.txt" % sandbox)
                    command = "%s -c %s -o corout.txt -r comment.txt " \
                              "-M %s/run.log -- ./%s input.txt correct.txt output.txt" % (
                        driver, sandbox, sandbox, os.path.basename(cormgr))
                    box_out = open("%s/box_out.txt" % sandbox, "w")
                    subprocess.Popen(command.split(), stderr=box_out).wait()
                    box_out.close()
                    points.append(get_points("%s/corout.txt" % sandbox))
                    comments.append(open("%s/comment.txt" % sandbox).read().strip())

        if ask_again and status == "TO" and prev_status == "TO":
            print
            print "Want to stop and consider everything to timeout? [y/N]",
            tmp = raw_input().lower()
            if tmp in ['y', 'yes']:
                stop = True
            else:
                ask_again = False
#        print sandbox
#        print command
        rmtree(sandbox)

    print
    maxlen = max(len(c) for c in comments)
    for i, (p, c, b) in enumerate(zip(points, comments, box_outs)):

        print "%3d) %5.2lf   ---   %s   [%s]" % (i, p, c.ljust(maxlen), b)
    return zip(points, comments, box_outs, statuses)


if __name__ == "__main__":
    correttore = manager = ""
    if len(sys.argv) < 7:
        usage()
    else:
        driver, soluzione, timeout, memlimit = sys.argv[1:5]
        timeout = float(timeout)
        memlimit = float(memlimit)

        tasktype = sys.argv[5:7]
        if tasktype == ["Batch", "Diff"] or tasktype == ["Batch", "Grad"]:
            if len(sys.argv) != 7:
                usage()
        elif tasktype == ["Batch", "Comp"] or tasktype == ["Batch", "GradComp"]:
            if len(sys.argv) != 8:
                usage()
            correttore = sys.argv[7]
        elif tasktype == ["Communication", "Empty"]:
            if len(sys.argv) != 8:
                usage()
            manager = sys.argv[7]
        else:
            usage()

    if os.path.exists("result"):
        rmtree("result")
    os.mkdir("result")

    numinput = len(glob(join("input", "input*.txt")))
    test_testcases(".", numinput, driver, soluzione, timeout, memlimit, tasktype[0], tasktype[1], correttore if correttore != "" else manager)
