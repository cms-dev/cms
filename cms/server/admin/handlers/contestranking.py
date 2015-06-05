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

"""Ranking-related handlers for AWS for a specific contest.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from sqlalchemy.orm import joinedload

from cms.db import Contest

from .base import BaseHandler


class RankingHandler(BaseHandler):
    """Shows the ranking for a contest.

    """
    def get(self, contest_id, format="online"):
        # This validates the contest id.
        self.safe_get_item(Contest, contest_id)

        # This massive joined load gets all the information which we will need
        # to generating the rankings.
        self.contest = self.sql_session.query(Contest)\
            .filter(Contest.id == contest_id)\
            .options(joinedload('participations'))\
            .options(joinedload('participations.submissions'))\
            .options(joinedload('participations.submissions.token'))\
            .options(joinedload('participations.submissions.results'))\
            .first()

        self.r_params = self.render_params()
        if format == "txt":
            self.set_header("Content-Type", "text/plain")
            self.set_header("Content-Disposition",
                            "attachment; filename=\"ranking.txt\"")
            self.render("ranking.txt", **self.r_params)
        elif format == "csv":
            self.set_header("Content-Type", "text/csv")
            self.set_header("Content-Disposition",
                            "attachment; filename=\"ranking.csv\"")
            self.render("ranking.csv", **self.r_params)
        else:
            self.render("ranking.html", **self.r_params)
