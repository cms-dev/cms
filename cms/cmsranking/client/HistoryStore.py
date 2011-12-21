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

from __pyjamas__ import JS


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
        JS('''
        // List of score-change events divided by scope
        // _t contains all the tasks together, and _c does the same
        self.history_t = new Array();  // per task
        self.history_c = new Array();  // per contest
        self.history_g = new Array();  // global
        ''')
        self.ds = datastore

    def request_update(self, callback):
        HTTPRequest().asyncGet(history_url, HistoryCallback(self, callback))

    def perform_update(self, data, callback):
        JS('''
        var d = new Object();
        for (var u_id in self.ds.users) {
            d[u_id] = new Object();
            for (var t_id in self.ds.tasks) {
                d[u_id][t_id] = 0.0;
            }
        }

        self.history_t = new Array();
        self.history_c = new Array();
        self.history_g = new Array();
        ''')

        for user, task, time, score in data:
            JS('''
            if (d[user]) {
                d[user][task] = score;

                self.history_t.push([user, task, time, score]);

                var contest_id = self.ds.tasks[task]['contest'];
                var tmp_score = 0.0;
                for (var t_id in d[user]) {
                    if (self.ds.tasks[t_id]['contest'] == contest_id) {
                        tmp_score += d[user][t_id];
                    }
                }
                self.history_c.push([user, contest_id, time, tmp_score])

                var tmp_score = 0.0;
                for (var t_id in d[user]) {
                    tmp_score += d[user][t_id];
                }
                self.history_g.push([user, time, tmp_score]);
            }
            ''')

        callback()

    def get_score_history_for_task(self, user_id, task_id):
        JS('''
        var result = new Array();

        for (var i in self.history_t) {
            var user = self.history_t[i][0];
            var task = self.history_t[i][1];
            var time = self.history_t[i][2];
            var score = self.history_t[i][3];
            if (user == user_id && task == task_id) {
                result.push([time, score, 0]);
            }
        }

        return result;
        ''')

    def get_score_history_for_contest(self, user_id, contest_id):
        JS('''
        var result = new Array();

        for (var i in self.history_c) {
            var user = self.history_c[i][0];
            var contest = self.history_c[i][1];
            var time = self.history_c[i][2];
            var score = self.history_c[i][3];
            if (user == user_id && contest == contest_id) {
                result.push([time, score, 0]);
            }
        }

        return result;
        ''')

    def get_score_history(self, user_id):
        JS('''
        var result = new Array();

        for (var i in self.history_g) {
            var user = self.history_g[i][0];
            var time = self.history_g[i][1];
            var score = self.history_g[i][2];
            if (user == user_id) {
                result.push([time, score, 0]);
            }
        }

        return result;
        ''')

    def get_rank_history_for_task(self, user_id, task_id):
        JS('''
        var d = new Object();
        for (var u_id in self.ds.users) {
            d[u_id] = 0.0;
        }
        var above = 0;
        var equal = Object.keys(self.ds.users).length;

        var result = new Array();

        // TODO consider together changes with the same time
        for (var i in self.history_t) {
            var user = self.history_t[i][0];
            var task = self.history_t[i][1];
            var time = self.history_t[i][2];
            var score = self.history_t[i][3];

            if (task == task_id) {
                if (user == user_id) {
                    d[user_id] = score;
                    var new_above = 0;
                    var new_equal = 0;
                    for (var s in d) {
                        if (d[s] > score) {
                            new_above += 1;
                        } else if (d[s] == score) {
                            new_equal += 1;
                        }
                    }
                    if (new_above != above || new_equal != equal) {
                        above = new_above;
                        equal = new_equal;
                        result.push([time, above+1, equal-1]);
                    }
                } else {
                    changed = false;
                    if (d[user] <= d[user_id] && score > d[user_id]) {
                        above += 1;
                        changed = true;
                    } else if (d[user] > d[user_id] && score <= d[user_id]) {
                        above -= 1;
                        changed = true;
                    }
                    if (d[user] == d[user_id]) {
                        equal -= 1;
                        changed = true;
                    } else if (score == d[user_id]) {
                        equal += 1;
                        changed = true;
                    }
                    if (changed) {
                        result.push([time, above+1, equal-1]);
                    }
                    d[user] = score;
                }
            }
        }

        return result;
        ''')

    def get_rank_history_for_contest(self, user_id, contest_id):
        JS('''
        var d = new Object();
        for (var u_id in self.ds.users) {
            d[u_id] = 0.0;
        }
        var above = 0;
        var equal = Object.keys(self.ds.users).length;

        var result = new Array();

        // TODO consider together changes with the same time
        for (var i in self.history_c) {
            var user = self.history_c[i][0];
            var contest = self.history_c[i][1];
            var time = self.history_c[i][2];
            var score = self.history_c[i][3];

            if (contest == contest_id) {
                if (user == user_id) {
                    d[user_id] = score;
                    var new_above = 0;
                    var new_equal = 0;
                    for (var s in d) {
                        if (d[s] > score) {
                            new_above += 1;
                        } else if (d[s] == score) {
                            new_equal += 1;
                        }
                    }
                    if (new_above != above || new_equal != equal) {
                        above = new_above;
                        equal = new_equal;
                        result.push([time, above+1, equal-1]);
                    }
                } else {
                    changed = false;
                    if (d[user] <= d[user_id] && score > d[user_id]) {
                        above += 1;
                        changed = true;
                    } else if (d[user] > d[user_id] && score <= d[user_id]) {
                        above -= 1;
                        changed = true;
                    }
                    if (d[user] == d[user_id]) {
                        equal -= 1;
                        changed = true;
                    } else if (score == d[user_id]) {
                        equal += 1;
                        changed = true;
                    }
                    if (changed) {
                        result.push([time, above+1, equal-1]);
                    }
                    d[user] = score;
                }
            }
        }

        return result;
        ''')

    def get_rank_history(self, user_id):
        JS('''
        var d = new Object();
        for (var u_id in self.ds.users) {
            d[u_id] = 0.0;
        }
        var above = 0;
        var equal = Object.keys(self.ds.users).length;

        var result = new Array();

        // TODO consider together changes with the same time
        for (var i in self.history_g) {
            var user = self.history_g[i][0];
            var time = self.history_g[i][1];
            var score = self.history_g[i][2];

            if (user == user_id) {
                d[user_id] = score;
                var new_above = 0;
                var new_equal = 0;
                for (var s in d) {
                    if (d[s] > score) {
                        new_above += 1;
                    } else if (d[s] == score) {
                        new_equal += 1;
                    }
                }
                if (new_above != above || new_equal != equal) {
                    above = new_above;
                    equal = new_equal;
                    result.push([time, above+1, equal-1]);
                }
            } else {
                changed = false;
                if (d[user] <= d[user_id] && score > d[user_id]) {
                    above += 1;
                    changed = true;
                } else if (d[user] > d[user_id] && score <= d[user_id]) {
                    above -= 1;
                    changed = true;
                }
                if (d[user] == d[user_id]) {
                    equal -= 1;
                    changed = true;
                } else if (score == d[user_id]) {
                    equal += 1;
                    changed = true;
                }
                if (changed) {
                    result.push([time, above+1, equal-1]);
                }
                d[user] = score;
            }
        }

        return result;
        ''')

