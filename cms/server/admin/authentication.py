#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2015 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2016 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

import json

from werkzeug.contrib.securecookie import SecureCookie
from werkzeug.local import Local, LocalManager
from werkzeug.wrappers import Request, Response

from cms import config
from cmscommon.binary import hex_to_bin
from cmscommon.datetime import make_timestamp


class UTF8JSON:
    @staticmethod
    def dumps(d):
        return json.dumps(d).encode('utf-8')

    @staticmethod
    def loads(e):
        return json.loads(e.decode('utf-8'))


class JSONSecureCookie(SecureCookie):
    serialization_method = UTF8JSON


class AWSAuthMiddleware:
    """Handler for the low-level tasks of admin authentication.

    Intercepts all requests and responses to AWS, parses the auth
    cookie to retrieve the admin, provides an interface for the rest of
    the application to access and modify this information, and then
    writes the headers to update the cookie.

    A single instance of this class manages the cookies for all current
    requests at the same time, using a Local object from Werkzeug.

    """
    COOKIE = "awslogin"

    def __init__(self, app):
        """Initialize the middleware, and chain it to the given app.

        app (function): a WSGI application.

        """
        self._app = app

        self._local = Local()
        self._local_manager = LocalManager([self._local])
        self.wsgi_app = self._local_manager.make_middleware(self.wsgi_app)

        self._request = self._local("request")
        self._cookie = self._local("cookie")

    @property
    def admin_id(self):
        """Return the ID of the admin.

        It's the value that has been read from the cookie and (if
        modified by the rest of the application) will be written back.

        returns (int or None): the ID of the admin, if logged in.

        """
        return self._cookie.get("id", None)

    def set(self, admin_id):
        """Set the admin ID that will be stored in the cookie.

        admin_id (int): the ID of the admin (to unset don't pass None:
            use clear()).

        """
        self._cookie["id"] = admin_id
        self._cookie["ip"] = self._request.remote_addr
        self.refresh()

    def refresh(self):
        """Update the timestamp that will be stored in the cookie.

        """
        self._cookie["timestamp"] = make_timestamp()

    def clear(self):
        """Remove all fields from the cookie.

        This doesn't actually cause the client to remove the cookie, it
        just makes it update the stored cookie to an empty value.

        """
        self._cookie.clear()

    def __call__(self, environ, start_response):
        """Invoke the class as a WSGI application.

        environ (dict): the WSGI environment.
        start_response (function): the WSGI start_response callable.
        returns (iterable): the WSGI response data.

        """
        return self.wsgi_app(environ, start_response)

    def wsgi_app(self, environ, start_response):
        """Invoke the class as a WSGI application.

        environ (dict): the WSGI environment.
        start_response (function): the WSGI start_response callable.
        returns (iterable): the WSGI response data.

        """
        self._local.request = Request(environ)
        self._local.cookie = JSONSecureCookie.load_cookie(
            self._request, AWSAuthMiddleware.COOKIE,
            hex_to_bin(config.secret_key))
        self._verify_cookie()

        def my_start_response(status, headers, exc_info=None):
            """Wrapper for the server-provided start_response.

            Once called by the application, modifies the received
            parameters to add the Set-Cookie parameter (if needed)
            and then forwards everything to the server.

            """
            response = Response(status=status, headers=headers)
            self._cookie.save_cookie(
                response, AWSAuthMiddleware.COOKIE, httponly=True)
            return start_response(
                status, response.headers.to_wsgi_list(), exc_info)

        return self._app(environ, my_start_response)

    def _verify_cookie(self):
        """Check whether the cookie is valid, and if not clear it.

        """
        # Clearing an empty cookie marks it as modified and causes it
        # to be sent in the response. This check prevents it.
        if not self._cookie:
            return

        admin_id = self._cookie.get("id", None)
        remote_addr = self._cookie.get("ip", None)
        timestamp = self._cookie.get("timestamp", None)

        if admin_id is None or remote_addr is None or timestamp is None:
            self.clear()
            return

        if not isinstance(admin_id, int) or not isinstance(timestamp, float):
            self.clear()
            return

        if remote_addr != self._request.remote_addr:
            self.clear()
            return

        if make_timestamp() - timestamp > config.admin_cookie_duration:
            self.clear()
            return
