#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2012 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2017 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2016 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2017 Luca Chiodini <luca@chiodini.org>
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

import re

from bs4 import BeautifulSoup

from cmstestsuite.web import GenericRequest, LoginRequest


class AWSLoginRequest(LoginRequest):
    def test_success(self):
        if not LoginRequest.test_success(self):
            return False
        fail_re = re.compile('Failed to log in.')
        if fail_re.search(self.res_data) is not None:
            return False
        username_re = re.compile(self.username)
        if username_re.search(self.res_data) is None:
            return False
        return True


class AWSSubmissionViewRequest(GenericRequest):
    """Load the view of a submission in AWS.

    """
    def __init__(self, browser, submission_id, base_url=None):
        GenericRequest.__init__(self, browser, base_url)
        self.submission_id = submission_id
        self.url = "%s/submission/%s" % (self.base_url, submission_id)

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
        # "html.parser" is Python's built-in parser. Alternatives that require
        # external dependencies are "lxml" and "html5lib".
        soup = BeautifulSoup(self.res_data, "html.parser")

        info = {}

        # Get submission status.
        tag = soup.find_all(id="submission_status")[0]
        info['status'] = tag.text.strip()

        # Get compilation text.
        tags = soup.find_all(id="compilation")
        if tags:
            content = tags[0]
            info['compile_output'] = "\n".join(
                [pre.text.strip() for pre in content.findAll("pre")])
        else:
            info['compile_output'] = None

        # Get evaluation results.
        evaluations = []
        tags = soup.find_all(id=re.compile(r"^eval_outcome_"))
        text_tags = soup.find_all(id=re.compile(r"^eval_text_"))
        for outcome_tag, text_tag in zip(tags, text_tags):
            # Get evaluation text also.
            evaluations.append({
                'outcome': outcome_tag.text.strip(),
                'text': text_tag.text.strip(),
            })

        info['evaluations'] = evaluations

        return info


class AWSUserTestViewRequest(GenericRequest):
    """Load the view of a user test in AWS."""
    def __init__(self, browser, user_test_id, base_url=None):
        GenericRequest.__init__(self, browser, base_url)
        self.user_test_id = user_test_id
        self.url = "%s/user_test/%s" % (self.base_url, user_test_id)

    def describe(self):
        return "check user_test %s" % self.user_test_id

    def test_success(self):
        if not GenericRequest.test_success(self):
            return False
        try:
            self.get_user_test_info()
            return True
        except:
            return False

    def get_user_test_info(self):
        # Only valid after self.execute()
        # Parse user test information out of response.
        # "html.parser" is Python's built-in parser. Alternatives that require
        # external dependencies are "lxml" and "html5lib".
        soup = BeautifulSoup(self.res_data, "html.parser")

        info = {}

        # Get user test status.
        tag = soup.findAll(id="user_test_status")[0]
        info['status'] = tag.text.strip()

        # Get compilation text.
        tags = soup.findAll(id="compilation")
        if tags:
            content = tags[0]
            info['compile_output'] = content.pre.text.strip()
        else:
            info['compile_output'] = None

        return info
