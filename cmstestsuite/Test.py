#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2012 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014-2015 Stefano Maggiolo <s.maggiolo@gmail.com>
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

import os
import re

from cmstestsuite import cws_submit, get_evaluation_result


class TestFailure(Exception):
    pass


class Check(object):
    def check(self, *args, **kwargs):
        raise NotImplementedError


class CheckOverallScore(Check):
    # This check searches for a string such :
    #   Evaluated (100.0 / 100.0)
    # in status and checks the score.

    score_re = re.compile(r'^Evaluated \(([0-9.]+) / ([0-9/.]+)\)')

    def __init__(self, expected_score, expected_total):
        self.expected_score = expected_score
        self.expected_total = expected_total

    def check(self, result_info):
        g = CheckOverallScore.score_re.match(result_info['status'])
        if not g:
            raise TestFailure("Expected total score, got status: %s" %
                              result_info['status'])

        score, total = g.groups()
        try:
            score = float(score)
            total = float(total)
        except ValueError:
            raise TestFailure("Expected readable score, got: %s/%s" %
                              (score, total))

        if score != self.expected_score or \
                total != self.expected_total:
            raise TestFailure("Expected score of %g/%g, but got %g/%g" %
                              (self.expected_score, self.expected_total,
                               score, total))


class CheckCompilationFail(Check):
    def check(self, result_info):
        if 'Compilation failed' not in result_info['status']:
            raise TestFailure("Expected compilation to fail, got: %s" %
                              result_info['status'])


class CheckAbstractEvaluationFailure(Check):
    def __init__(self, short_adjective, failure_string):
        self.short_adjective = short_adjective
        self.failure_string = failure_string

    def check(self, result_info):
        if 'Evaluated' not in result_info['status']:
            raise TestFailure("Expected a successful evaluation, got: %s" %
                              result_info['status'])
        if not result_info['evaluations']:
            raise TestFailure("No evaluations found.")
        for evaluation in result_info['evaluations']:
            score = float(evaluation['outcome'])
            text = evaluation['text']
            if score != 0.0:
                raise TestFailure("Should have %s. Scored %g." %
                                  (self.short_adjective, score))
            if self.failure_string not in text:
                raise TestFailure("Should have %s, got %s" %
                                  (self.short_adjective, text))


class CheckTimeout(CheckAbstractEvaluationFailure):
    def __init__(self):
        CheckAbstractEvaluationFailure.__init__(
            self, "timed out", "Execution timed out")


class CheckTimeoutWall(CheckAbstractEvaluationFailure):
    def __init__(self):
        CheckAbstractEvaluationFailure.__init__(
            self, "wall timed out",
            "Execution timed out (wall clock limit exceeded)")


class CheckForbiddenSyscall(CheckAbstractEvaluationFailure):
    def __init__(self, syscall_name=''):
        CheckAbstractEvaluationFailure.__init__(
            self, "executed a forbidden syscall",
            "Execution killed because of forbidden syscall %s" % syscall_name)


class CheckSignal(CheckAbstractEvaluationFailure):
    def __init__(self, signal_number):
        CheckAbstractEvaluationFailure.__init__(
            self, "died on a signal",
            "Execution killed with signal %d" % signal_number)


class CheckNonzeroReturn(CheckAbstractEvaluationFailure):
    def __init__(self):
        CheckAbstractEvaluationFailure.__init__(
            self, "nonzero return",
            "Execution failed because the return code was nonzero")


class Test(object):
    def __init__(self, name, task, filename, languages, checks):
        self.name = name
        self.task_module = task
        self.filename = filename
        self.languages = languages
        self.checks = checks

    def run(self, contest_id, task_id, user_id, language):
        # Source files are stored under cmstestsuite/code/.
        path = os.path.join(os.path.dirname(__file__), 'code')

        # Choose the correct file to submit.
        filename = self.filename.replace("%l", language)

        full_path = os.path.join(path, filename)

        # Submit our code.
        submission_id = cws_submit(contest_id, task_id, user_id,
                                   full_path, language)

        # Wait for evaluation to complete.
        result_info = get_evaluation_result(contest_id, submission_id)

        # Run checks.
        for check in self.checks:
            try:
                check.check(result_info)
            except TestFailure:
                # Our caller can deal with these.
                raise
