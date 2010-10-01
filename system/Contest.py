#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright (C) 2010 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright (C) 2010 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright (C) 2010 Matteo Boscariol <boscarim@hotmail.com>
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

class Contest(CouchObject):
    _to_copy = ["name", "description",
                "token_initial", "token_max", "token_total",
                "token_min_interval", "token_gen_time",
                "start", "stop"]
    _to_copy_id_array = ["tasks", "users", "submissions"]

    def __init__(self, name, description,
                 tasks, users,
                 token_initial, token_max, token_total,
                 token_min_interval, token_gen_time,
                 start = None, stop = None,
                 submissions = [],
                 couch_id = None):
        self.name = name
        self.description = description
        self.tasks = tasks
        self.users = users
        self.token_initial = token_initial
        self.token_max = token_max
        self.token_total = token_total
        self.token_min_interval = token_min_interval
        self.token_gen_time = token_gen_time
        self.start = start
        self.stop = stop
        self.submissions = submissions
        CouchObject.__init__(self, "contest", couch_id)

    def choose_couch_id_basename(self):
        return "contest-%s" % (self.name)

def sample_contest(couch_id = None):
    import User
    import Task
    import Submission
    c = Contest("hello", "Hello world",
                [Task.sample_task() for i in range(3)],
                [User.sample_user() for i in range(10)],
                10, 3, 3, 30, 60,
                couch_id = couch_id)
    s = Submission.sample_submission(couch_id = 'sample_submission')
    c.submissions.append(s)
    c.to_couch()
    s.task = c.tasks[0]
    s.user = c.users[0]
    s.to_couch()
    u = c.users[0]
    u.username = "username"
    u.to_couch()
    return c

if __name__ == "__main__":
    c = sample_contest(couch_id = 'sample_contest')
    print "Couch ID: %s" % (c.couch_id)
