#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
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

from BeautifulSoup import BeautifulSoup

from stresstesting import GenericRequest


class AWSSubmissionViewRequest(GenericRequest):
    """Load the view of a submission in AWS.

    """
    def __init__(self, browser, submission_id, base_url=None):
        GenericRequest.__init__(self, browser, base_url)
        self.submission_id = submission_id
        self.url = "%ssubmission/%s" % (self.base_url, submission_id)

    def describe(self):
        return "check submission %d" % self.submission_id

    def test_success(self):
        if not GenericRequest.test_success(self):
            return False
        try:
            self.get_submission_status()
            return True
        except:
            return False

    def get_submission_status(self):
        # Only valid after self.execute()
        # Parse submission status out of response.
        soup = BeautifulSoup(self.res_data)
        id_tag = soup.findAll(id="submission_status")[0]
        return id_tag.text
