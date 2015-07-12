#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2015 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2015 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
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

"""Web server for administration of contests.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import base64
import json
import logging
import pkg_resources

from werkzeug.contrib.securecookie import SecureCookie
from werkzeug.wrappers import Request, Response

from cms import config, ServiceCoord, get_service_shards
from cms.db.filecacher import FileCacher
from cms.io import WebService
from cmscommon.datetime import make_timestamp

from .handlers import HANDLERS
from .handlers import views
from .rpc_authorization import rpc_authorization_checker


logger = logging.getLogger(__name__)


AUTHENTICATED_USER_HEADER_IN_ENV = "HTTP_" + \
    WebService.AUTHENTICATED_USER_HEADER.upper().replace('-', '_')


class AdminWebServer(WebService):
    """Service that runs the web server serving the managers.

    """
    def __init__(self, shard):
        parameters = {
            "ui_modules": views,
            "login_url": "/login",
            "template_path": pkg_resources.resource_filename(
                "cms.server.admin", "templates"),
            "static_files": [("cms.server", "static"),
                             ("cms.server.admin", "static")],
            "cookie_secret": base64.b64encode(config.secret_key),
            "debug": config.tornado_debug,
            "auth_middleware": AWSAuthMiddleware,
            "rpc_enabled": True,
            "rpc_auth": rpc_authorization_checker,
        }
        super(AdminWebServer, self).__init__(
            config.admin_listen_port,
            HANDLERS,
            parameters,
            shard=shard,
            listen_address=config.admin_listen_address)

        # A list of pending notifications.
        self.notifications = []

        self.file_cacher = FileCacher(self)
        self.evaluation_service = self.connect_to(
            ServiceCoord("EvaluationService", 0))
        self.scoring_service = self.connect_to(
            ServiceCoord("ScoringService", 0))

        ranking_enabled = len(config.rankings) > 0
        self.proxy_service = self.connect_to(
            ServiceCoord("ProxyService", 0),
            must_be_present=ranking_enabled)

        self.resource_services = []
        for i in range(get_service_shards("ResourceService")):
            self.resource_services.append(self.connect_to(
                ServiceCoord("ResourceService", i)))
        self.logservice = self.connect_to(ServiceCoord("LogService", 0))

    def add_notification(self, timestamp, subject, text):
        """Store a new notification to send at the first
        opportunity (i.e., at the first request for db notifications).

        timestamp (datetime): the time of the notification.
        subject (string): subject of the notification.
        text (string): body of the notification.

        """
        self.notifications.append((timestamp, subject, text))


class JSONSecureCookie(SecureCookie):
    serialization_method = json


class AWSAuthMiddleware(object):
    """Authentication layer for AWS.

    For incoming requests, check if the user's cookies grant them
    access as a specific admin, and in that case adds
    "X-Cms-Authenticated-User" header with value the id of the admin
    (as an int). For outgoing requests, looks for the
    "X-Cms-Authenticated-Cookie" header: if its value is "delete", it
    deletes the user's cookie; if it is "refresh" it refreshes is,
    extending its validity (maybe this implies creating it).

    """

    # Name of the cookie containing the authentication for AWS.
    COOKIE = "awslogin"

    def __init__(self, app):
        """Create an authentication wrapper.

        auth (function|None): underlying WSGI application..

        """
        self._app = app

    def __call__(self, environ, start_response):
        """Execute this instance as a WSGI application."""
        request = Request(environ)
        admin_id = self._authenticate(request)
        if admin_id is not None:
            environ[AUTHENTICATED_USER_HEADER_IN_ENV] = admin_id
        response = self._app(
            environ,
            self._build_start_response(environ, start_response, admin_id))
        return response

    def _build_start_response(self, environ, start_response, admin_id=None):
        """Return a modified start_response function handling cookies.

        environ ({}): WSGI environ object.
        start_response (function): original start_response function
        admin_id (int|None): id of the admin in the cookie, if present.

        return (function): modified start_response function that sets,
            change or delete the cookie based on the decision of the
            underlying application

        """
        def my_start_response(status, headers, exc_info=None):
            cookie = ""
            for i, header in enumerate(headers):
                if header[0] == WebService.AUTHENTICATED_COOKIE_HEADER:
                    cookie = header[1]
                    del headers[i]
                    break
            response = Response(status=status, headers=headers)
            remote_addr = environ.get("REMOTE_ADDR")
            if cookie == "delete":
                response.delete_cookie(AWSAuthMiddleware.COOKIE)
            elif cookie == "refresh":
                response.set_cookie(
                    AWSAuthMiddleware.COOKIE,
                    self._get_cookie(admin_id, remote_addr),
                    httponly=True)
            elif cookie.startswith("create:"):
                response.set_cookie(
                    AWSAuthMiddleware.COOKIE,
                    self._get_cookie(int(cookie.replace("create:", "")),
                                     remote_addr),
                    httponly=True)
            return response(environ, start_response)

        return my_start_response

    def _authenticate(self, request):
        """Check if the cookie exists and is valid

        request (werkzeug.wrappers.Request): werkzeug request object.

        return (int|None): admin id in the cookie, if it is valid.

        """
        cookie = JSONSecureCookie.load_cookie(
            request, AWSAuthMiddleware.COOKIE, config.secret_key)

        admin_id = cookie.get("id", None)
        remote_addr = cookie.get("ip", None)
        timestamp = cookie.get("timestamp", None)
        if admin_id is None or remote_addr is None or timestamp is None:
            return None

        if remote_addr != request.remote_addr:
            return None

        if make_timestamp() - timestamp > config.admin_cookie_duration:
            return None

        return int(admin_id)

    def _get_cookie(self, admin_id, remote_addr):
        """Return the cookie for the given admin.

        admin_id (int): id to save in the cookie.
        remote_addr (unicode): ip of the host making the request.

        return (bytes): secure cookie for the given admin id and the
            current time.

        """
        data = {
            "id": admin_id,
            "ip": remote_addr,
            "timestamp": make_timestamp(),
        }
        return JSONSecureCookie(data, config.secret_key).serialize()
