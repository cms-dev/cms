#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2015 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2015-2016 William Di Luigi <williamdiluigi@gmail.com>
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
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from future.builtins.disabled import *  # noqa
from future.builtins import *  # noqa

from .main import \
    LoginHandler, \
    LogoutHandler, \
    StartHandler, \
    NotificationsHandler, \
    StatsHandler, \
    PrintingHandler, \
    DocumentationHandler
from .task import \
    TaskDescriptionHandler, \
    TaskStatementViewHandler, \
    TaskAttachmentViewHandler
from .tasksubmission import \
    SubmitHandler, \
    TaskSubmissionsHandler, \
    SubmissionStatusHandler, \
    SubmissionDetailsHandler, \
    SubmissionFileHandler, \
    UseTokenHandler
from .taskusertest import \
    UserTestInterfaceHandler, \
    UserTestHandler, \
    UserTestStatusHandler, \
    UserTestDetailsHandler, \
    UserTestIOHandler, \
    UserTestFileHandler
from .communication import \
    CommunicationHandler, \
    QuestionHandler


HANDLERS = [

    # Main

    (r"/login", LoginHandler),
    (r"/logout", LogoutHandler),
    (r"/start", StartHandler),
    (r"/notifications", NotificationsHandler),
    (r"/stats", StatsHandler),
    (r"/printing", PrintingHandler),
    (r"/documentation", DocumentationHandler),

    # Tasks

    (r"/tasks/(.*)/description", TaskDescriptionHandler),
    (r"/tasks/(.*)/statements/(.*)", TaskStatementViewHandler),
    (r"/tasks/(.*)/attachments/(.*)", TaskAttachmentViewHandler),

    # Task submissions

    (r"/tasks/(.*)/submit", SubmitHandler),
    (r"/tasks/(.*)/submissions", TaskSubmissionsHandler),
    (r"/tasks/(.*)/submissions/([1-9][0-9]*)", SubmissionStatusHandler),
    (r"/tasks/(.*)/submissions/([1-9][0-9]*)/details",
     SubmissionDetailsHandler),
    (r"/tasks/(.*)/submissions/([1-9][0-9]*)/files/(.*)",
     SubmissionFileHandler),
    (r"/tasks/(.*)/submissions/([1-9][0-9]*)/token", UseTokenHandler),

    # Task usertests

    (r"/testing", UserTestInterfaceHandler),
    (r"/tasks/(.*)/test", UserTestHandler),
    (r"/tasks/(.*)/tests/([1-9][0-9]*)", UserTestStatusHandler),
    (r"/tasks/(.*)/tests/([1-9][0-9]*)/details", UserTestDetailsHandler),
    (r"/tasks/(.*)/tests/([1-9][0-9]*)/(input|output)", UserTestIOHandler),
    (r"/tasks/(.*)/tests/([1-9][0-9]*)/files/(.*)", UserTestFileHandler),

    # Communications

    (r"/communication", CommunicationHandler),
    (r"/question", QuestionHandler),

    # The following prefixes are handled by WSGI middlewares:
    # * /static, defined in cms/io/web_service.py
    # * /stl, defined in cms/server/contest/server.py
]


__all__ = ["HANDLERS"]
