#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2016 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2015 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2015-2016 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
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

"""Base handler classes for CWS.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import traceback
import tornado.web

from cms.db import Contest
from cms.server import CommonRequestHandler


logger = logging.getLogger(__name__)


class BaseHandler(CommonRequestHandler):
    """Base RequestHandler for this application.

    This will also handle the contest list on the homepage.

    """

    def __init__(self, *args, **kwargs):
        super(BaseHandler, self).__init__(*args, **kwargs)
        self.cookie_lang = None
        self.browser_lang = None
        self.langs = None
        self._ = None

    def get(self):
        self.r_params = self.render_params()

        self.render("contest_list.html", **self.r_params)

    def prepare(self):
        """This method is executed at the beginning of each request.

        """
        super(BaseHandler, self).prepare()

        # We need this to be computed for each request because we want to be
        # able to import new contests without having to restart CWS. But only
        # in multi-contest mode.
        self.contest_list = {}
        if self.is_multi_contest():
            for contest in self.sql_session.query(Contest).all():
                self.contest_list[contest.name] = contest

    def render_params(self):
        """Return the default render params used by almost all handlers.

        return (dict): default render params

        """
        ret = {}
        ret["timestamp"] = self.timestamp
        ret["url"] = self.url

        ret["contest_list"] = self.contest_list

        return ret

    def write_error(self, status_code, **kwargs):
        if "exc_info" in kwargs and \
                kwargs["exc_info"][0] != tornado.web.HTTPError:
            exc_info = kwargs["exc_info"]
            logger.error(
                "Uncaught exception (%r) while processing a request: %s",
                exc_info[1], ''.join(traceback.format_exception(*exc_info)))

        # We assume that if r_params is defined then we have at least
        # the data we need to display a basic template with the error
        # information. If r_params is not defined (i.e. something went
        # *really* bad) we simply return a basic textual error notice.
        if getattr(self, 'r_params', None) is not None:
            self.render("error.html", status_code=status_code, **self.r_params)
        else:
            self.write("A critical error has occurred :-(")
            self.finish()

    def is_multi_contest(self):
        """Return whether CWS serves all contests."""
        return self.application.service.contest_id is None


class StaticFileGzHandler(tornado.web.StaticFileHandler):
    """Handle files which may be gzip-compressed on the filesystem.

    """
    def is_multi_contest(self):
        """Return whether CWS serves all contests."""
        return self.application.service.contest_id is None

    def get_absolute_path(self, root, path_or_contest_name):
        if self.is_multi_contest():
            # In multi contest mode, the second argument is the contest name,
            # and we retrieve the file path from path_args.
            return os.path.abspath(os.path.join(root, self.path_args[1]))
        else:
            # Otherwise, we can just use the second argument.
            return os.path.abspath(os.path.join(root, path_or_contest_name))

    def validate_absolute_path(self, root, absolute_path):
        self.is_gzipped = False
        try:
            return tornado.web.StaticFileHandler.validate_absolute_path(
                self, root, absolute_path)
        except tornado.web.HTTPError as e:
            if e.status_code != 404:
                raise
            self.is_gzipped = True
            self.absolute_path = \
                tornado.web.StaticFileHandler.validate_absolute_path(
                    self, root, absolute_path + ".gz")
            self.set_header("Content-encoding", "gzip")
            return self.absolute_path

    def get_content_type(self):
        if self.is_gzipped:
            return "text/plain"
        else:
            return tornado.web.StaticFileHandler.get_content_type(self)
