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
from datetime import datetime, timedelta
from future.moves.urllib.parse import quote, urlencode

from functools import wraps
from tornado.web import RequestHandler

import gevent
import io

from cms.db import Session
from cms.db.filecacher import FileCacher
from cmscommon.datetime import make_datetime


logger = logging.getLogger(__name__)


def compute_actual_phase(timestamp, contest_start, contest_stop,
                         analysis_start, analysis_stop, per_user_time,
                         starting_time, delay_time, extra_time):
    """Determine the current phase and when the active phase is.

    The "actual phase" of the contest for a certain user is the status
    in which the contest is presented to the user and determines the
    information the latter is allowed to see (and the actions he is
    allowed to perform). In general it may be different for each user.

    The phases, and their meaning, are the following:
    * -2: the user cannot compete because the contest hasn't started
          yet;
    * -1: the user cannot compete because, even if the contest has
          already started, its per-user time frame hasn't yet (this
          usually means the user still has to click on the "start!"
          button in USACO-like contests);
    * 0: the user can compete;
    * +1: the user cannot compete because, even if the contest hasn't
          stopped yet, its per-user time frame already has (again, this
          should normally happen only in USACO-like contests);
    * +2: the user cannot compete because the contest has already
          stopped and the analysis mode hasn't started yet.
    * +3: the user can take part in analysis mode.
    * +4: the user cannot compete because the contest has already
          stopped. analysis mode has already finished or has been
          disabled for this contest.
    A user is said to "compete" if he can read the tasks' statements,
    submit solutions, see their results, etc.

    This function returns the actual phase at the given timestamp, as
    well as its boundaries (i.e. when it started and will end, with
    None meaning +/- infinity) and the boundaries of the phase 0 (if it
    is defined, otherwise None).

    timestamp (datetime): the current time.
    contest_start (datetime): the contest's start.
    contest_stop (datetime): the contest's stop.
    per_user_time (timedelta|None): the amount of time allocated to
        each user; if it's None the contest is traditional, otherwise
        it's USACO-like.
    starting_time (datetime|None): when the user started their time
        frame.
    delay_time (timedelta): how much the user's start is delayed.
    extra_time (timedelta): how much extra time is given to the user at
        the end.

    return (tuple): 5 items: an integer (in [-2, +2]) and two pairs of
        datetimes (or None) defining two intervals.

    """
    # Validate arguments.
    assert (isinstance(timestamp, datetime) and
            isinstance(contest_start, datetime) and
            isinstance(contest_stop, datetime) and
            (per_user_time is None or isinstance(per_user_time, timedelta)) and
            (starting_time is None or isinstance(starting_time, datetime)) and
            isinstance(delay_time, timedelta) and
            isinstance(extra_time, timedelta))

    assert contest_start <= contest_stop
    assert per_user_time is None or per_user_time >= timedelta()
    assert delay_time >= timedelta()
    assert extra_time >= timedelta()

    if per_user_time is not None and starting_time is None:
        # "USACO-like" contest, but we still don't know when the user
        # started/will start.
        actual_start = None
        actual_stop = None

        if contest_start <= timestamp <= contest_stop:
            actual_phase = -1
            current_phase_begin = contest_start
            current_phase_end = contest_stop
        elif timestamp < contest_start:
            actual_phase = -2
            current_phase_begin = None
            current_phase_end = contest_start
        elif contest_stop < timestamp:
            actual_phase = +2
            current_phase_begin = contest_stop
            current_phase_end = None
        else:
            raise RuntimeError("Logic doesn't seem to be working...")

    else:
        if per_user_time is None:
            # "Traditional" contest.
            intended_start = contest_start
            intended_stop = contest_stop
        else:
            # "USACO-like" contest, and we already know when the user
            # started/will start.
            # Both values are lower- and upper-bounded to prevent the
            # ridiculous situations of starting_time being set by the
            # admin way before contest_start or after contest_stop.
            intended_start = min(max(starting_time,
                                     contest_start), contest_stop)
            intended_stop = min(max(starting_time + per_user_time,
                                    contest_start), contest_stop)
        actual_start = intended_start + delay_time
        actual_stop = intended_stop + delay_time + extra_time

        assert contest_start <= actual_start <= actual_stop

        if actual_start <= timestamp <= actual_stop:
            actual_phase = 0
            current_phase_begin = actual_start
            current_phase_end = actual_stop
        elif contest_start <= timestamp < actual_start:
            # This also includes a funny corner case: the user's start
            # is known but is in the future (the admin either set it
            # that way or added some delay after the user started).
            actual_phase = -1
            current_phase_begin = contest_start
            current_phase_end = actual_start
        elif timestamp < contest_start:
            actual_phase = -2
            current_phase_begin = None
            current_phase_end = contest_start
        elif actual_stop < timestamp <= contest_stop:
            actual_phase = +1
            current_phase_begin = actual_stop
            current_phase_end = contest_stop
        elif contest_stop < timestamp:
            actual_phase = +2
            current_phase_begin = max(contest_stop, actual_stop)
            current_phase_end = None
        else:
            raise RuntimeError("Logic doesn't seem to be working...")

    if actual_phase == +2:
        if analysis_start is not None:
            assert contest_stop <= analysis_start
            assert analysis_stop is not None
            assert analysis_start <= analysis_stop
            if timestamp < analysis_start:
                current_phase_end = analysis_start
            elif analysis_start <= timestamp <= analysis_stop:
                current_phase_begin = analysis_start
                # actual_stop might be greater than analysis_start in case
                # of extra_time or delay_time.
                if actual_stop is not None:
                    current_phase_begin = max(analysis_start, actual_stop)
                current_phase_end = analysis_stop
                actual_phase = +3
            elif analysis_stop < timestamp:
                current_phase_begin = analysis_stop
                current_phase_end = None
                actual_phase = +4
            else:
                raise RuntimeError("Logic doesn't seem to be working...")
        else:
            actual_phase = +4

    return (actual_phase,
            current_phase_begin, current_phase_end,
            actual_start, actual_stop)


# TODO: multi_contest and actual_phase_required are only relevant for CWS


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


def actual_phase_required(*actual_phases):
    """Return decorator filtering out requests in the wrong phase.

    actual_phases ([int]): the phases in which the request can pass.

    return (function): the decorator.

    """
    def decorator(func):
        @wraps(func)
        def wrapped(self, *args, **kwargs):
            if self.r_params["actual_phase"] not in actual_phases and \
                    (self.current_user is None or
                     not self.current_user.unrestricted):
                # TODO maybe return some error code?
                self.redirect(self.contest_url())
            else:
                return func(self, *args, **kwargs)
        return wrapped
    return decorator


def filter_ascii(string):
    """Return the printable ascii character in string.

    This to avoid problem printing a string privided by a malicious
    entity.

    string (unicode): the input string.

    return (unicode): string with non-printable chars substituted by *.

    """
    def filter_ascii_char(c):
        """Return * if c is non-printable."""
        if 32 <= ord(c) <= 127:
            return c
        else:
            return '*'

    return "".join(filter_ascii_char(c) for c in string)


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
