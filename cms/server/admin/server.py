#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2015 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2016 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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
import logging
import pkg_resources

from cms import config, ServiceCoord, get_service_shards
from cms.db.filecacher import FileCacher
from cms.io import WebService

from .handlers import HANDLERS
from .handlers import views
from .authentication import AWSAuthMiddleware
from .rpc_authorization import rpc_authorization_checker


logger = logging.getLogger(__name__)


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
            "rpc_auth": self.is_rpc_authorized,
            "xsrf_cookies": True,
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

    def is_rpc_authorized(self, service, shard, method):
        return rpc_authorization_checker(self.auth_handler.admin_id,
                                         service, shard, method)

    def add_notification(self, timestamp, subject, text):
        """Store a new notification to send at the first
        opportunity (i.e., at the first request for db notifications).

        timestamp (datetime): the time of the notification.
        subject (string): subject of the notification.
        text (string): body of the notification.

        """
        self.notifications.append((timestamp, subject, text))
