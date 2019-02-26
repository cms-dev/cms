#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2011-2017 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

import argparse
import functools
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
from werkzeug.exceptions import HTTPException, BadRequest, Unauthorized, \
    Forbidden, NotFound, NotAcceptable, UnsupportedMediaType
from werkzeug.routing import Map, Rule
from werkzeug.wrappers import Request, Response
from werkzeug.wsgi import responder, wrap_file, SharedDataMiddleware, \
    DispatcherMiddleware

# Needed for initialization. Do not remove.
import cmsranking.Logger  # noqa
from cmscommon.eventsource import EventSource
from cmsranking.Config import Config
from cmsranking.Contest import Contest
from cmsranking.Entity import InvalidData
from cmsranking.Scoring import ScoringStore
from cmsranking.Store import Store
from cmsranking.Subchange import Subchange
from cmsranking.Submission import Submission
from cmsranking.Task import Task
from cmsranking.Team import Team
from cmsranking.User import User


logger = logging.getLogger(__name__)


class CustomUnauthorized(Unauthorized):

    def __init__(self, realm_name):
        super().__init__()
        self.realm_name = realm_name

    def get_response(self, environ=None):
        response = super().get_response(environ)
        # XXX With werkzeug-0.9 a full-featured Response object is
        # returned: there is no need for this.
        response = Response.force_type(response)
        response.www_authenticate.set_basic(self.realm_name)
        return response


class StoreHandler:

    def __init__(self, store, username, password, realm_name):
        self.store = store
        self.username = username
        self.password = password
        self.realm_name = realm_name

        self.router = Map([
            Rule("/<key>", methods=["GET"], endpoint="get"),
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
            request.authorization.username == self.username and \
            request.authorization.password == self.password

    def get(self, request, response, key):
        # Limit charset of keys.
        if re.match("^[A-Za-z0-9_]+$", key) is None:
            return NotFound()
        if key not in self.store:
            raise NotFound()

        response.status_code = 200
        response.headers['Timestamp'] = "%0.6f" % time.time()
        response.mimetype = "application/json"
        response.data = json.dumps(self.store.retrieve(key))

    def get_list(self, request, response):
        response.status_code = 200
        response.headers['Timestamp'] = "%0.6f" % time.time()
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
            raise CustomUnauthorized(self.realm_name)
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
        except InvalidData as err:
            logger.warning("Invalid data: %s" % str(err), exc_info=False,
                           extra={'location': request.url,
                                  'details': pprint.pformat(data)})
            raise BadRequest()

        response.status_code = 204

    def put_list(self, request, response):
        if not self.authorized(request):
            logger.info("Unauthorized request.",
                        extra={'location': request.url,
                               'details': repr(request.authorization)})
            raise CustomUnauthorized(self.realm_name)
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
        except InvalidData as err:
            logger.warning("Invalid data: %s" % str(err), exc_info=False,
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
            raise CustomUnauthorized(self.realm_name)

        self.store.delete(key)

        response.status_code = 204

    def delete_list(self, request, response):
        if not self.authorized(request):
            logger.info("Unauthorized request.",
                        extra={'location': request.url,
                               'details': repr(request.authorization)})
            raise CustomUnauthorized(self.realm_name)

        self.store.delete_list()

        response.status_code = 204


class DataWatcher(EventSource):
    """Receive the messages from the entities store and redirect them."""

    def __init__(self, stores, buffer_size):
        self._CACHE_SIZE = buffer_size
        EventSource.__init__(self)

        stores["contest"].add_create_callback(
            functools.partial(self.callback, "contest", "create"))
        stores["contest"].add_update_callback(
            functools.partial(self.callback, "contest", "update"))
        stores["contest"].add_delete_callback(
            functools.partial(self.callback, "contest", "delete"))

        stores["task"].add_create_callback(
            functools.partial(self.callback, "task", "create"))
        stores["task"].add_update_callback(
            functools.partial(self.callback, "task", "update"))
        stores["task"].add_delete_callback(
            functools.partial(self.callback, "task", "delete"))

        stores["team"].add_create_callback(
            functools.partial(self.callback, "team", "create"))
        stores["team"].add_update_callback(
            functools.partial(self.callback, "team", "update"))
        stores["team"].add_delete_callback(
            functools.partial(self.callback, "team", "delete"))

        stores["user"].add_create_callback(
            functools.partial(self.callback, "user", "create"))
        stores["user"].add_update_callback(
            functools.partial(self.callback, "user", "update"))
        stores["user"].add_delete_callback(
            functools.partial(self.callback, "user", "delete"))

        stores["scoring"].add_score_callback(self.score_callback)

    def callback(self, entity, event, key, *args):
        self.send(entity, "%s %s" % (event, key))

    def score_callback(self, user, task, score):
        # FIXME Use score_precision.
        self.send("score", "%s %s %0.2f" % (user, task, score))


class SubListHandler:

    def __init__(self, stores):
        self.task_store = stores["task"]
        self.scoring_store = stores["scoring"]

        self.router = Map([
            Rule("/<user_id>", methods=["GET"], endpoint="sublist"),
        ], encoding_errors="strict")

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)

    def wsgi_app(self, environ, start_response):
        route = self.router.bind_to_environ(environ)
        try:
            endpoint, args = route.match()
        except HTTPException as exc:
            return exc(environ, start_response)

        assert endpoint == "sublist"

        request = Request(environ)
        request.encoding_errors = "strict"

        if request.accept_mimetypes.quality("application/json") <= 0:
            raise NotAcceptable()

        result = list()
        for task_id in self.task_store._store.keys():
            result.extend(
                self.scoring_store.get_submissions(
                    args["user_id"], task_id
                ).values()
            )
        result.sort(key=lambda x: (x.task, x.time))
        result = list(a.__dict__ for a in result)

        response = Response()
        response.status_code = 200
        response.mimetype = "application/json"
        response.data = json.dumps(result)

        return response(environ, start_response)


class HistoryHandler:

    def __init__(self, stores):
        self.scoring_store = stores["scoring"]

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)

    def wsgi_app(self, environ, start_response):
        request = Request(environ)
        request.encoding_errors = "strict"

        if request.accept_mimetypes.quality("application/json") <= 0:
            raise NotAcceptable()

        result = list(self.scoring_store.get_global_history())

        response = Response()
        response.status_code = 200
        response.mimetype = "application/json"
        response.data = json.dumps(result)

        return response(environ, start_response)


class ScoreHandler:

    def __init__(self, stores):
        self.scoring_store = stores["scoring"]

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)

    def wsgi_app(self, environ, start_response):
        request = Request(environ)
        request.encoding_errors = "strict"

        if request.accept_mimetypes.quality("application/json") <= 0:
            raise NotAcceptable()

        result = dict()
        for u_id, tasks in self.scoring_store._scores.items():
            for t_id, score in tasks.items():
                if score.get_score() > 0.0:
                    result.setdefault(u_id, dict())[t_id] = score.get_score()

        response = Response()
        response.status_code = 200
        response.headers['Timestamp'] = "%0.6f" % time.time()
        response.mimetype = "application/json"
        response.data = json.dumps(result)

        return response(environ, start_response)


class ImageHandler:
    EXT_TO_MIME = {
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'gif': 'image/gif',
        'bmp': 'image/bmp'
    }

    MIME_TO_EXT = dict((v, k) for k, v in EXT_TO_MIME.items())

    def __init__(self, location, fallback):
        self.location = location
        self.fallback = fallback

        self.router = Map([
            Rule("/<name>", methods=["GET"], endpoint="get"),
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
        for extension, mimetype in self.EXT_TO_MIME.items():
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

        response.response = wrap_file(environ, open(path, 'rb'))
        response.direct_passthrough = True

        return response


class RootHandler:

    def __init__(self, location):
        self.path = os.path.join(location, "Ranking.html")

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)

    @responder
    def wsgi_app(self, environ, start_response):
        request = Request(environ)
        request.encoding_errors = "strict"

        response = Response()
        response.status_code = 200
        response.mimetype = "text/html"
        response.last_modified = \
            datetime.utcfromtimestamp(os.path.getmtime(self.path))\
                    .replace(microsecond=0)
        # TODO check for If-Modified-Since and If-None-Match
        response.response = wrap_file(environ, open(self.path, 'rb'))
        response.direct_passthrough = True

        return response


class RoutingHandler:

    def __init__(self, root_handler, event_handler, logo_handler,
                 score_handler, history_handler):
        self.router = Map([
            Rule("/", methods=["GET"], endpoint="root"),
            Rule("/history", methods=["GET"], endpoint="history"),
            Rule("/scores", methods=["GET"], endpoint="scores"),
            Rule("/events", methods=["GET"], endpoint="events"),
            Rule("/logo", methods=["GET"], endpoint="logo"),
        ], encoding_errors="strict")

        self.event_handler = event_handler
        self.logo_handler = logo_handler
        self.score_handler = score_handler
        self.history_handler = history_handler
        self.root_handler = root_handler

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
        elif endpoint == "scores":
            return self.score_handler(environ, start_response)
        elif endpoint == "history":
            return self.history_handler(environ, start_response)


def main():
    """Entry point for RWS.

    return (int): exit code (0 on success, 1 on error)

    """
    parser = argparse.ArgumentParser(
        description="Ranking for CMS.")
    parser.add_argument("--config", type=argparse.FileType("rt"),
                        help="override config file")
    parser.add_argument("-d", "--drop", action="store_true",
                        help="drop the data already stored")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="do not require confirmation on dropping data")
    args = parser.parse_args()

    config = Config()
    config.load(args.config)

    if args.drop:
        if args.yes:
            ans = 'y'
        else:
            ans = input("Are you sure you want to delete directory %s? [y/N] " %
                        config.lib_dir).strip().lower()
        if ans in ['y', 'yes']:
            print("Removing directory %s." % config.lib_dir)
            shutil.rmtree(config.lib_dir)
        else:
            print("Not removing directory %s." % config.lib_dir)
        return 0

    stores = dict()

    stores["subchange"] = Store(
        Subchange, os.path.join(config.lib_dir, 'subchanges'), stores)
    stores["submission"] = Store(
        Submission, os.path.join(config.lib_dir, 'submissions'), stores,
        [stores["subchange"]])
    stores["user"] = Store(
        User, os.path.join(config.lib_dir, 'users'), stores,
        [stores["submission"]])
    stores["team"] = Store(
        Team, os.path.join(config.lib_dir, 'teams'), stores,
        [stores["user"]])
    stores["task"] = Store(
        Task, os.path.join(config.lib_dir, 'tasks'), stores,
        [stores["submission"]])
    stores["contest"] = Store(
        Contest, os.path.join(config.lib_dir, 'contests'), stores,
        [stores["task"]])

    stores["contest"].load_from_disk()
    stores["task"].load_from_disk()
    stores["team"].load_from_disk()
    stores["user"].load_from_disk()
    stores["submission"].load_from_disk()
    stores["subchange"].load_from_disk()

    stores["scoring"] = ScoringStore(stores)
    stores["scoring"].init_store()

    toplevel_handler = RoutingHandler(
        RootHandler(config.web_dir),
        DataWatcher(stores, config.buffer_size),
        ImageHandler(
            os.path.join(config.lib_dir, '%(name)s'),
            os.path.join(config.web_dir, 'img', 'logo.png')),
        ScoreHandler(stores),
        HistoryHandler(stores))

    wsgi_app = SharedDataMiddleware(DispatcherMiddleware(
        toplevel_handler, {
            '/contests': StoreHandler(
                stores["contest"],
                config.username, config.password, config.realm_name),
            '/tasks': StoreHandler(
                stores["task"],
                config.username, config.password, config.realm_name),
            '/teams': StoreHandler(
                stores["team"],
                config.username, config.password, config.realm_name),
            '/users': StoreHandler(
                stores["user"],
                config.username, config.password, config.realm_name),
            '/submissions': StoreHandler(
                stores["submission"],
                config.username, config.password, config.realm_name),
            '/subchanges': StoreHandler(
                stores["subchange"],
                config.username, config.password, config.realm_name),
            '/faces': ImageHandler(
                os.path.join(config.lib_dir, 'faces', '%(name)s'),
                os.path.join(config.web_dir, 'img', 'face.png')),
            '/flags': ImageHandler(
                os.path.join(config.lib_dir, 'flags', '%(name)s'),
                os.path.join(config.web_dir, 'img', 'flag.png')),
            '/sublist': SubListHandler(stores),
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
    return 0
