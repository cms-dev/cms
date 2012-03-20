#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2012 Bernard Blackham <bernard@largestprime.net>
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

import os
import re

from cmstestsuite.util import cws_submit, get_evaluation_result


class TestFailure(Exception):
    pass


class Check:
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

    def check(self, status):
        g = CheckOverallScore.score_re.match(status)
        if not g:
            raise TestFailure("Expected total score, got status: %s" % status)

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


class Test:
    def __init__(self, task, filename, languages, checks):
        self.task_module = task
        self.filename = filename
        self.languages = languages
        self.checks = checks

    def run(self, contest_id, task_id, user_id):
        # For each language, run.
        for lang in self.languages:
            self.run_lang(contest_id, task_id, user_id, lang)

    def run_lang(self, contest_id, task_id, user_id, language):
        path = os.path.join(os.path.dirname(__file__), 'code')
        # Choose the correct file to submit.
        filename = self.filename.replace("%l", language)

        full_path = os.path.join(path, filename)

        # Submit our code.
        submission_id = cws_submit(contest_id, task_id, user_id,
                                   full_path, language)

        # Wait for evaluation to complete.
        status = get_evaluation_result(contest_id, submission_id)

        # Run checks.
        for check in self.checks:
            try:
                check.check(status)
            except TestFailure:
                # TODO: Do something useful with these, like aggregating them.
                # For now, just raise it and abort.
                raise
