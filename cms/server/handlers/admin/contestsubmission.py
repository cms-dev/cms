#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2015 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
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

"""Submission-related handlers for AWS for a specific contest.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from sqlalchemy.orm import joinedload

from cms.db import Contest, Submission, Task
from .base import BaseHandler


class ContestSubmissionsHandler(BaseHandler):
    """Shows all submissions for this contest.

    """
    def get(self, contest_id):
        contest = self.safe_get_item(Contest, contest_id)
        self.contest = contest

        self.r_params = self.render_params()
        self.r_params["submissions"] = \
            self.sql_session.query(Submission).join(Task)\
                            .filter(Task.contest == contest)\
                            .options(joinedload(Submission.participation))\
                            .options(joinedload(Submission.files))\
                            .options(joinedload(Submission.token))\
                            .options(joinedload(Submission.results))\
                            .order_by(Submission.timestamp.desc()).all()
        self.render("contest_submissions.html", **self.r_params)
