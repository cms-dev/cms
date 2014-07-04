#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2011-2013 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import functools
import io
import json
import logging
import os
import pprint
import re
import shutil
import time
from datetime import datetime

import gevent
from gevent.pywsgi import WSGIServer

from werkzeug.wrappers import Request, Response
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import HTTPException, BadRequest, Unauthorized, \
    Forbidden, NotFound, NotAcceptable, UnsupportedMediaType
from werkzeug.wsgi import responder, wrap_file, SharedDataMiddleware, \
    DispatcherMiddleware
from werkzeug.utils import redirect

# Needed for initialization. Do not remove.
import cmsranking.Logger

from cmscommon.eventsource import EventSource
from cmsranking.Config import config
from cmsranking.Entity import InvalidData
import cmsranking.Contest as Contest
import cmsranking.Task as Task
import cmsranking.Team as Team
import cmsranking.User as User
import cmsranking.Submission as Submission
import cmsranking.Subchange as Subchange
import cmsranking.Scoring as Scoring


logger = logging.getLogger(__name__)


class CustomUnauthorized(Unauthorized):
    def get_response(self, environ=None):
        response = Unauthorized.get_response(self, environ)
        # XXX With werkzeug-0.9 a full-featured Response object is
        # returned: there is no need for this.
        response = Response.force_type(response)
        response.www_authenticate.set_basic(config.realm_name)
        return response


class StoreHandler(object):
    def __init__(self, store):
        self.store = store

        self.router = Map(
            [Rule("/<key>", methods=["GET"], endpoint="get"),
             Rule("/", methods=["GET"], endpoint="get_list"),
             Rule("/<key>", methods=["PUT"], endpoint="put"),
             Rule("/", methods=["PUT"], endpoint="put_list"),
             Rule("/<key>", methods=["DELETE"], endpoint="delete"),
             Rule("/", methods=["DELETE"], endpoint="delete_list"),
             ], encoding_errors="strict")

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)

    @responder
    def wsgi_app(self, environ, start_response):
        route = self.router.bind_to_environ(environ)
        try:
            endpoint, args = route.match()
        except HTTPException as exc:
            return exc

        request = Request(environ)
        request.encoding_errors = "strict"

        response = Response()

        try:
            if endpoint == "get":
                self.get(request, response, args["key"])
            elif endpoint == "get_list":
                self.get_list(request, response)
            elif endpoint == "put":
                self.put(request, response, args["key"])
            elif endpoint == "put_list":
                self.put_list(request, response)
            elif endpoint == "delete":
                self.delete(request, response, args["key"])
            elif endpoint == "delete_list":
                self.delete_list(request, response)
            else:
                raise RuntimeError()
        except HTTPException as exc:
            return exc

        return response

    def authorized(self, request):
        return request.authorization is not None and \
            request.authorization.type == "basic" and \
            request.authorization.username == config.username and \
            request.authorization.password == config.password

    def get(self, request, response, key):
        # Limit charset of keys.
        if re.match("^[A-Za-z0-9_]+$", key) is None:
            return NotFound()
        if key not in self.store:
            raise NotFound()
        if request.accept_mimetypes.quality("application/json") <= 0:
            raise NotAcceptable()

        response.status_code = 200
        response.headers[b'Timestamp'] = b"%0.6f" % time.time()
        response.mimetype = "application/json"
        response.data = json.dumps(self.store.retrieve(key))

    def get_list(self, request, response):
        if request.accept_mimetypes.quality("application/json") <= 0:
            raise NotAcceptable()

        response.status_code = 200
        response.headers[b'Timestamp'] = b"%0.6f" % time.time()
        response.mimetype = "application/json"
        response.data = json.dumps(self.store.retrieve_list())

    def put(self, request, response, key):
        # Limit charset of keys.
        if re.match("^[A-Za-z0-9_]+$", key) is None:
            return Forbidden()
        if not self.authorized(request):
            logger.warning("Unauthorized request.",
                           extra={'location': request.url,
                                  'details': repr(request.authorization)})
            raise CustomUnauthorized()
        if request.mimetype != "application/json":
            logger.warning("Unsupported MIME type.",
                           extra={'location': request.url,
                                  'details': request.mimetype})
            raise UnsupportedMediaType()

        try:
            data = json.load(request.stream)
        except (TypeError, ValueError):
            logger.warning("Wrong JSON.",
                           extra={'location': request.url})
            raise BadRequest()

        try:
            if key not in self.store:
                self.store.create(key, data)
            else:
                self.store.update(key, data)
        except InvalidData:
            logger.warning("Invalid data.", exc_info=True,
                           extra={'location': request.url,
                                  'details': pprint.pformat(data)})
            raise BadRequest()

        response.status_code = 204

    def put_list(self, request, response):
        if not self.authorized(request):
            logger.info("Unauthorized request.",
                        extra={'location': request.url,
                               'details': repr(request.authorization)})
            raise CustomUnauthorized()
        if request.mimetype != "application/json":
            logger.warning("Unsupported MIME type.",
                           extra={'location': request.url,
                                  'details': request.mimetype})
            raise UnsupportedMediaType()

        try:
            data = json.load(request.stream)
        except (TypeError, ValueError):
            logger.warning("Wrong JSON.",
                           extra={'location': request.url})
            raise BadRequest()

        try:
            self.store.merge_list(data)
        except InvalidData:
            logger.warning("Invalid data.", exc_info=True,
                           extra={'location': request.url,
                                  'details': pprint.pformat(data)})
            raise BadRequest()

        response.status_code = 204

    def delete(self, request, response, key):
        # Limit charset of keys.
        if re.match("^[A-Za-z0-9_]+$", key) is None:
            return NotFound()
        if key not in self.store:
            raise NotFound()
        if not self.authorized(request):
            logger.info("Unauthorized request.",
                        extra={'location': request.url,
                               'details': repr(request.authorization)})
            raise CustomUnauthorized()

        self.store.delete(key)

        response.status_code = 204

    def delete_list(self, request, response):
        if not self.authorized(request):
            logger.info("Unauthorized request.",
                        extra={'location': request.url,
                               'details': repr(request.authorization)})
            raise CustomUnauthorized()

        self.store.delete_list()

        response.status_code = 204


class DataWatcher(EventSource):
    """Receive the messages from the entities store and redirect them."""
    def __init__(self):
        self._CACHE_SIZE = config.buffer_size
        EventSource.__init__(self)

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

    def callback(self, entity, event, key, *args):
        self.send(entity, "%s %s" % (event, key))

    def score_callback(self, user, task, score):
        # FIXME Use score_precision.
        self.send("score", "%s %s %0.2f" % (user, task, score))


def SubListHandler(request, response, user_id):
    if request.accept_mimetypes.quality("application/json") <= 0:
        raise NotAcceptable()

    result = list()
    for task_id in Task.store._store.iterkeys():
        result.extend(Scoring.store.get_submissions(user_id, task_id).values())
    result.sort(key=lambda x: (x.task, x.time))
    result = list(a.__dict__ for a in result)

    response.status_code = 200
    response.mimetype = "application/json"
    response.data = json.dumps(result)


def HistoryHandler(request, response):
    if request.accept_mimetypes.quality("application/json") <= 0:
        raise NotAcceptable()

    result = list(Scoring.store.get_global_history())

    response.status_code = 200
    response.mimetype = "application/json"
    response.data = json.dumps(result)


def ScoreHandler(request, response):
    if request.accept_mimetypes.quality("application/json") <= 0:
        raise NotAcceptable()

    result = dict()
    for u_id, tasks in Scoring.store._scores.iteritems():
        for t_id, score in tasks.iteritems():
            if score.get_score() > 0.0:
                result.setdefault(u_id, dict())[t_id] = score.get_score()

    response.status_code = 200
    response.headers[b'Timestamp'] = b"%0.6f" % time.time()
    response.mimetype = "application/json"
    response.data = json.dumps(result)


class ImageHandler(object):
    EXT_TO_MIME = {
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'gif': 'image/gif',
        'bmp': 'image/bmp'
    }

    MIME_TO_EXT = dict((v, k) for k, v in EXT_TO_MIME.iteritems())

    def __init__(self, location, fallback):
        self.location = location
        self.fallback = fallback

        self.router = Map(
            [Rule("/<name>", methods=["GET"], endpoint="get"),
             ], encoding_errors="strict")

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)

    @responder
    def wsgi_app(self, environ, start_response):
        route = self.router.bind_to_environ(environ)
        try:
            endpoint, args = route.match()
        except HTTPException as exc:
            return exc

        location = self.location % args

        request = Request(environ)
        request.encoding_errors = "strict"

        response = Response()

        available = list()
        for extension, mimetype in self.EXT_TO_MIME.iteritems():
            if os.path.isfile(location + '.' + extension):
                available.append(mimetype)
        mimetype = request.accept_mimetypes.best_match(available)
        if mimetype is not None:
            path = "%s.%s" % (location, self.MIME_TO_EXT[mimetype])
        else:
            path = self.fallback
            mimetype = 'image/png'  # FIXME Hardcoded type.

        response.status_code = 200
        response.mimetype = mimetype
        response.last_modified = \
            datetime.utcfromtimestamp(os.path.getmtime(path))\
                    .replace(microsecond=0)

        # TODO check for If-Modified-Since and If-None-Match

        response.response = wrap_file(environ, io.open(path, 'rb'))
        response.direct_passthrough = True

        return response


class RoutingHandler(object):
    def __init__(self, event_handler, logo_handler):
        self.router = Map(
            [Rule("/", methods=["GET"], endpoint="root"),
             Rule("/sublist/<user_id>", methods=["GET"], endpoint="sublist"),
             Rule("/history", methods=["GET"], endpoint="history"),
             Rule("/scores", methods=["GET"], endpoint="scores"),
             Rule("/events", methods=["GET"], endpoint="events"),
             Rule("/logo", methods=["GET"], endpoint="logo"),
             ], encoding_errors="strict")

        self.event_handler = event_handler
        self.logo_handler = logo_handler
        self.root_handler = redirect("Ranking.html")

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)

    def wsgi_app(self, environ, start_response):
        route = self.router.bind_to_environ(environ)
        try:
            endpoint, args = route.match()
        except HTTPException as exc:
            return exc(environ, start_response)

        if endpoint == "events":
            return self.event_handler(environ, start_response)
        elif endpoint == "logo":
            return self.logo_handler(environ, start_response)
        elif endpoint == "root":
            return self.root_handler(environ, start_response)
        else:
            request = Request(environ)
            request.encoding_errors = "strict"

            response = Response()

            if endpoint == "sublist":
                SubListHandler(request, response, args["user_id"])
            elif endpoint == "scores":
                ScoreHandler(request, response)
            elif endpoint == "history":
                HistoryHandler(request, response)

            return response(environ, start_response)


def main():
    """Entry point for RWS.

    return (bool): True if executed successfully.

    """
    parser = argparse.ArgumentParser(
        description="Ranking for CMS.")
    parser.add_argument("-d", "--drop", action="store_true",
                        help="drop the data already stored")
    args = parser.parse_args()

    if args.drop:
        print("Are you sure you want to delete directory %s? [y/N]" %
              config.lib_dir, end='')
        ans = raw_input().lower()
        if ans in ['y', 'yes']:
            print("Removing directory %s." % config.lib_dir)
            shutil.rmtree(config.lib_dir)
        else:
            print("Not removing directory %s." % config.lib_dir)
        return False

    toplevel_handler = RoutingHandler(DataWatcher(), ImageHandler(
        os.path.join(config.lib_dir, '%(name)s'),
        os.path.join(config.web_dir, 'img', 'logo.png')))

    wsgi_app = SharedDataMiddleware(DispatcherMiddleware(
        toplevel_handler,
        {'/contests': StoreHandler(Contest.store),
         '/tasks': StoreHandler(Task.store),
         '/teams': StoreHandler(Team.store),
         '/users': StoreHandler(User.store),
         '/submissions': StoreHandler(Submission.store),
         '/subchanges': StoreHandler(Subchange.store),
         '/faces': ImageHandler(
             os.path.join(config.lib_dir, 'faces', '%(name)s'),
             os.path.join(config.web_dir, 'img', 'face.png')),
         '/flags': ImageHandler(
             os.path.join(config.lib_dir, 'flags', '%(name)s'),
             os.path.join(config.web_dir, 'img', 'flag.png')),
         }), {'/': config.web_dir})

    servers = list()
    if config.http_port is not None:
        http_server = WSGIServer(
            (config.bind_address, config.http_port), wsgi_app)
        servers.append(http_server)
    if config.https_port is not None:
        https_server = WSGIServer(
            (config.bind_address, config.https_port), wsgi_app,
            certfile=config.https_certfile, keyfile=config.https_keyfile)
        servers.append(https_server)

    try:
        gevent.joinall(list(gevent.spawn(s.serve_forever) for s in servers))
    except KeyboardInterrupt:
        pass
    finally:
        gevent.joinall(list(gevent.spawn(s.stop) for s in servers))
    return True
