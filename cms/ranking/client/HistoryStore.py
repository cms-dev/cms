# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2011 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

from pyjamas.HTTPRequest import HTTPRequest
from pyjamas.JSONParser import JSONParser

from pyjamas import Window
from pyjamas import DOM


# Config
history_url = '/history'


class HistoryCallback:
    def __init__(self, store, callback):
        self.store = store
        self.callback = callback

    def onCompletion(self, response):
        self.store.perform_update(JSONParser().decode(response), self.callback)

    def onError(self, response, code):
        Window.alert("Error " + code + '\n' + response)


class HistoryStore:
    def __init__(self, datastore):
        self.history_t = []  # per task
        self.history_c = []  # per contest
        self.history_g = []  # global
        self.ds = datastore

    def request_update(self, callback):
        HTTPRequest().asyncGet(history_url, HistoryCallback(self, callback))

    def perform_update(self, data, callback):
        d = dict()
        for i in self.ds.users.iterkeys():
            d[i] = dict()
            for j in self.ds.tasks.iterkeys():
                d[i][j] = 0.0

        self.history_t = []
        self.history_c = []
        self.history_g = []

        for user, task, time, score in data:
            if user in d and task in d[user]:
                d[user][task] = score

                self.history_t.append((user, task, time, round(score, 2)))

                contest_id = self.ds.tasks[task]['contest']
                tmp_score = 0.0
                for x in d[user].iterkeys():
                    if self.ds.tasks[x]['contest'] is contest_id:
                        tmp_score += d[user][x]
                self.history_c.append((user, contest_id, time, round(tmp_score, 2)))

                tmp_score = 0.0
                for x in d[user].iterkeys():
                    tmp_score += d[user][x]
                self.history_g.append((user, time, round(tmp_score, 2)))

        callback()

    def get_score_history_for_task(self, user_id, task_id):
        result = []

        for user, task, time, score in self.history_t:
            if user is user_id and task is task_id:
                result.append((time, score, 0))

        return result

    def get_score_history_for_contest(self, user_id, contest_id):
        result = []

        for user, contest, time, score in self.history_c:
            if user is user_id and contest is contest_id:
                result.append((time, score, 0))

        return result

    def get_score_history(self, user_id):
        result = []

        for user, time, score in self.history_g:
            if user is user_id:
                result.append((time, score, 0))

        return result

    def get_rank_history_for_task(self, user_id, task_id):
        d = dict()
        for i in self.ds.users.iterkeys():
            d[i] = 0.0
        above = 0
        equal = len(self.ds.users)

        result = []

        for user, task, time, score in self.history_t:
            # TODO consider together changes with the same time
            if task is task_id:
                if user is user_id:
                    d[user_id] = score
                    new_above = 0
                    new_equal = 0
                    for s in d.itervalues():
                        if s > score:
                            new_above += 1
                        elif s == score:
                            new_equal += 1
                    if new_above is not above or new_equal is not equal:
                        above = new_above
                        equal = new_equal
                        result.append((time, above+1, equal-1))
                else:
                    changed = False
                    if d[user] <= d[user_id] and score > d[user_id]:
                        above += 1
                        changed = True
                    elif d[user] > d[user_id] and score <= d[user_id]:
                        above -= 1
                        changed = True
                    if d[user] == d[user_id]:
                        equal -= 1
                        changed = True
                    elif score == d[user_id]:
                        equal += 1
                        changed = True
                    if changed:
                        result.append((time, above+1, equal-1))
                    d[user] = score

        return result

    def get_rank_history_for_contest(self, user_id, contest_id):
        d = dict()
        for i in self.ds.users.iterkeys():
            d[i] = 0.0
        above = 0
        equal = len(self.ds.users)

        result = []

        for user, contest, time, score in self.history_c:
            # TODO consider together changes with the same time
            if contest is contest_id:
                if user is user_id:
                    d[user_id] = score
                    new_above = 0
                    new_equal = 0
                    for s in d.itervalues():
                        if s > score:
                            new_above += 1
                        elif s == score:
                            new_equal += 1
                    if new_above is not above or new_equal is not equal:
                        above = new_above
                        equal = new_equal
                        result.append((time, above+1, equal-1))
                else:
                    changed = False
                    if d[user] <= d[user_id] and score > d[user_id]:
                        above += 1
                        changed = True
                    elif d[user] > d[user_id] and score <= d[user_id]:
                        above -= 1
                        changed = True
                    if d[user] == d[user_id]:
                        equal -= 1
                        changed = True
                    elif score == d[user_id]:
                        equal += 1
                        changed = True
                    if changed:
                        result.append((time, above+1, equal-1))
                    d[user] = score

        return result

    def get_rank_history(self, user_id):
        d = dict()
        for i in self.ds.users.iterkeys():
            d[i] = 0.0
        above = 0
        equal = len(self.ds.users)

        result = []

        for user, time, score in self.history_g:
            # TODO consider together changes with the same time
            if user is user_id:
                d[user_id] = score
                new_above = 0
                new_equal = 0
                for s in d.itervalues():
                    if s > score:
                        new_above += 1
                    elif s == score:
                        new_equal += 1
                if new_above is not above or new_equal is not equal:
                    above = new_above
                    equal = new_equal
                    result.append((time, above+1, equal-1))
            else:
                changed = False
                if d[user] <= d[user_id] and score > d[user_id]:
                    above += 1
                    changed = True
                elif d[user] > d[user_id] and score <= d[user_id]:
                    above -= 1
                    changed = True
                if d[user] == d[user_id]:
                    equal -= 1
                    changed = True
                elif score == d[user_id]:
                    equal += 1
                    changed = True
                if changed:
                    result.append((time, above+1, equal-1))
                d[user] = score

        return result

