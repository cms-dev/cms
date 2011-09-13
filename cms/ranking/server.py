#!/usr/bin/python
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

import tornado.ioloop
import tornado.web

import store
import json
import functools
import submissions
import time
import os
from operator import attrgetter

def create_handler(entity_store):
    """Return a handler for the given store.

    Return a RESTful Tornado RequestHandler to manage the given EntityStore.
    The HTTP methods are mapped to the CRUD actions available on the store.
    The returned handler is supposed to be paired with an URL like:
        /<root>/<entity>/(.+)   (the group matches the key of the entity)

    """
    assert isinstance(entity_store, store.EntityStore)

    class RestHandler(tornado.web.RequestHandler):

        def prepare(self):
            # uncomment the next line to be automatically authenticated
            # self._current_user = "something"
            pass

        def get_current_user(self):
            # TODO implement some real authentication system
            return None

        @tornado.web.authenticated
        def post(self, entity_id):
            # create
            try:
                entity_store.create(entity_id, self.request.body)
            except store.InvalidKey:
                self.set_status(405)
            except (ValueError, store.InvalidData):
                self.set_status(400)
            else:
                self.set_status(201)

        @tornado.web.authenticated
        def put(self, entity_id):
            # update
            try:
                entity_store.update(entity_id, self.request.body)
            except store.InvalidKey:
                self.set_status(404)
            except (ValueError, store.InvalidData):
                self.set_status(400)
            else:
                self.set_status(200)

        @tornado.web.authenticated
        def delete(self, entity_id):
            # delete
            try:
                entity_store.delete(entity_id)
            except store.InvalidKey:
                self.set_status(404)
            else:
                self.set_status(200)

        def get(self, entity_id):
            if entity_id == '':
                # list
                self.set_status(200)
                self.write(entity_store.list() + '\n')
            else:
                # retrieve
                try:
                    entity = entity_store.retrieve(entity_id)
                except store.InvalidKey:
                    self.set_status(404)
                else:
                    self.set_status(200)
                    self.write(entity + '\n')

    return RestHandler


class NotificationHandler(tornado.web.RequestHandler):
    """Provide notification of the changes in the data store."""
    @tornado.web.asynchronous
    def get(self):
        """Send asynchronous updates."""
        self.set_status(200)
        self.set_header('Content-Type', 'text/event-stream')
        self.set_header('Cache-Control', 'no-cache')
        self.flush()
        self.write('retry: 0\n')
        self.write('\n')
        self.flush()

        store.contest_store.add_create_callback(
            functools.partial(self.callback, "contest", "create"))
        store.contest_store.add_update_callback(
            functools.partial(self.callback, "contest", "update"))
        store.contest_store.add_delete_callback(
            functools.partial(self.callback, "contest", "delete"))

        store.task_store.add_create_callback(
            functools.partial(self.callback, "task", "create"))
        store.task_store.add_update_callback(
            functools.partial(self.callback, "task", "update"))
        store.task_store.add_delete_callback(
            functools.partial(self.callback, "task", "delete"))

        store.team_store.add_create_callback(
            functools.partial(self.callback, "team", "create"))
        store.team_store.add_update_callback(
            functools.partial(self.callback, "team", "update"))
        store.team_store.add_delete_callback(
            functools.partial(self.callback, "team", "delete"))

        store.user_store.add_create_callback(
            functools.partial(self.callback, "user", "create"))
        store.user_store.add_update_callback(
            functools.partial(self.callback, "user", "update"))
        store.user_store.add_delete_callback(
            functools.partial(self.callback, "user", "delete"))

        submissions.submission_store.add_callback(self.score_callback)

    def callback(self, entity, event, key):
        self.write("id: " + str(int(time.time())) + "\n")
        self.write("event: " + entity + "\n")
        self.write("data: " + event + " " + key + "\n")
        self.write("\n")
        self.flush()

    def score_callback(self, user, task, score):
        self.write("id: " + str(int(time.time())) + "\n")
        self.write("event: score\n")
        self.write("data: " + user + " " + task + " " + str(score) + "\n")
        self.write("\n")
        self.flush()


class SubmissionHandler(tornado.web.RequestHandler):
    def prepare(self):
        # uncomment the next line to be automatically authenticated
        # self._current_user = "something"
        pass

    @tornado.web.authenticated
    def post(self, entity_id):
        # create
        try:
            submissions.submission_store.create(entity_id, json.loads(self.request.body))
        except submissions.InvalidKey:
            self.set_status(405)
        except (ValueError, submissions.InvalidTime, submissions.InvalidData):
            self.set_status(400)
        else:
            self.set_status(201)

    @tornado.web.authenticated
    def put(self, entity_id):
        # update
        try:
            submissions.submission_store.update(entity_id, json.loads(self.request.body))
        except submissions.InvalidKey:
            self.set_status(404)
        except (ValueError, submissions.InvalidTime, submissions.InvalidData):
            self.set_status(400)
        else:
            self.set_status(200)

    @tornado.web.authenticated
    def delete(self, entity_id):
        # delete
        try:
            submissions.submission_store.delete(entity_id)
        except submissions.InvalidKey:
            self.set_status(404)
        else:
            self.set_status(200)

    def get(self, entity_id):
        # retrieve
        try:
            entity = submissions.submission_store.retrieve(entity_id)
        except submissions.InvalidKey:
            self.set_status(404)
        else:
            self.set_status(200)
            self.write(json.dumps(entity.dump()) + '\n')


class SubListHandler(tornado.web.RequestHandler):
    def get(self, user_id):
        if user_id not in store.user_store._store:
            self.set_status(404)
        elif user_id not in submissions.submission_store._scores:
            self.set_status(200)
            self.write("[]\n")
        else:
            subs = []
            for task_id, l in submissions.submission_store._scores[user_id].iteritems():
                for i in l._subs.itervalues():
                    s = {}
                    s['task'] = task_id
                    s['time'] = i.time
                    s['score'] = i.get_current_score()
                    s['token'] = i.get_current_token()
                    s['extra'] = i.get_current_extra()
                    subs.append(s)
            subs.sort(key=lambda x: (x['task'], x['time']))
            self.set_status(200)
            self.write(json.dumps(subs) + '\n')


class HistoryHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_status(200)
        self.write(json.dumps(list(submissions.get_global_history())) + '\n')


class ScoreHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_status(200)

        for u_id, user in submissions.submission_store._scores.iteritems():
            for t_id, task in user.iteritems():
                if task._history:
                    self.write('%s %s %f\n' % (u_id, t_id, task._history[-1][1]))


if __name__ == "__main__":
    application = tornado.web.Application([
        (r"/contests/([A-Za-z0-9_]*)", create_handler(store.contest_store)),
        (r"/tasks/([A-Za-z0-9_]*)", create_handler(store.task_store)),
        (r"/teams/([A-Za-z0-9_]*)", create_handler(store.team_store)),
        (r"/users/([A-Za-z0-9_]*)", create_handler(store.user_store)),
        (r"/subs/([A-Za-z0-9_]*)", SubmissionHandler),
        (r"/submissions/([A-Za-z0-9_]+)", SubListHandler),
        (r"/history", HistoryHandler),
        (r"/scores", ScoreHandler),
        (r"/events", NotificationHandler),
        (r"/(.*)", tornado.web.StaticFileHandler,
            dict(path=os.path.join(os.path.dirname(__file__), 'static'))),
    ])
    # application.add_transform (tornado.web.ChunkedTransferEncoding)
    application.listen(8890)
    tornado.ioloop.IOLoop.instance().start()
