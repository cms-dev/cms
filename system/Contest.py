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

class Contest(CouchObject):
    _to_copy = ["name", "description",
                "token_initial", "token_max", "token_total",
                "token_min_interval", "token_gen_time",
                "start", "stop", "announcements"]
    _to_copy_id = ["ranking_view"]
    _to_copy_id_array = ["tasks", "users", "submissions"]

    def __init__(self, name, description,
                 tasks, users,
                 token_initial, token_max, token_total,
                 token_min_interval, token_gen_time,
                 start = None, stop = None, announcements = [],
                 submissions = [], ranking_view = None,
                 couch_id = None, couch_rev = None, ):
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
        self.announcements = announcements
        self.submissions = submissions
        self.ranking_view = ranking_view
        CouchObject.__init__(self, "contest", couch_id, couch_rev)

    def choose_couch_id_basename(self):
        return "contest-%s" % (self.name)

    def update_ranking_view(self):
        self.ranking_view.scores = {}
        for user in self.users:
            self.ranking_view.scores[user.username] = []
            for task in self.tasks:
                score = task.scorer.scores.get(user.username, 0.0)
                self.ranking_view.scores[user.username].append(score)
        # This to_couch() call should never fail, because only
        # Evaluation Server modifies the ranking view
        self.ranking_view.to_couch()

    def get_task(self, task_name):
        """
        Returns the first task in the contest with the given name.
        """
        for t in self.tasks:
            if t.name == task_name:
                return t
        raise KeyError("Task not found")

    def get_task_index(self, task_name):
        """
        Returns the index of the first task in the contest with the
        given name.
        """
        for i, t in enumerate(self.tasks):
            if t.name == task_name:
                return i
        raise KeyError("Task not found")


def sample_contest(couch_id = None):
    import User
    import Task
    import Submission
    c = Contest("hello", "Hello world",
                [Task.sample_task() for i in range(3)],
                [User.sample_user() for i in range(10)],
                10, 3, 3, 30, 60,
                couch_id = couch_id)
    s = Submission.sample_submission()
    c.submissions.append(s)
    # These to_couch() calls should never fail, because they act on
    # freshly created document
    c.to_couch()
    s.task = c.tasks[0]
    s.user = c.users[0]
    s.to_couch()
    u = c.users[0]
    u.username = "username"
    u.to_couch()
    return c

if __name__ == "__main__":
    c = sample_contest()
    print "Couch ID: %s" % (c.couch_id)
