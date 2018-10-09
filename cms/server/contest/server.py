#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2015 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2015 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""ContestWebServer serves the webpage that contestants are using to:

- view information about the contest (times, ...);
- view tasks;
- view documentation (STL, ...);
- submit questions;
- view announcements and answer to questions;
- submit solutions;
- view the state and maybe the score of their submissions;
- release submissions to see their full score;
- query the test interface.

"""

import logging

from werkzeug.wsgi import SharedDataMiddleware

from cms import ConfigError, ServiceCoord, config
from cms.io import WebService
from cms.locale import get_translations
from cms.server.contest.jinja2_toolbox import CWS_ENVIRONMENT
from cmscommon.binary import hex_to_bin
from .handlers import HANDLERS
from .handlers.base import ContestListHandler
from .handlers.main import MainHandler


logger = logging.getLogger(__name__)


SECONDS_IN_A_YEAR = 365 * 24 * 60 * 60


class ContestWebServer(WebService):
    """Service that runs the web server serving the contestants.

    """
    def __init__(self, shard, contest_id=None):
        parameters = {
            "static_files": [("cms.server", "static"),
                             ("cms.server.contest", "static")],
            "cookie_secret": hex_to_bin(config.secret_key),
            "debug": config.tornado_debug,
            "is_proxy_used": config.is_proxy_used,
            "num_proxies_used": config.num_proxies_used,
            "xsrf_cookies": True,
        }

        try:
            listen_address = config.contest_listen_address[shard]
            listen_port = config.contest_listen_port[shard]
        except IndexError:
            raise ConfigError("Wrong shard number for %s, or missing "
                              "address/port configuration. Please check "
                              "contest_listen_address and contest_listen_port "
                              "in cms.conf." % __name__)

        self.contest_id = contest_id

        if self.contest_id is None:
            HANDLERS.append((r"", MainHandler))
            handlers = [(r'/', ContestListHandler)]
            for h in HANDLERS:
                handlers.append((r'/([^/]+)' + h[0],) + h[1:])
        else:
            HANDLERS.append((r"/", MainHandler))
            handlers = HANDLERS

        super().__init__(
            listen_port,
            handlers,
            parameters,
            shard=shard,
            listen_address=listen_address)

        self.wsgi_app = SharedDataMiddleware(
            self.wsgi_app, {"/stl": config.stl_path},
            cache=True, cache_timeout=SECONDS_IN_A_YEAR,
            fallback_mimetype="application/octet-stream")

        self.jinja2_environment = CWS_ENVIRONMENT

        # This is a dictionary (indexed by username) of pending
        # notification. Things like "Yay, your submission went
        # through.", not things like "Your question has been replied",
        # that are handled by the db. Each username points to a list
        # of tuples (timestamp, subject, text).
        self.notifications = {}

        # Retrieve the available translations.
        self.translations = get_translations()

        self.evaluation_service = self.connect_to(
            ServiceCoord("EvaluationService", 0))
        self.scoring_service = self.connect_to(
            ServiceCoord("ScoringService", 0))

        ranking_enabled = len(config.rankings) > 0
        self.proxy_service = self.connect_to(
            ServiceCoord("ProxyService", 0),
            must_be_present=ranking_enabled)

        printing_enabled = config.printer is not None
        self.printing_service = self.connect_to(
            ServiceCoord("PrintingService", 0),
            must_be_present=printing_enabled)

    def add_notification(self, username, timestamp, subject, text, level):
        """Store a new notification to send to a user at the first
        opportunity (i.e., at the first request fot db notifications).

        username (string): the user to notify.
        timestamp (datetime): the time of the notification.
        subject (string): subject of the notification.
        text (string): body of the notification.
        level (string): one of NOTIFICATION_* (defined above)

        """
        if username not in self.notifications:
            self.notifications[username] = []
        self.notifications[username].append((timestamp, subject, text, level))
