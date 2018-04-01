#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2012 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
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
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa

import os
import re

from cms.grading.languagemanager import get_language

from cmstestsuite.functionaltestframework import FunctionalTestFramework


class TestFailure(Exception):
    pass


class Check(object):
    def check(self, *args, **kwargs):
        raise NotImplementedError


class CheckOverallScore(Check):
    # This check searches for a string such :
    #   Scored (100.0 / 100.0)
    # in status and checks the score.

    score_re = re.compile(r'^Scored \(([0-9.]+) / ([0-9/.]+)\)')

    def __init__(self, expected_score, expected_total):
        self.expected_score = expected_score
        self.expected_total = expected_total

    def check(self, result_info):
        g = CheckOverallScore.score_re.match(result_info['status'])
        if not g:
            raise TestFailure(
                "Expected total score, got status: %s\n"
                "Compilation output:\n%s" %
                (result_info['status'], result_info['compile_output']))

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
        if 'Scored' not in result_info['status']:
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
            "Execution killed with signal %s" % signal_number)


class CheckNonzeroReturn(CheckAbstractEvaluationFailure):
    def __init__(self):
        CheckAbstractEvaluationFailure.__init__(
            self, "nonzero return",
            "Execution failed because the return code was nonzero")


class Test(object):
    def __init__(self, name, task, filenames, languages, checks,
                 user_tests=False):
        self.framework = FunctionalTestFramework()

        self.name = name
        self.task_module = task
        self.filenames = filenames
        self.languages = languages
        self.checks = checks
        submission_format = list(
            e.strip() for e in task.task_info["submission_format"].split(","))
        self.submission_format = submission_format

        self.user_tests = user_tests

        self.submission_id = {}
        self.user_test_id = {}

    def _sources_names(self, language):
        # Source files are stored under cmstestsuite/code/.
        path = os.path.join(os.path.dirname(__file__), 'code')

        # Choose the correct file to submit.
        if language is not None:
            ext = get_language(language).source_extension
            filenames = [filename.replace(".%l", ext)
                         for filename in self.filenames]
        else:
            filenames = self.filenames

        full_paths = [os.path.join(path, filename) for filename in filenames]

        return full_paths

    def submit(self, task_id, user_id, language):
        full_paths = self._sources_names(language)
        self.submission_id[language] = self.framework.cws_submit(
            task_id, user_id,
            self.submission_format, full_paths, language)

    def wait(self, contest_id, language):
        # This means we were not able to submit, hence the error
        # should have been already noted.
        if self.submission_id.get(language) is None:
            return

        # Wait for evaluation to complete.
        result_info = self.framework.get_evaluation_result(
            contest_id, self.submission_id[language])

        # Run checks.
        for check in self.checks:
            try:
                check.check(result_info)
            except TestFailure:
                # Our caller can deal with these.
                raise

    def submit_user_test(self, task_id, user_id, language):
        full_paths = self._sources_names(language)
        self.user_test_id[language] = self.framework.cws_submit_user_test(
            task_id, user_id,
            self.submission_format, full_paths, language)

    def wait_user_test(self, contest_id, language):
        # This means we were not able to submit, hence the error
        # should have been already noted.
        if self.user_test_id.get(language) is None:
            return

        # Wait for evaluation to complete. We do not do any other check.
        self.framework.get_user_test_result(
            contest_id, self.user_test_id[language])
