#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2018 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2017 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
# Copyright © 2016 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2016 Amir Keivan Mohtashami <akmohtashami97@gmail.com>
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

"""Random utilities for web servers and page templates.

"""

import logging
from functools import wraps
from urllib.parse import quote, urlencode

from tornado.web import RequestHandler

from cms.db import Session
from cms.server.file_middleware import FileServerMiddleware
from cmscommon.datetime import make_datetime


logger = logging.getLogger(__name__)


# TODO: multi_contest is only relevant for CWS
def multi_contest(f):
    """Return decorator swallowing the contest name if in multi contest mode.

    """
    @wraps(f)
    def wrapped_f(self, *args):
        if self.is_multi_contest():
            # Swallow the first argument (the contest name).
            f(self, *(args[1:]))
        else:
            # Otherwise, just forward all arguments.
            f(self, *args)
    return wrapped_f


class FileHandlerMixin(RequestHandler):

    """Provide methods for serving files.

    Due to shortcomings of Tornado's WSGI support we need to resort to
    hack-ish solutions to achieve efficient file serving. For a more
    detailed explanation see the docstrings of FileServerMiddleware.

    """

    def fetch(self, digest, content_type, filename):
        """Serve the file with the given digest.

        This will just add the headers required to trigger
        FileServerMiddleware, which will do the real work.

        digest (str): the digest of the file that has to be served.
        content_type (str): the MIME type the file should be served as.
        filename (str): the name the file should be served as.

        """
        self.set_header(FileServerMiddleware.DIGEST_HEADER, digest)
        self.set_header(FileServerMiddleware.FILENAME_HEADER, filename)
        self.set_header("Content-Type", content_type)
        self.set_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.finish()


def get_url_root(request_path):
    """Return a relative URL pointing to the root of the website.

    request_path (string): the starting point of the relative path.

    return (string): relative URL from request_path to the root.

    """

    # Compute the number of levels we would need to ascend.
    path_depth = request_path.count("/") - 1

    if path_depth > 0:
        return "/".join([".."] * path_depth)
    else:
        return "."


class Url:
    """An object that helps in building a URL piece by piece.

    """

    def __init__(self, url_root):
        """Create a URL relative to the given root.

        url_root (str): the root of all paths that are generated.

        """
        assert not url_root.endswith("/") or url_root == "/"
        self.url_root = url_root

    def __call__(self, *args, **kwargs):
        """Generate a URL.

        Assemble a URL using the positional arguments as URL components
        and the keyword arguments as the query string. The URL will be
        relative to the root given to the constructor.

        args ([object]): the path components (will be cast to strings).
        kwargs ({str: object}): the query parameters (values will be
            cast to strings).

        return (str): the desired URL.

        """
        url = self.url_root
        for component in args:
            if not url.endswith("/"):
                url += "/"
            url += quote("%s" % component, safe="")
        if kwargs:
            url += "?" + urlencode(kwargs)
        return url

    def __getitem__(self, component):
        """Produce a new Url obtained by extending this instance.

        Return a new Url object that will generate paths based on this
        instance's URL root extended with the path component given as
        argument. That is, if url() is "/foo", then url["bar"]() is
        "/foo/bar".

        component (object): the path component (will be cast to string).

        return (Url): the extended URL generator.

        """
        return self.__class__(self.__call__(component))


class CommonRequestHandler(RequestHandler):
    """Encapsulates shared RequestHandler functionality.

    """

    # Whether the login cookie duration has to be refreshed when
    # this handler is called. Useful to filter asynchronous
    # requests.
    refresh_cookie = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timestamp = make_datetime()
        self.sql_session = Session()
        self.r_params = None
        self.contest = None
        self.url = None

    def prepare(self):
        """This method is executed at the beginning of each request.

        """
        super().prepare()
        self.url = Url(get_url_root(self.request.path))
        self.set_header("Cache-Control", "no-cache, must-revalidate")

    def finish(self, *args, **kwargs):
        """Finish this response, ending the HTTP request.

        We override this method in order to properly close the database.

        TODO - Now that we have greenlet support, this method could be
        refactored in terms of context manager or something like
        that. So far I'm leaving it to minimize changes.

        """
        if self.sql_session is not None:
            try:
                self.sql_session.close()
            except Exception as error:
                logger.warning("Couldn't close SQL connection: %r", error)
        try:
            super().finish(*args, **kwargs)
        except OSError:
            # When the client closes the connection before we reply,
            # Tornado raises an OSError exception, that would pollute
            # our log with unnecessarily critical messages
            logger.debug("Connection closed before our reply.")

    @property
    def service(self):
        return self.application.service
