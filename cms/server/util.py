#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2015 Stefano Maggiolo <s.maggiolo@gmail.com>
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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa

import time
import logging
from future.moves.urllib.parse import quote, urlencode

from functools import wraps
from tornado.web import RequestHandler

import gevent
import io

from cms.db import Session
from cms.db.filecacher import FileCacher
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


def file_handler_gen(BaseClass):
    """This generates an extension of the BaseHandler that allows us
    to send files to the user. This *Gen is needed because the code in
    the class FileHandler is exactly the same (in AWS and CWS) but
    they inherits from different BaseHandler.

    BaseClass (type): the BaseHandler of our server.

    return (type): a FileHandler extending BaseClass.

    """
    class FileHandler(BaseClass):
        """Base class for handlers that need to serve a file to the user.

        """
        def fetch(self, digest, content_type, filename):
            """Send a file from FileCacher by its digest."""
            if len(digest) == 0:
                logger.error("No digest given")
                self.finish()
                return
            try:
                self.temp_file = \
                    self.service.file_cacher.get_file(digest)
            except Exception:
                logger.error("Exception while retrieving file `%s'.", digest,
                             exc_info=True)
                self.finish()
                return
            self._fetch_temp_file(content_type, filename)

        def fetch_from_filesystem(self, filepath, content_type, filename):
            """Send a file from filesystem by filepath."""
            try:
                self.temp_file = io.open(filepath, 'rb')
            except Exception:
                logger.error("Exception while retrieving file `%s'.", filepath,
                             exc_info=True)
                self.finish()
                return
            self._fetch_temp_file(content_type, filename)

        def _fetch_temp_file(self, content_type, filename):
            """When calling this method, self.temp_file must be a fileobj
            seeked at the beginning of the file.

            """
            self.set_header("Content-Type", content_type)
            self.set_header("Content-Disposition",
                            "attachment; filename=\"%s\"" % filename)
            self.start_time = time.time()
            self.size = 0

            # TODO - Here I'm changing things as few as possible when
            # switching from the asynchronous to the greenlet-based
            # framework; at some point this should be rewritten in a
            # somewhat more greenlet-idomatic way...
            ret = True
            while ret:
                ret = self._fetch_write_chunk()
                gevent.sleep(0)

        def _fetch_write_chunk(self):
            """Send a chunk of the file to the browser.

            """
            data = self.temp_file.read(FileCacher.CHUNK_SIZE)
            length = len(data)
            self.size += length / (1024 * 1024)
            self.write(data)
            if length < FileCacher.CHUNK_SIZE:
                self.temp_file.close()
                duration = time.time() - self.start_time
                logger.info("%.3lf seconds for %.3lf MB",
                            duration, self.size)
                self.finish()
                return False
            return True

    return FileHandler


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


class Url(object):
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
        super(CommonRequestHandler, self).__init__(*args, **kwargs)
        self.timestamp = make_datetime()
        self.sql_session = Session()
        self.r_params = None
        self.contest = None
        self.url = None

    def prepare(self):
        """This method is executed at the beginning of each request.

        """
        super(CommonRequestHandler, self).prepare()
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
            super(CommonRequestHandler, self).finish(*args, **kwargs)
        except IOError:
            # When the client closes the connection before we reply,
            # Tornado raises an IOError exception, that would pollute
            # our log with unnecessarily critical messages
            logger.debug("Connection closed before our reply.")

    @property
    def service(self):
        return self.application.service
