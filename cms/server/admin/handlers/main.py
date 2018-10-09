#!/usr/bin/env python3

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

"""Non-categorized handlers for AWS.

"""

import json
import logging

from cms import ServiceCoord, get_service_shards, get_service_address
from cms.db import Admin, Contest, Question
from cmscommon.crypto import validate_password
from cmscommon.datetime import make_datetime, make_timestamp
from .base import BaseHandler, SimpleHandler, require_permission


logger = logging.getLogger(__name__)


class LoginHandler(SimpleHandler("login.html", authenticated=False)):
    """Login handler.

    """
    def post(self):
        error_args = {"login_error": "true"}
        next_page = self.get_argument("next", None)
        if next_page is not None:
            error_args["next"] = next_page
            if next_page != "/":
                next_page = self.url(*next_page.strip("/").split("/"))
            else:
                next_page = self.url()
        else:
            next_page = self.url()
        error_page = self.url("login", **error_args)

        username = self.get_argument("username", "")
        password = self.get_argument("password", "")
        admin = self.sql_session.query(Admin)\
            .filter(Admin.username == username)\
            .first()

        if admin is None:
            logger.warning("Nonexistent admin account: %s", username)
            self.redirect(error_page)
            return

        try:
            allowed = validate_password(admin.authentication, password)
        except ValueError:
            logger.warning("Unable to validate password for admin %r", username,
                           exc_info=True)
            allowed = False

        if not allowed or not admin.enabled:
            if not allowed:
                logger.info("Login error for admin %r from IP %s.", username,
                            self.request.remote_ip)
            elif not admin.enabled:
                logger.info("Login successful for admin %r from IP %s, but "
                            "account is disabled.", username,
                            self.request.remote_ip)
            self.redirect(error_page)
            return

        logger.info("Admin logged in: %r from IP %s.", username,
                    self.request.remote_ip)
        self.service.auth_handler.set(admin.id)
        self.redirect(next_page)


class LogoutHandler(BaseHandler):
    """Logout handler.

    """
    def post(self):
        self.service.auth_handler.clear()
        self.redirect(self.url())


class ResourcesHandler(BaseHandler):
    @require_permission(BaseHandler.AUTHENTICATED)
    def get(self, shard=None, contest_id=None):
        if contest_id is not None:
            self.contest = self.safe_get_item(Contest, contest_id)
            contest_address = [contest_id]
        else:
            contest_address = []

        if shard is None:
            shard = "all"

        self.r_params = self.render_params()
        self.r_params["resource_shards"] = \
            get_service_shards("ResourceService")
        self.r_params["resource_addresses"] = {}
        if shard == "all":
            for i in range(self.r_params["resource_shards"]):
                self.r_params["resource_addresses"][i] = get_service_address(
                    ServiceCoord("ResourceService", i)).ip
        else:
            shard = int(shard)
            try:
                address = get_service_address(
                    ServiceCoord("ResourceService", shard))
            except KeyError:
                self.redirect(self.url(*(["resourceslist"] + contest_address)))
                return
            self.r_params["resource_addresses"][shard] = address.ip

        self.render("resources.html", **self.r_params)


class NotificationsHandler(BaseHandler):
    """Displays notifications.

    """
    @require_permission(BaseHandler.AUTHENTICATED)
    def get(self):
        res = []
        last_notification = make_datetime(
            float(self.get_argument("last_notification", "0")))

        # Keep "== None" in filter arguments. SQLAlchemy does not
        # understand "is None".
        questions = self.sql_session.query(Question)\
            .filter(Question.reply_timestamp.is_(None))\
            .filter(Question.question_timestamp > last_notification)\
            .all()

        for question in questions:
            res.append({
                "type": "new_question",
                "timestamp": make_timestamp(question.question_timestamp),
                "subject": question.subject,
                "text": question.text,
                "contest_id": question.participation.contest_id
            })

        # Simple notifications
        for notification in self.service.notifications:
            res.append({"type": "notification",
                        "timestamp": make_timestamp(notification[0]),
                        "subject": notification[1],
                        "text": notification[2]})
        self.service.notifications = []

        self.write(json.dumps(res))
