#!/usr/bin/python
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

import tornado.ioloop
import tornado.web

import argparse
import shutil
import simplejson as json
import functools
import time
from datetime import datetime
import os
import re
import base64
import ssl

from cmsranking.Config import config
from cmsranking.Logger import logger

from cmsranking.Entity import InvalidKey, InvalidData
import cmsranking.Store as Store
import cmsranking.Contest as Contest
import cmsranking.Task as Task
import cmsranking.Team as Team
import cmsranking.User as User
import cmsranking.Submission as Submission
import cmsranking.Subchange as Subchange
import cmsranking.Scoring as Scoring


def authenticated(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if 'Authorization' not in self.request.headers:
            logger.warning("Authentication: Header is missing",
                           extra={'location': self.request.full_url()})
            raise tornado.web.HTTPError(401)
        header = self.request.headers['Authorization']

        try:
            match = re.match('^Basic[ ]+([A-Za-z0-9+/]+[=]{0,2})$', header)
            if match is None:
                raise Exception("Invalid header")
            if len(match.group(1)) % 4 != 0:  # base64 tokens are 4k chars long
                raise Exception("Invalid header")
            token = base64.b64decode(match.group(1))
            assert ':' in token, "Invalid header"
            username = token.split(':')[0]
            password = ':'.join(token.split(':')[1:])
            assert username == config.username, "Wrong username"
            assert password == config.password, "Wrong password"
        except Exception as exc:
            logger.warning("Authentication: %s" % exc, exc_info=False,
                           extra={'location': self.request.full_url(),
                                  'details': header})
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
        self.set_header('Date', datetime.utcnow())
        # In case we need sub-second precision (and we do...).
        self.set_header('Timestamp', "%0.6f" % time.time())
        self.set_header("Cache-Control", "no-cache, must-revalidate")

    def write_error(self, status_code, **kwargs):
        if status_code == 401:
            self.set_header('WWW-Authenticate',
                            'Basic realm="' + config.realm_name + '"')


def create_handler(entity_store):
    """Return a handler for the given store.

    Return a RESTful Tornado RequestHandler to manage the given
    EntityStore. The HTTP methods are mapped to the CRUD actions
    available on the store. The returned handler is supposed to be
    paired with an URL like:
        /<root>/<entity>/(.*)   (the group matches the key of the entity)

    When the key is an empty string, we assume the operation is targeted
    on the entire collection of entities.

    """
    if not isinstance(entity_store, Store.Store):
        raise ValueError("The 'entity_store' parameter "
                         "isn't a subclass of Store")

    class RestHandler(DataHandler):
        @authenticated
        def put(self, entity_id):
            if not entity_id:
                # merge list
                try:
                    entity_store.merge_list(self.request.body,
                                            self.finish)
                except InvalidData as exc:
                    logger.error(str(exc), exc_info=False,
                                 extra={'location': self.request.full_url(),
                                        'details': self.request.body})
                    raise tornado.web.HTTPError(400)
            elif entity_id not in entity_store:
                # create
                try:
                    entity_store.create(entity_id, self.request.body,
                                        self.finish)
                except InvalidData as exc:
                    logger.error(str(exc), exc_info=False,
                                 extra={'location': self.request.full_url(),
                                        'details': self.request.body})
                    raise tornado.web.HTTPError(400)
            else:
                # update
                try:
                    entity_store.update(entity_id, self.request.body,
                                        self.finish)
                except InvalidData as exc:
                    logger.error(str(exc), exc_info=False,
                                 extra={'location': self.request.full_url(),
                                        'details': self.request.body})
                    raise tornado.web.HTTPError(400)

        @authenticated
        def delete(self, entity_id):
            if not entity_id:
                # delete list
                entity_store.delete_list(self.finish)
            elif entity_id in entity_store:
                # delete
                try:
                    entity_store.delete(entity_id, self.finish)
                except InvalidKey:
                    logger.error("Entity %s doesn't exist" % entity_id,
                                 extra={'location': self.request.full_url()})
                    raise tornado.web.HTTPError(404)

        def get(self, entity_id):
            if not entity_id:
                # retrieve list
                self.write(entity_store.retrieve_list() + '\n')
            else:
                # retrieve
                try:
                    self.write(entity_store.retrieve(entity_id) + '\n')
                except InvalidKey:
                    raise tornado.web.HTTPError(404)

    return RestHandler


class MessageProxy(object):
    """Receive the messages from the entities store and redirect them."""
    def __init__(self):
        self.clients = list()

        # We keep a buffer of sent messages, to send them to the clients
        # that temporarily lose the connection, to avoid them missing
        # any data. We push messages to the _new_buffer. When it fills
        # up (i.e. reaches config.buffer_size messages) we drop the
        # _old_buffer, make the _new_buffer become the _old_buffer and
        # set up a new empty _new_buffer. In this way every push
        # requires O(1) time and we keep at most 2 * config.buffer_size
        # messages in the buffers.
        self._new_buffer = list()
        self._old_buffer = list()

        # The "age" of the buffers is the minimum time such that we are
        # sure to have all events that happened after that time.
        self.age = time.time()

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
        timestamp = time.time()
        msg = 'id: %0.6f\n' \
              'event: %s\n' \
              'data: %s %s\n' \
              '\n' % (timestamp, entity, event, key)
        self.send(msg, timestamp)

    def score_callback(self, user, task, score):
        timestamp = time.time()
        msg = 'id: %0.6f\n' \
              'event: score\n' \
              'data: %s %s %0.2f\n' \
              '\n' % (timestamp, user, task, score)
        self.send(msg, timestamp)

    def send(self, message, timestamp):
        for client in self.clients:
            client(message)
        if len(self._new_buffer) == config.buffer_size:
            if self._old_buffer:
                self.age = self._old_buffer[-1][0]
            self._old_buffer = self._new_buffer
            self._new_buffer = list()
        self._new_buffer.append((timestamp, message))

    @property
    def buffer(self):
        for msg in self._old_buffer:
            yield msg
        for msg in self._new_buffer:
            yield msg

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
        self.set_status(200)
        self.set_header('Content-Type', 'text/event-stream')
        self.set_header('Cache-Control', 'no-cache')
        self.flush()

        # This is only needed to make Firefox fire the 'open' event on
        # the EventSource object.
        self.write(':\n')
        self.flush()

        # The EventSource polyfill will only deliver events once the
        # connection has been closed, so we have to finish the request
        # right after the first message has been sent. This custom
        # header allows us to identify the requests from the polyfill.
        self.one_shot = False
        if 'X-Requested-With' in self.request.headers and \
                self.request.headers['X-Requested-With'] == 'XMLHttpRequest':
            self.one_shot = True

        # We get the ID of the last event the client received. We give
        # priority to the HTTP header because it's more reliable: on the
        # first connection the client won't use the header but will use
        # the argument (set by us); if it disconnects, it will try to
        # reconnect with the same argument (which is now outdated) but
        # with the header correctly set (which is what we want).
        if "Last-Event-ID" in self.request.headers:
            last_id = float(self.request.headers.get_list("Last-Event-ID")[-1])
        elif self.get_argument("last_event_id", None) != None:
            last_id = float(self.get_argument("last_event_id", None))
        else:
            last_id = time.time()

        self.outdated = False
        if last_id < proxy.age:
            self.outdated = True
            # The reload event will tell the client that we can't update
            # its data using buffered event and that it'll need to init
            # it again from scratch (in pratice: reload the page).
            self.write("event: reload\n")
            self.write("data: _\n\n")
            # We're keeping the connection open because we want the
            # client to close it. If we'd close it the client (i.e. the
            # browser) may automatically attempt to reconnect before
            # having processed the event we sent it.
            if self.one_shot:
                self.finish()
                # Not calling .clean() because there's nothing to be
                # cleaned yet and because it would have no effect,
                # since self.outdated == True.
            else:
                self.flush()
            return

        sent = False
        for t, msg in proxy.buffer:
            if t > last_id:
                self.write(msg)
                sent = True
        if sent and self.one_shot:
            self.finish()
            # Not calling .clean() because there's nothing to be
            # cleaned yet
            return

        proxy.add_callback(self.send_event)

        def callback():
            self.finish()
            self.clean()

        self.timeout = tornado.ioloop.IOLoop.instance().add_timeout(
            time.time() + config.timeout, callback)

    # If the connection is closed by the client then the "on_connection_
    # _close" callback is called. If we decide to finish the request (by
    # calling the finish() method) then the "on_finish" callback gets
    # called (and "on_connection_close" *won't* be called!).

    def clean(self):
        if not self.outdated:
            proxy.remove_callback(self.send_event)
            tornado.ioloop.IOLoop.instance().remove_timeout(self.timeout)

    def on_connection_close(self):
        self.clean()

    # TODO As soon as we start supporting only Tornado 2.2+ use the
    # .on_finish() callback to call .clean() instead of doing it after
    # every call to .finish().

    def send_event(self, message):
        self.write(message)
        if self.one_shot:
            self.finish()
            self.clean()
        else:
            self.flush()


class SubListHandler(DataHandler):
    def get(self, user_id):
        result = list()
        for task_id in Task.store._store.iterkeys():
            result.extend(Scoring.store.get_submissions(user_id,
                                                        task_id).values())
        result.sort(key=lambda x: (x.task, x.time))
        self.write(json.dumps(map(lambda a: a.__dict__, result)) + '\n')


class HistoryHandler(DataHandler):
    def get(self):
        self.write(json.dumps(list(Scoring.store.get_global_history())) + '\n')


class ScoreHandler(DataHandler):
    def get(self):
        for u_id, dic in Scoring.store._scores.iteritems():
            for t_id, score in dic.iteritems():
                if score.get_score() > 0.0:
                    self.write('%s %s %0.2f\n' %
                               (u_id, t_id, score.get_score()))


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

        for ext, filetype in self.formats.iteritems():
            if os.path.isfile(self.location + '.' + ext):
                self.serve(self.location + '.' + ext, filetype)
                return

        self.serve(self.fallback, 'image/png')  # FIXME hardcoded type

    def serve(self, path, filetype):
        self.set_header("Content-Type", filetype)

        modified = datetime.utcfromtimestamp(int(os.path.getmtime(path)))
        self.set_header('Last-Modified', modified)

        # TODO check for If-Modified-Since and If-None-Match

        with open(path, 'rb') as data:
            self.write(data.read())


class HomeHandler(tornado.web.RequestHandler):
    def get(self):
        # Manually redirect us so that any relative paths are preserved.
        self.set_status(302)
        self.set_header("Location", "Ranking.html")
        self.finish()


def main():
    parser = argparse.ArgumentParser(
        description="Ranking for CMS.")
    parser.add_argument("-d", "--drop",
                        help="drop the data already stored",
                        action="store_true")
    args = parser.parse_args()

    if args.drop:
        print "Are you sure you want to delete directory %s? [y/N]" % \
              config.lib_dir,
        ans = raw_input().lower()
        if ans in ['y', 'yes']:
            print "Removing directory %s." % config.lib_dir
            shutil.rmtree(config.lib_dir)
        else:
            print "Not removing directory %s." % config.lib_dir
        return

    application = tornado.web.Application([
        # FIXME We should allow keys to be arbitrary unicode strings.
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
    # application.add_transform(tornado.web.ChunkedTransferEncoding)
    if config.http_port is not None:
        application.listen(config.http_port, address=config.bind_address)
    if config.https_port is not None:
        application.listen(config.https_port, address=config.bind_address,
                           ssl_options={"ssl_version": ssl.PROTOCOL_SSLv23,
                                        "certfile": config.https_certfile,
                                        "keyfile": config.https_keyfile})

    try:
        tornado.ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        # Exit cleanly.
        return


if __name__ == "__main__":
    main()
