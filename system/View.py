#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
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

import Utils
from CouchObject import CouchObject

class RankingView(CouchObject):
    _to_copy = ["timestamp", "scores"]
    _to_copy_id = ["contest"]

    def __init__(self, contest = None,
                 timestamp = 0.0, scores = {},
                 couch_id = None, couch_rev = None):
        self.contest = contest
        self.timestamp = timestamp
        self.scores = scores
        CouchObject.__init__(self, "rankingview", couch_id, couch_rev)

    def choose_couch_id_basename(self):
        return "rankingview-%s" % (self.contest.name)

