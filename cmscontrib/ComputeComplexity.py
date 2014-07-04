#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/.
# Copyright © 2012 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2010-2011 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2011 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2011 Matteo Boscariol <boscarim@hotmail.com>
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

"""This module tries to estimate the complexity of the submissions
related to a single task, using a simple least mean square method.

In particular, it computes the best coefficients of an expression of
the form N^i log_2^j(N) (2^N)^l, where i, k, l are small integers, to
approximate the times obtained by the solution, where N is the number
of bytes of the input file.

More precise results can be obtained using a task-specific model for
the dimensions of the testcases.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import imp
import io
import numpy
import sys

from cms import utf8_decoder
from cms.db import SessionGen, Task
from cms.db.filecacher import FileCacher


MAXP = 4
MAXL = 1
MAXE = 1


def ijk_to_idx(i, j, k):
    """Return the linear index associated to the triple i, j, k."""
    return (MAXE + 1) * ((MAXL + 1) * i + j) + k


def ijk_to_func(i, j, k):
    """Return the function associated to the triple i, j, k."""
    return lambda x: (x ** i) * (numpy.log2(x) ** j) * ((2 ** x) ** k)


class FileLengther(object):
    """A simple file-like object to count the bytes written to the
    file.

    """
    def __init__(self):
        """Initialize the file object."""
        self.bytes = 0

    def open(self, unused_name, unused_mode):
        """Initialize the file object."""
        self.bytes = 0

    def write(self, string):
        """Add string to the content of the file."""
        self.bytes += len(string)

    def tell(self):
        """Return the current position in the file."""
        return self.bytes

    def close(self):
        """Close the file object."""
        self.bytes = 0


def file_length(digest, file_cacher=None, file_lengther=None):
    """Compute the length of the file identified by digest.

    digest (string): the digest of the file.
    file_cacher (FileCacher): the cacher to use, or None.
    file_lengther (type): a File-like object that tell the dimension
        of the input (see example above for how to write one).

    return (int): the length of the tile.

    """
    if file_cacher is None:
        file_cacher = FileCacher()
    if file_lengther is None:
        file_lengther = FileLengther
    lengther = file_lengther()
    file_cacher.get_file_to_fobj(digest, lengther)
    return lengther.tell()


def complexity_to_string(complexity):
    """Given a tuple, return a string representing the complexity.

    complexity ([int]): a tuple of exponents.

    return (string): the complexity as a string.

    """
    string = ""
    if complexity == (0, 0, 0):
        string = "1"
    else:
        if complexity[0] > 0:
            string += " x^%d" % complexity[0]
        if complexity[1] > 0:
            string += " log^%d(x)" % complexity[1]
        if complexity[2] > 0:
            string += " (2^x)^%d" % complexity[2]
    return string


def extract_meaningful_points(testcases_lengths, submission):
    """Extract the meaningful points (consider the most expensive of
    the ones with common dimension, and throw away the ones without a
    time).

    testcases_lengths ([float]): the dimensions of the testcases.
    submission (Submission): the submission to grade.

    return (([float], [float])): x and y coordinates of the points.

    """
    points_x = []
    points_y = []
    last_length = -1
    for idx, length in enumerate(testcases_lengths):
        evaluation = submission.evaluations[idx]
        if float(evaluation.outcome) == 1.0 and \
                evaluation.execution_time is not None:
            if length == last_length:
                points_y[-1] = max(points_y[-1], evaluation.execution_time)
            else:
                points_x.append(length)
                points_y.append(evaluation.execution_time)
                last_length = length
    return points_x, points_y


def extract_complexity_submission(testcases_lengths, submission):
    """Extract the complexity of a submission, writing two files in
    the cwd, sub_<id>.dat and sub_<id>.info. In the first, there are
    three columns, X, Y, YP, where X is the dimension of the testcase,
    Y is the time used by the submission and YP is the time predicted
    by the complexity model; in the seconds, there are the
    coefficients and the residues computed for all possible
    complexities. The first can be plotted using gnuplot:

    plot "sub_<id>.dat" using 1:2, "sub_<id>.dat" using 1:3;

    testcases_lengths ([float]): the dimensions of the testcases.
    submission (Submission): the submission to grade.

    return ([float, (int), float]): score, tuple representing the
                                    complexity, confidence.

    """
    result = [None, None, None]

    points_x, points_y = extract_meaningful_points(testcases_lengths,
                                                   submission)
    print(submission.user.username, len(points_x))
    if len(points_x) <= 6:
        return result

    # Rescaling.
    x_scale = max(points_x)
    points_x = [x * 1.0 / x_scale for x in points_x]
    y_scale = max(points_y)
    if y_scale > 0:
        points_y = [y * 1.0 / y_scale for y in points_y]

    res = []
    residues = []
    best_residue = -1
    best_idxs = (-1, -1, -1)
    sbest_residue = -1

    for i in xrange(MAXP + 1):
        for j in xrange(MAXL + 1):
            for k in xrange(MAXE + 1):
                matrix = []
                for point_x in points_x:
                    matrix.append([ijk_to_func(i, j, k)(point_x)])
                points_y = numpy.array(points_y)
                matrix = numpy.vstack(matrix)
                res.append(numpy.linalg.lstsq(matrix, points_y)[0][0])

                residues.append(0.0)
                for idx, point_y in enumerate(points_y):
                    residues[-1] += (matrix[idx][0] * res[-1] - point_y) ** 2
                if best_residue == -1 or best_residue > residues[-1]:
                    sbest_residue = best_residue
                    best_residue = residues[-1]
                    best_idxs = (i, j, k)
                elif sbest_residue == -1 or sbest_residue > residues[-1]:
                    sbest_residue = residues[-1]

    result[0] = submission.score
    result[1] = best_idxs

    with io.open("sub_%s.info" % submission.id,
                 "wt", encoding="utf-8") as info:
        for i in xrange(MAXP + 1):
            for j in xrange(MAXL + 1):
                for k in xrange(MAXE + 1):
                    info.write(
                        "%+20.13lf x^%d log^%d(x) (2^x)^%d  -->  %+20.13lf\n" %
                        (res[ijk_to_idx(i, j, k)], i, j, k,
                         residues[ijk_to_idx(i, j, k)]))
        info.write("Complexity: %s\n" % complexity_to_string(best_idxs))
        if sbest_residue != 0.0:
            confidence = (100.0 * (1.0 - best_residue / sbest_residue))
            info.write("Confidence: %5.2lf (%20.13lf, %20.13lf)\n" % (
                confidence, best_residue, sbest_residue))
            result[2] = confidence
        if submission.score is not None:
            info.write("Score: %3d\n" % submission.score)

    computed_y = []
    for point_x in points_x:
        i, j, k = best_idxs
        computed_y.append(ijk_to_func(i, j, k)(point_x) *
                          res[ijk_to_idx(i, j, k)])

    with io.open("sub_%s.dat" % submission.id, "wt", encoding="utf-8") as dat:
        for point_x, point_y, computed_y in zip(points_x, points_y,
                                                computed_y):
            dat.write("%15.8lf %+15.8lf %+15.8lf\n" % (point_x * x_scale,
                                                       point_y * y_scale,
                                                       computed_y * y_scale))
    print(submission.user.username, result)
    return result


def extract_complexity(task_id, file_lengther=None):
    """Extract the complexity of all submissions of the task. The
    results are stored in a file task_<id>.info

    task_id (int): the id of the task we are interested in.
    file_lengther (type): a File-like object that tell the dimension
        of the input (see example above for how to write one).

    return (int): 0 if operation was successful.

    """
    with SessionGen() as session:
        task = Task.get_from_id(task_id, session)
        if task is None:
            return -1

        # Extracting the length of the testcase.
        file_cacher = FileCacher()
        testcases_lengths = [file_length(testcase.input,
                                         file_cacher, file_lengther)
                             for testcase in task.testcases]
        file_cacher.purge_cache()

        # Compute the complexity of the solutions.
        with io.open("task_%s.info" % task_id, "wt", encoding="utf-8") as info:
            for submission in task.contest.get_submissions():
                if submission.task_id == task_id and \
                        submission.evaluated():
                    print(submission.user.username)
                    result = extract_complexity_submission(testcases_lengths,
                                                           submission)
                    if result[1] is None:
                        continue
                    info.write("Submission: %s" % submission.id)
                    info.write(" - user: %15s" % submission.user.username)
                    info.write(" - task: %s" % task.name)
                    if result[0] is not None:
                        info.write(" - score: %6.2lf" % result[0])
                    info.write(" - complexity: %20s" %
                               complexity_to_string(result[1]))
                    if result[2] is not None:
                        info.write(" - confidence %5.1lf" % result[2])
                    info.write("\n")

    return 0


def main():
    """Parse arguments and launch process.

    """
    parser = argparse.ArgumentParser(
        description="Extract the complexity of submissions of a task.")
    parser.add_argument("task_id", action="store", type=int,
                        help="id of the task in the DB")
    parser.add_argument("-l", "--lengther", action="store", type=utf8_decoder,
                        help="filename of a Python source "
                        "with a FileLengther class")
    args = parser.parse_args()

    file_lengther = None
    if args.lengther is not None:
        if args.lengther.endswith(".py"):
            args.lengther = args.lengther[:-3]
        try:
            file_, file_name, description = imp.find_module(args.lengther)
            module = imp.load_module(args.lengther,
                                     file_, file_name, description)
            file_lengther = module.FileLengther
        except ImportError as error:
            print("Unable to import module %s.\n%r" % (args.lengther, error))
            return -1
        except AttributeError:
            print("Module %s must have a class named FileLengther." %
                  args.lengther)

    return extract_complexity(args.task_id, file_lengther=file_lengther)


if __name__ == "__main__":
    sys.exit(main())
