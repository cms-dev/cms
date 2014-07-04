#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2012 Bernard Blackham <bernard@largestprime.net>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import re

from BeautifulSoup import BeautifulSoup

from cmstestsuite.web import GenericRequest


class AWSSubmissionViewRequest(GenericRequest):
    """Load the view of a submission in AWS.

    """
    def __init__(self, browser, submission_id, base_url=None):
        GenericRequest.__init__(self, browser, base_url)
        self.submission_id = submission_id
        self.url = "%ssubmission/%s" % (self.base_url, submission_id)

    def describe(self):
        return "check submission %s" % self.submission_id

    def test_success(self):
        if not GenericRequest.test_success(self):
            return False
        try:
            self.get_submission_info()
            return True
        except:
            return False

    def get_submission_info(self):
        # Only valid after self.execute()
        # Parse submission information out of response.

        soup = BeautifulSoup(self.res_data)

        info = {}

        # Get submission status.
        tag = soup.findAll(id="submission_status")[0]
        info['status'] = tag.text.strip()

        # Get compilation text.
        tags = soup.findAll(id="compilation")
        if tags:
            content = tags[0]
            info['compile_output'] = content.pre.text.strip()
        else:
            info['compile_output'] = None

        # Get evaluation results.
        evaluations = []
        tags = soup.findAll(id=re.compile(r"^eval_outcome_"))
        for outcome_tag in sorted(tags, key=lambda t: t['id']):
            codename = outcome_tag['id'][len("eval_outcome_"):]

            # Get evaluation text also.
            text_tag = soup.findAll(id="eval_text_%s" % codename)[0]

            evaluations.append({
                'outcome': outcome_tag.text.strip(),
                'text': text_tag.text.strip(),
            })

        info['evaluations'] = evaluations

        return info
