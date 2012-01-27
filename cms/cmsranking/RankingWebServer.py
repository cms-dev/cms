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

import json
import functools
import time
from datetime import datetime
import os
import re
import base64

from Config import config
from Logger import logger

from Entity import InvalidKey, InvalidData
import Store
import Contest
import Task
import Team
import User
import Submission
import Subchange
import Scoring


def authenticated(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if 'Authorization' not in self.request.headers:
            logger.error("Auth: Header is missing\n" + self.request.full_url())
            raise tornado.web.HTTPError(401)
        header = self.request.headers['Authorization']

        try:
            match = re.match('^Basic[ ]+([A-Za-z0-9+/]+[=]{0,2})$', header)
            if match is None:
                raise Exception("Invalid header")
            if len(match.group(1)) % 4 != 0:  # base64 tokens are 4*k chars long
                raise Exception("Invalid header")
            token = base64.b64decode(match.group(1))
            assert ':' in token, "Invalid header"
            username = token.split(':')[0]
            password = ':'.join(token.split(':')[1:])
            assert username == config.username, "Wrong username"
            assert password == config.password, "Wrong password"
        except Exception as e:
            logger.error("Auth: " + str(e) + "\n" + self.request.full_url(),
                         extra={'request_body': header})
            raise tornado.web.HTTPError(401)

        return method(self, *args, **kwargs)
    return wrapper


class DataHandler(tornado.web.RequestHandler):
    def initialize(self):
        if self.request.method == 'POST':
            self.set_status(201)
        else:
            self.set_status(200)

    def set_default_headers(self):
        self.set_header('Content-Type', 'text/plain; charset=UTF-8')

    def write_error(self, status_code, **kwargs):
        if status_code == 401:
            self.set_header('WWW-Authenticate',
                            'Basic realm="' + config.realm_name + '"')

def create_handler(entity_store):
    """Return a handler for the given store.

    Return a RESTful Tornado RequestHandler to manage the given EntityStore.
    The HTTP methods are mapped to the CRUD actions available on the store.
    The returned handler is supposed to be paired with an URL like:
        /<root>/<entity>/(.+)   (the group matches the key of the entity)

    """
    if not isinstance(entity_store, Store.Store):
        raise ValueError("The 'entity_store' parameter isn't a subclass of Store")

    class RestHandler(DataHandler):
        @authenticated
        def put(self, entity_id):
            if not entity_id:
                logger.error("No entity ID specified\n" + self.request.full_url(), extra={'request_body': self.request.body})
                raise tornado.web.HTTPError(404)
            if entity_id not in entity_store:
                # create
                try:
                    entity_store.create(entity_id, self.request.body)
                except InvalidData, exc:
                    logger.error(str(exc) + "\n" + self.request.full_url(), extra={'request_body': self.request.body})
                    raise tornado.web.HTTPError(400)
            else:
                # update
                try:
                    entity_store.update(entity_id, self.request.body)
                except InvalidData, exc:
                    logger.error(str(exc) + "\n" + self.request.full_url(), extra={'request_body': self.request.body})
                    raise tornado.web.HTTPError(400)

        @authenticated
        def delete(self, entity_id):
            # delete
            try:
                entity_store.delete(entity_id)
            except InvalidKey:
                raise tornado.web.HTTPError(404)

        def get(self, entity_id):
            if not entity_id:
                # list
                self.write(entity_store.list() + '\n')
            else:
                # retrieve
                try:
                    entity = entity_store.retrieve(entity_id)
                    self.write(entity + '\n')
                except InvalidKey:
                    raise tornado.web.HTTPError(404)

    return RestHandler


class MessageProxy(object):
    """Receive the messages from the entities store and redirect them."""
    def __init__(self):
        self.clients = list()

        Contest.store.add_create_callback(
            functools.partial(self.callback, "contest", "create"))
        Contest.store.add_update_callback(
            functools.partial(self.callback, "contest", "update"))
        Contest.store.add_delete_callback(
            functools.partial(self.callback, "contest", "delete"))

        Task.store.add_create_callback(
            functools.partial(self.callback, "task", "create"))
        Task.store.add_update_callback(
            functools.partial(self.callback, "task", "update"))
        Task.store.add_delete_callback(
            functools.partial(self.callback, "task", "delete"))

        Team.store.add_create_callback(
            functools.partial(self.callback, "team", "create"))
        Team.store.add_update_callback(
            functools.partial(self.callback, "team", "update"))
        Team.store.add_delete_callback(
            functools.partial(self.callback, "team", "delete"))

        User.store.add_create_callback(
            functools.partial(self.callback, "user", "create"))
        User.store.add_update_callback(
            functools.partial(self.callback, "user", "update"))
        User.store.add_delete_callback(
            functools.partial(self.callback, "user", "delete"))

        Scoring.store.add_score_callback(self.score_callback)

    def callback(self, entity, event, key):
        msg = 'id: ' + str(int(time.time())) + '\n' + \
              'event: ' + entity + '\n' + \
              'data: ' + event + ' ' + key + '\n' + \
              '\n'
        self.send(msg)

    def score_callback(self, user, task, score):
        msg = 'id: ' + str(int(time.time())) + '\n' + \
              'event: score\n' + \
              'data: ' + user + ' ' + task + ' ' + str(score) + '\n' + \
              '\n'
        self.send(msg)

    def send(self, message):
        for client in self.clients:
            client(message)

    def add_callback(self, callback):
        self.clients.append(callback)

    def remove_callback(self, callback):
        self.clients.remove(callback)

proxy = MessageProxy()


class NotificationHandler(DataHandler):
    """Provide notification of the changes in the data store."""
    @tornado.web.asynchronous
    def get(self):
        """Send asynchronous updates."""
        global proxy
        self.set_status(200)
        self.set_header('Content-Type', 'text/event-stream')
        self.set_header('Cache-Control', 'no-cache')
        self.flush()
        self.write('retry: 0\n')
        self.write('\n')
        self.flush()

        proxy.add_callback(self.send_event)

        # TODO add automatic connection close after a certain timeout

    def on_connection_close(self):
        proxy.remove_callback(self.send_event)

    def send_event(self, message):
        self.write(message)
        self.flush()


class SubListHandler(DataHandler):
    def get(self, user_id):
        result = list()
        for task_id in Task.store._store.iterkeys():
            result.extend(Scoring.store.get_submissions(user_id, task_id).values())
        result.sort(key=lambda x: (x.task, x.time))
        self.write(json.dumps(map(lambda a: a.__dict__, result)) + '\n')


class HistoryHandler(DataHandler):
    def get(self):
        self.write(json.dumps(list(Scoring.store.get_global_history())) + '\n')


class ScoreHandler(DataHandler):
    def get(self):
        for u_id, d in Scoring.store._scores.iteritems():
            for t_id, score in d.iteritems():
                if score.get_score() > 0.0:
                    self.write('%s %s %f\n' % (u_id, t_id, score.get_score()))


class ImageHandler(tornado.web.RequestHandler):
    formats = {
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'gif': 'image/gif',
        'bmp': 'image/bmp'
    }

    def initialize(self, location, fallback):
        self.location = location
        self.fallback = fallback

    def get(self, *args):
        self.location %= tuple(args)

        for ext, type in self.formats.iteritems():
            if os.path.isfile(self.location + '.' + ext):
                self.serve(self.location + '.' + ext, type)
                return

        self.serve(self.fallback, 'image/png')  # FIXME hardcoded type

    def serve(self, path, type):
        self.set_header("Content-Type", type)

        modified = datetime.utcfromtimestamp(int(os.path.getmtime(path)))
        self.set_header('Last-Modified', modified)

        # TODO check for If-Modified-Since and If-None-Match

        with open(path, 'rb') as f:
            self.write(f.read())


class HomeHandler(tornado.web.RequestHandler):
    def get(self):
        self.redirect('Ranking.html')


def main():
    application = tornado.web.Application(
        [
            (r"/contests/([A-Za-z0-9_]*)", create_handler(Contest.store)),
            (r"/tasks/([A-Za-z0-9_]*)", create_handler(Task.store)),
            (r"/teams/([A-Za-z0-9_]*)", create_handler(Team.store)),
            (r"/users/([A-Za-z0-9_]*)", create_handler(User.store)),
            (r"/submissions/([A-Za-z0-9_]*)", create_handler(Submission.store)),
            (r"/subchanges/([A-Za-z0-9_]*)", create_handler(Subchange.store)),
            (r"/sublist/([A-Za-z0-9_]+)", SubListHandler),
            (r"/history", HistoryHandler),
            (r"/scores", ScoreHandler),
            (r"/events", NotificationHandler),
            (r"/logo", ImageHandler, {
                'location': os.path.join(config.lib_dir, 'logo'),
                'fallback': os.path.join(config.web_dir, 'img', 'logo.png')
            }),
            (r"/faces/([A-Za-z0-9_]+)", ImageHandler, {
                'location': os.path.join(config.lib_dir, 'faces', '%s'),
                'fallback': os.path.join(config.web_dir, 'img', 'face.png')
            }),
            (r"/flags/([A-Za-z0-9_]+)", ImageHandler, {
                'location': os.path.join(config.lib_dir, 'flags', '%s'),
                'fallback': os.path.join(config.web_dir, 'img', 'flag.png')
            }),
            (r"/(.+)", tornado.web.StaticFileHandler, {
                'path': config.web_dir
            }),
            (r"/", HomeHandler)
        ])
    # application.add_transform (tornado.web.ChunkedTransferEncoding)
    application.listen(config.port)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    main()
