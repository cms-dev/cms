#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2013 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2015 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2014 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2015 William Di Luigi <williamdiluigi@gmail.com>
# Copyright © 2016 Myungwoo Chun <mc.tamaki@gmail.com>
# Copyright © 2016 Peyman Jabbarzade Ganje <peyman.jabarzade@gmail.com>
# Copyright © 2017 Valentin Rosca <rosca.valentin2012@gmail.com>
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

"""User-related handlers for AWS for a specific contest.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging

import tornado.web

from cms.db import Contest, Message, Participation, Submission, User, Team
from cmscommon.datetime import make_datetime
from cmscommon.crypto import parse_authentication, hash_password

from .base import BaseHandler, require_permission


logger = logging.getLogger(__name__)


class ContestUsersHandler(BaseHandler):
    REMOVE_FROM_CONTEST = "Remove from contest"

    @require_permission(BaseHandler.AUTHENTICATED)
    def get(self, contest_id):
        self.contest = self.safe_get_item(Contest, contest_id)

        self.r_params = self.render_params()
        self.r_params["contest"] = self.contest
        self.r_params["unassigned_users"] = \
            self.sql_session.query(User)\
                .filter(User.id.notin_(
                    self.sql_session.query(Participation.user_id)
                        .filter(Participation.contest == self.contest)
                        .all()))\
                .all()
        self.render("contest_users.html", **self.r_params)

    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, contest_id):
        fallback_page = "/contest/%s/users" % contest_id

        try:
            user_id = self.get_argument("user_id")
            operation = self.get_argument("operation")
            assert operation in (
                self.REMOVE_FROM_CONTEST,
            ), "Please select a valid operation"
        except Exception as error:
            self.application.service.add_notification(
                make_datetime(), "Invalid field(s)", repr(error))
            self.redirect(fallback_page)
            return

        if operation == self.REMOVE_FROM_CONTEST:
            asking_page = "/contest/%s/user/%s/remove" % (contest_id, user_id)
            # Open asking for remove page
            self.redirect(asking_page)
            return

        self.redirect(fallback_page)


class RemoveParticipationHandler(BaseHandler):
    """Get returns a page asking for confirmation, delete actually removes
    the participation from the contest.

    """

    @require_permission(BaseHandler.PERMISSION_ALL)
    def get(self, contest_id, user_id):
        self.contest = self.safe_get_item(Contest, contest_id)
        user = self.safe_get_item(User, user_id)
        participation = self.sql_session.query(Participation)\
                            .filter(Participation.contest_id == contest_id)\
                            .filter(Participation.user_id == user_id)\
                            .first()
        # Check that the participation is valid.
        if participation is None:
            raise tornado.web.HTTPError(404)

        submission_query = self.sql_session.query(Submission)\
            .filter(Submission.participation == participation)
        self.render_params_for_remove_confirmation(submission_query)

        self.r_params["user"] = user
        self.r_params["contest"] = self.contest
        self.render("participation_remove.html", **self.r_params)

    @require_permission(BaseHandler.PERMISSION_ALL)
    def delete(self, contest_id, user_id):
        self.contest = self.safe_get_item(Contest, contest_id)
        user = self.safe_get_item(User, user_id)

        participation = self.sql_session.query(Participation)\
            .filter(Participation.user == user)\
            .filter(Participation.contest == self.contest)\
            .first()

        # Unassign the user from the contest.
        self.sql_session.delete(participation)

        if self.try_commit():
            # Remove the participation on RWS.
            self.application.service.proxy_service.reinitialize()

        # Maybe they'll want to do this again (for another participation)
        self.write("../../users")


class AddContestUserHandler(BaseHandler):
    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, contest_id):
        fallback_page = "/contest/%s/users" % contest_id

        self.contest = self.safe_get_item(Contest, contest_id)

        try:
            user_id = self.get_argument("user_id")
            assert user_id != "null", "Please select a valid user"
        except Exception as error:
            self.application.service.add_notification(
                make_datetime(), "Invalid field(s)", repr(error))
            self.redirect(fallback_page)
            return

        user = self.safe_get_item(User, user_id)

        # Create the participation.
        participation = Participation(contest=self.contest, user=user)
        self.sql_session.add(participation)

        if self.try_commit():
            # Create the user on RWS.
            self.application.service.proxy_service.reinitialize()

        # Maybe they'll want to do this again (for another user)
        self.redirect(fallback_page)


class ParticipationHandler(BaseHandler):
    """Shows the details of a single user in a contest: submissions,
    questions, messages (and allows to send the latters).

    """
    @require_permission(BaseHandler.AUTHENTICATED)
    def get(self, contest_id, user_id):
        participation = self.get_participation(contest_id, user_id)

        # Check that the participation is valid.
        if participation is None:
            raise tornado.web.HTTPError(404)

        submission_query = self.sql_session.query(Submission)\
            .filter(Submission.participation == participation)
        page = int(self.get_query_argument("page", 0))
        self.render_params_for_submissions(submission_query, page)

        if participation.password is not None:
            method, payload = parse_authentication(participation.password)
            participation.method = method
            if method == 'text':
                participation.password = payload
            else:
                participation.password = ""
        else:
            participation.method = "text"
            participation.password = ""

        self.r_params["participation"] = participation
        self.r_params["selected_user"] = participation.user
        self.r_params["teams"] = self.sql_session.query(Team).all()
        self.render("participation.html", **self.r_params)

    def get_participation(self, contest_id, user_id):
        """Sets the contest of the current object and return
        the participation of the user in the contest with
        the specified id.

        contest_id (int): Id of the contest
        user_id (int): Id of the user in the contest

        return (participation): participation type object representing
        the participation of the user in the contest
        """
        self.contest = self.safe_get_item(Contest, contest_id)
        participation = self.sql_session.query(Participation) \
            .filter(Participation.contest_id == contest_id) \
            .filter(Participation.user_id == user_id) \
            .first()
        return participation

    @require_permission(BaseHandler.PERMISSION_ALL)
    def post(self, contest_id, user_id):
        fallback_page = "/contest/%s/user/%s/edit" % (contest_id, user_id)

        participation = self.get_participation(contest_id, user_id)

        # Check that the participation is valid.
        if participation is None:
            raise tornado.web.HTTPError(404)

        try:
            attrs = participation.get_attrs()

            self.get_string(attrs, "password", empty=None)
            self.get_string(attrs, "method", empty="text")
            if "method" not in attrs:
                attrs["method"] = "text"
            method = attrs["method"]
            password = attrs["password"]
            if password is not None:
                attrs["password"] = hash_password(password, method)
            elif method != "text":
                # Preserve old password if password is empty
                # and method is not text
                attrs["password"] = participation.password

            del attrs["method"]

            self.get_ip_address_or_subnet(attrs, "ip")
            self.get_datetime(attrs, "starting_time")
            self.get_timedelta_sec(attrs, "delay_time")
            self.get_timedelta_sec(attrs, "extra_time")
            self.get_bool(attrs, "hidden")
            self.get_bool(attrs, "unrestricted")

            # Update the participation.
            participation.set_attrs(attrs)

            # Update the team
            self.get_string(attrs, "team")
            team = self.sql_session.query(Team)\
                       .filter(Team.code == attrs["team"])\
                       .first()
            participation.team = team

        except Exception as error:
            self.application.service.add_notification(
                make_datetime(), "Invalid field(s)", repr(error))
            self.redirect(fallback_page)
            return

        if self.try_commit():
            # Update the user on RWS.
            self.application.service.proxy_service.reinitialize()
        self.redirect(fallback_page)


class MessageHandler(BaseHandler):
    """Called when a message is sent to a specific user.

    """

    @require_permission(BaseHandler.PERMISSION_MESSAGING)
    def post(self, contest_id, user_id):
        user = self.safe_get_item(User, user_id)
        self.contest = self.safe_get_item(Contest, contest_id)
        participation = self.sql_session.query(Participation)\
            .filter(Participation.contest == self.contest)\
            .filter(Participation.user == user)\
            .first()

        # check that the participation is valid
        if participation is None:
            raise tornado.web.HTTPError(404)

        message = Message(make_datetime(),
                          self.get_argument("message_subject", ""),
                          self.get_argument("message_text", ""),
                          participation=participation)
        self.sql_session.add(message)
        if self.try_commit():
            logger.info("Message submitted to user %s in contest %s.",
                        user.username, self.contest.name)

        self.redirect("/contest/%s/user/%s/edit" % (self.contest.id, user.id))
