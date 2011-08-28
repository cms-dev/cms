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
                entity_store.create(entity_id, json.loads(self.request.body))
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
                entity_store.update(entity_id, json.loads(self.request.body))
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
            # retrieve
            try:
                entity = entity_store.retrieve(entity_id)
            except store.InvalidKey:
                self.set_status(404)
            else:
                self.set_status(200)
                self.write(json.dumps(entity.dump()))

    return RestHandler


class NotificationHandler(tornado.web.RequestHandler):
    """Provide notification of the changes in the data store."""
    @tornado.web.asynchronous
    def get(self):
        """Send asynchronous updates."""
        self.set_status(200)
        self.flush()

        store.contest_store.add_create_callback(
            functools.partial(self.callback, "contest", "created"))
        store.contest_store.add_update_callback(
            functools.partial(self.callback, "contest", "updated"))
        store.contest_store.add_delete_callback(
            functools.partial(self.callback, "contest", "deleted"))

        store.task_store.add_create_callback(
            functools.partial(self.callback, "task", "created"))
        store.task_store.add_update_callback(
            functools.partial(self.callback, "task", "updated"))
        store.task_store.add_delete_callback(
            functools.partial(self.callback, "task", "deleted"))

        store.team_store.add_create_callback(
            functools.partial(self.callback, "team", "created"))
        store.team_store.add_update_callback(
            functools.partial(self.callback, "team", "updated"))
        store.team_store.add_delete_callback(
            functools.partial(self.callback, "team", "deleted"))

        store.user_store.add_create_callback(
            functools.partial(self.callback, "user", "created"))
        store.user_store.add_update_callback(
            functools.partial(self.callback, "user", "updated"))
        store.user_store.add_delete_callback(
            functools.partial(self.callback, "user", "deleted"))

    def callback(self, entity, event, key):
        self.write(entity + " " + event + " " + key + "\n")
        self.flush()


if __name__ == "__main__":
    application = tornado.web.Application([
        (r"/contests/([A-Za-z0-9_]+)", create_handler(store.contest_store)),
        (r"/tasks/([A-Za-z0-9_]+)", create_handler(store.task_store)),
        (r"/teams/([A-Za-z0-9_]+)", create_handler(store.team_store)),
        (r"/users/([A-Za-z0-9_]+)", create_handler(store.user_store)),
        (r"/notifications", NotificationHandler),
    ])
    # application.add_transform (tornado.web.ChunkedTransferEncoding)
    application.listen(8888)
    tornado.ioloop.IOLoop.instance().start()
