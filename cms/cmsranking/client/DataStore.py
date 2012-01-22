# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2011-2012 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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
        data = JSONParser().decode(response)
        self.callback(self.key, data)

    def onError(self, response, code):
        Window.alert("Error " + code + '\n' + response)


class DataStore:
    def __init__(self, callback):
        self.init_callback = callback
        self.inits_done = 0

        # Dictionaries
        self.contests = dict()
        self.tasks = dict()
        self.teams = dict()
        self.users = dict()

        self.scores = dict()

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
            for (key, val) in JSONParser().decode(data).iteritems():
                self.create_contest(key, val)
            self.done_init()
        HTTPRequest().asyncGet(contest_list_url,
                               TextHandler(contest_dispatch))

        def task_dispatch(data):
            for (key, val) in JSONParser().decode(data).iteritems():
                self.create_task(key, val)
            self.done_init()
        HTTPRequest().asyncGet(task_list_url,
                               TextHandler(task_dispatch))

        def team_dispatch(data):
            for (key, val) in JSONParser().decode(data).iteritems():
                self.create_team(key, val)
            self.done_init()
        HTTPRequest().asyncGet(team_list_url,
                               TextHandler(team_dispatch))

        def user_dispatch(data):
            for (key, val) in JSONParser().decode(data).iteritems():
                self.create_user(key, val)
            self.done_init()
        HTTPRequest().asyncGet(user_list_url,
                               TextHandler(user_dispatch))

        def score_dispatch(data):
            for line in data.split('\n')[:-1]:
                user, task, score = line.split(' ')
                self.set_score(user, task, float(score))
            self.done_init()
        HTTPRequest().asyncGet(score_url,
                               TextHandler(score_dispatch))

    def done_init(self):
        self.inits_done += 1
        if self.inits_done == 5:
            self.init_callback()

    ### Contest

    def contest_listener(self, event):
        (action, key) = event.data.split(" ")
        if action is 'create':
            HTTPRequest().asyncGet(contest_read_url % key,
                                   JsonHandler(key, self.create_contest))
        elif action is 'update':
            HTTPRequest().asyncGet(contest_read_url % key,
                                   JsonHandler(key, self.update_contest))
        elif action is 'delete':
            self.delete_contest(key)

    def create_contest(self, key, data):
        self.contests[key] = data

    def update_contest(self, key, data):
        self.contests[key] = data

    def delete_contest(self, key):
        del self.contests[key]

    ### Task

    def task_listener(self, event):
        (action, key) = event.data.split(" ")
        if action is 'create':
            HTTPRequest().asyncGet(task_read_url % key,
                                   JsonHandler(key, self.create_task))
        elif action is 'update':
            HTTPRequest().asyncGet(task_read_url % key,
                                   JsonHandler(key, self.update_task))
        elif action is 'delete':
            self.delete_task(key)

    def create_task(self, key, data):
        self.tasks[key] = data

    def update_task(self, key, data):
        self.tasks[key] = data

    def delete_task(self, key):
        del self.tasks[key]

    ### Team

    def team_listener(self, event):
        (action, key) = event.data.split(" ")
        if action is 'create':
            HTTPRequest().asyncGet(team_read_url % key,
                                   JsonHandler(key, self.create_team))
        elif action is 'update':
            HTTPRequest().asyncGet(team_read_url % key,
                                   JsonHandler(key, self.update_team))
        elif action is 'delete':
            self.delete_team(key)

    def create_team(self, key, data):
        self.teams[key] = data

    def update_team(self, key, data):
        self.teams[key] = data

    def delete_team(self, key):
        del self.teams[key]

    ### User

    def user_listener(self, event):
        (action, key) = event.data.split(" ")
        if action is 'create':
            HTTPRequest().asyncGet(user_read_url % key,
                                   JsonHandler(key, self.create_user))
        elif action is 'update':
            HTTPRequest().asyncGet(user_read_url % key,
                                   JsonHandler(key, self.update_user))
        elif action is 'delete':
            self.delete_user(key)

    def create_user(self, key, data):
        self.users[key] = data

    def update_user(self, key, data):
        self.users[key] = data

    def delete_user(self, key):
        del self.users[key]

    ### Score

    def score_listener(self, event):
        for line in event.data.split('\n'):
            (user, task, score) = line.split(" ")
            self.set_score(user, task, float(score))

    def set_score(self, user, task, score):
        score = round(score, 2)
        if score == 0.0:
            del self.scores[user][task]
            if not self.scores[user]:
                del self.scores[user]
        else:
            if user not in self.scores:
                self.scores[user] = dict()
            self.scores[user][task] = score

    def get_score_t(self, user, task):
        if user not in self.scores or task not in self.scores[user]:
            return 0
        else:
            return self.scores[user][task]

    def get_score_c(self, user, contest):
        if user not in self.scores:
            return 0
        else:
            return sum([s for t, s in self.scores[user].iteritems()
                        if self.tasks[t]['contest'] == contest])

    def get_score(self, user):
        if user not in self.scores:
            return 0
        else:
            return sum(self.scores[user].itervalues())

    ### Sorting

    def iter_contests(self):
        return sorted(self.contests.iteritems(),
            key=lambda a: (a[1]['begin'], a[1]['end'], a[1]['name'], a[0]))

    def iter_tasks(self):
        return sorted(self.tasks.iteritems(),
            key=lambda a: (a[1]['order'], a[1]['name'], a[0]))

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
