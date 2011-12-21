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

from EventSrc import EventSrc

from pyjamas.HTTPRequest import HTTPRequest
from pyjamas.JSONParser import JSONParser

from pyjamas import Window

from __pyjamas__ import JS


# Config
event_url = '/events'
contest_read_url = '/contests/%s'
contest_list_url = '/contests/'
task_read_url = '/tasks/%s'
task_list_url = '/tasks/'
team_read_url = '/teams/%s'
team_list_url = '/teams/'
user_read_url = '/users/%s'
user_list_url = '/users/'
score_url = '/scores'


class TextHandler:
    def __init__(self, callback):
        self.callback = callback

    def onCompletion(self, response):
        self.callback(response)

    def onError(self, response, code):
        Window.alert("Error " + code + '\n' + response)


class JsonHandler:
    def __init__(self, key, callback):
        self.key = key
        self.callback = callback

    def onCompletion(self, response):
        JS('''
        var data = JSON.parse(response);
        self.callback(self.key, data);
        ''')

    def onError(self, response, code):
        Window.alert("Error " + code + '\n' + response)


class DataStore:
    def __init__(self, callback):
        self.init_callback = callback
        self.inits_todo = 0

        # Dictionaries
        JS('''
        self.contests = new Object();
        self.tasks = new Object();
        self.teams = new Object();
        self.users = new Object();

        self.scores = new Object();

        self.contest_list = new Array();
        self.team_list = new Array();
        ''')

        self.selected = set()
        self.select_handlers = list()

        # Event listeners
        self.es = EventSrc(event_url)
        self.es.add_event_listener("contest", self.contest_listener)
        self.es.add_event_listener("task", self.task_listener)
        self.es.add_event_listener("team", self.team_listener)
        self.es.add_event_listener("user", self.user_listener)

        # Initial data
        def contest_dispatch(data):
            JS('''
            var data = JSON.parse(data);
            for (var key in data) {
                self.create_contest(key, data[key]);
            }
            self.done_init();
            ''')
        self.inits_todo += 1
        HTTPRequest().asyncGet(contest_list_url, TextHandler(contest_dispatch))

        def task_dispatch(data):
            JS('''
            var data = JSON.parse(data);
            for (var key in data) {
                self.create_task(key, data[key]);
            }
            self.done_init();
            ''')
        self.inits_todo += 1
        HTTPRequest().asyncGet(task_list_url, TextHandler(task_dispatch))

        def team_dispatch(data):
            JS('''
            var data = JSON.parse(data);
            for (var key in data) {
                self.create_team(key, data[key]);
            }
            self.done_init();
            ''')
        self.inits_todo += 1
        HTTPRequest().asyncGet(team_list_url, TextHandler(team_dispatch))

        def user_dispatch(data):
            JS('''
            var data = JSON.parse(data);
            for (var key in data) {
                self.create_user(key, data[key]);
            }
            self.done_init();
            ''')
        self.inits_todo += 1
        HTTPRequest().asyncGet(user_list_url, TextHandler(user_dispatch))

        def score_dispatch(data):
            for line in data.split('\n')[:-1]:
                user, task, score = line.split(' ')
                self.set_score(user, task, float(score))
            self.done_init()
        self.inits_todo += 1
        HTTPRequest().asyncGet(score_url, TextHandler(score_dispatch))

    def done_init(self):
        """Called by each init when it's done."""
        self.inits_todo -= 1
        if self.inits_todo == 0:
            self.init_callback()

    ### Contest

    def contest_listener(self, event):
        action, key = event.data.split(' ')
        if action is 'create':
            HTTPRequest().asyncGet(contest_read_url % key,
                                   JsonHandler(key, self.create_contest))
        elif action is 'update':
            HTTPRequest().asyncGet(contest_read_url % key,
                                   JsonHandler(key, self.update_contest))
        elif action is 'delete':
            self.delete_contest(key)

    def create_contest(self, key, data):
        JS('''
        data["key"] = key;
        data["tasks"] = new Array();
        self.contests[key] = data;

        // Insert data in the sorted contest list
        var a = data;
        for (var i = 0; i < self.contest_list.length; i += 1) {
            var b = self.contest_list[i];
            if ((a["begin"] < b["begin"]) || ((a["begin"] == b["begin"]) &&
               ((a["end"]   < b["end"]  ) || ((a["end"]   == b["end"]  ) &&
               ((a["name"]  < b["name"] ) || ((a["name"]  == b["name"] ) &&
               (key < b["key"]))))))) {
                // We found the first element which is greater than a
                self.contest_list.splice(i, 0, a);
                return;
            }
        }
        self.contest_list.push(a);
        ''')

    def update_contest(self, key, data):
        JS('''
        self.delete_contest(key);
        self.create_contest(key, data);
        ''')

    def delete_contest(self, key):
        JS('''
        delete self.contests[key];

        // Remove data from the sorted contest list
        for (var i = 0; i < self.contest_list.length; i += 1) {
            var b = self.contest_list[i];
            if (key == b["key"]) {
                self.contest_list.splice(i, 1);
                return;
            }
        }
        self.contest_list.pop();
        ''')

    ### Task

    def task_listener(self, event):
        action, key = event.data.split(' ')
        if action is 'create':
            HTTPRequest().asyncGet(task_read_url % key,
                                   JsonHandler(key, self.create_task))
        elif action is 'update':
            HTTPRequest().asyncGet(task_read_url % key,
                                   JsonHandler(key, self.update_task))
        elif action is 'delete':
            self.delete_task(key)

    def create_task(self, key, data):
        JS('''
        if (!self.contests[data["contest"]])
        {
            console.error("Could not find contest: " + data["contest"]);
            return;
        }
        var task_list = self.contests[data["contest"]]["tasks"];

        data["key"] = key;
        self.tasks[key] = data;

        // Insert data in the sorted task list for the contest
        var a = data;
        for (var i = 0; i < task_list.length; i += 1) {
            var b = task_list[i];
            if ((a["order"] < b["order"]) || ((a["order"] == b["order"]) &&
               ((a["name"]  < b["name"] ) || ((a["name"]  == b["name"] ) &&
               (key < b["key"]))))) {
                // We found the first element which is greater than a
                task_list.splice(i, 0, a);
                return;
            }
        }
        task_list.push(a);
        ''')


    def update_task(self, key, data):
        JS('''
        self.delete_task(key);
        self.create_task(key, data);
        ''')

    def delete_task(self, key):
        JS('''
        var task_list = self.contests[self.tasks[key]["contest"]]["tasks"];

        delete self.tasks[key];

        // Remove data from the sorted task list for the contest
        for (var i = 0; i < task_list.length; i += 1) {
            var b = task_list[i];
            if (key == b["key"]) {
                task_list.splice(i, 1);
                return;
            }
        }
        task_list.pop();
        ''')

    ### Team

    def team_listener(self, event):
        action, key = event.data.split(' ')
        if action is 'create':
            HTTPRequest().asyncGet(team_read_url % key,
                                   JsonHandler(key, self.create_team))
        elif action is 'update':
            HTTPRequest().asyncGet(team_read_url % key,
                                   JsonHandler(key, self.update_team))
        elif action is 'delete':
            self.delete_team(key)

    def create_team(self, key, data):
        JS('''
        data["key"] = key;
        self.teams[key] = data;

        // Insert data in the sorted team list
        var a = data;
        for (var i = 0; i < self.team_list.length; i += 1) {
            var b = self.team_list[i];
            if ((a["name"] < b["name"]) || (key < b["key"])) {
                // We found the first element which is greater than a
                self.team_list.splice(i, 0, a);
                return;
            }
        }
        self.team_list.push(a);
        ''')

    def update_team(self, key, data):
        JS('''
        self.delete_team(key);
        self.create_team(key, data);
        ''')

    def delete_team(self, key):
        JS('''
        delete self.teams[key];

        // Remove data from the sorted team list
        for (var i = 0; i < self.team_list.length; i += 1) {
            var b = self.team_list[i];
            if (key == b["key"]) {
                self.team_list.splice(i, 1);
                return;
            }
        }
        self.team_list.pop();
        ''')

    ### User

    def user_listener(self, event):
        action, key = event.data.split(' ')
        if action is 'create':
            HTTPRequest().asyncGet(user_read_url % key,
                                   JsonHandler(key, self.create_user))
        elif action is 'update':
            HTTPRequest().asyncGet(user_read_url % key,
                                   JsonHandler(key, self.update_user))
        elif action is 'delete':
            self.delete_user(key)

    def create_user(self, key, data):
        JS('''
        if (data["team"] !== null && !self.teams[data["team"]])
        {
            console.error("Could not find team: " + data["team"]);
            data["team"] = null;
        }

        data["key"] = key;
        self.users[key] = data;
        ''')

    def update_user(self, key, data):
        JS('''
        self.delete_user(key);
        self.create_user(key, data);
        ''')

    def delete_user(self, key):
        JS('''
        delete self.users[key];
        ''')

    ### Score

    def score_listener(self, event):
        for line in event.data.split('\n'):
            user, task, score = line.split(' ')
            self.set_score(user, task, float(score))
            print user, task, score

    def set_score(self, user, task, score):
        JS('''
        if (score === 0.0) {
            delete self.scores[user][task];
            if (Object.keys(self.scores[user]).length === 0) {
                delete self.scores[user];
            }
        } else {
            if (!self.scores[user]) {
                self.scores[user] = new Object();
            }
            self.scores[user][task] = score;
        }
        ''')

    def get_score_t(self, user, task):
        JS('''
        if (!self.scores[user] || !self.scores[user][task]) {
            return 0.0;
        } else {
            return self.scores[user][task];
        }
        ''')

    def get_score_c(self, user, contest):
        JS('''
        if (!self.scores[user]) {
            return 0.0;
        } else {
            var sum = 0.0;
            for (var t_id in self.scores[user]) {
                if (self.tasks[t_id]["contest"] == contest) {
                    sum += self.scores[user][t_id];
                }
            }
            return sum;
        }
        ''')

    def get_score(self, user):
        JS('''
        if (!self.scores[user]) {
            return 0.0;
        } else {
            var sum = 0.0;
            for (var t_id in self.scores[user]) {
                sum += self.scores[user][t_id];
            }
            return sum;
        }
        ''')

    ### Selection

    def set_selected(self, u_id, flag):
        if flag:
            if u_id not in self.selected:
                self.selected.add(u_id)
                for h in self.select_handlers:
                    h(u_id, flag)
        else:
            if u_id in self.selected:
                self.selected.remove(u_id)
                for h in self.select_handlers:
                    h(u_id, flag)


    def get_selected(self, u_id):
        return u_id in self.selected

    def add_select_handler(self, handler):
        self.select_handlers.append(handler)
