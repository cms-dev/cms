#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2017 Tudor Nazarie <nazarietudor@gmail.com>
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

"""Handlers related to the signup interface
"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging
import datetime

import tornado.web

from cms.db import Participation, User, SessionGen, Contest, Team
from cmscommon.crypto import generate_random_password

from .base import BaseHandler

from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


def add_user(first_name, last_name, username, password, email, timezone=None,
             preferred_languages=None):
    if password is None:
        password = generate_random_password()
    if preferred_languages is None or preferred_languages == "":
        preferred_languages = "[]"
    else:
        preferred_languages = \
            "[" + ",".join("\"" + lang + "\""
                           for lang in preferred_languages.split(",")) + "]"

    user = User(
        first_name=first_name,
        last_name=last_name,
        username=username,
        password=password,
        email=email,
        timezone=timezone,
        preferred_languages=preferred_languages
    )

    try:
        with SessionGen() as session:
            session.add(user)
            session.commit()
    except IntegrityError:
        return False

    logger.info("Registered user {} with password {}".format(username,
                                                             password))
    return True


def add_participation(username, contest_id, ip=None, delay_time=None,
                      extra_time=None, password=None, team_code=None,
                      hidden=False, unrestricted=False):
    delay_time = delay_time if delay_time is not None else 0
    extra_time = extra_time if extra_time is not None else 0

    try:
        with SessionGen() as session:
            user = \
                session.query(User).filter(User.username == username).first()
            if user is None:
                return False
            contest = Contest.get_from_id(contest_id, session)
            if contest is None:
                return False
            team = None
            if team_code is not None:
                team = \
                    session.query(Team).filter(Team.code == team_code).first()
                if team is None:
                    return False
            participation = Participation(
                user=user,
                contest=contest,
                ip=ip,
                delay_time=datetime.timedelta(seconds=delay_time),
                extra_time=datetime.timedelta(seconds=extra_time),
                password=password,
                team=team,
                hidden=hidden,
                unrestricted=unrestricted
            )

            session.add(participation)
            session.commit()
    except IntegrityError:
        return False
    logger.info("Added participation for user {}".format(username))
    return True


class SignupHandler(BaseHandler):
    """Displays the signup interface
    """
    def get(self):
        participation = self.current_user

        if not self.contest.allow_signup:
            raise tornado.web.HTTPError(404)

        if participation is not None:
            self.redirect("/")
            return

        self.render("signup.html", **self.r_params)


class RegisterHandler(BaseHandler):
    """Register handler
    """
    def post(self):
        username = self.get_argument("username", "")
        first_name = self.get_argument("first_name", "")
        last_name = self.get_argument("last_name", "")
        email = self.get_argument("email", "")
        password = self.get_argument("password", "")
        confirm_password = self.get_argument("confirm_password", "")

        if not self.contest.allow_signup:
            raise tornado.web.HTTPError(404)

        if self.contest.phase(self.timestamp) != -1:
            self.redirect("/")
            return

        if password != confirm_password:
            self.redirect("/signup?password_no_match=true")
            return

        user = self.sql_session.query(User)\
            .filter(User.username == username)\
            .first()
        participation = self.sql_session.query(Participation)\
            .filter(Participation.contest == self.contest)\
            .filter(Participation.user == user)\
            .first()

        if user is not None and participation is not None:
            self.redirect("/signup?user_exists=true")
            return

        if user is None:
            add_user(
                first_name=first_name,
                last_name=last_name,
                username=username,
                password=password,
                email=email
            )
        add_participation(
            username=username,
            password=password,
            contest_id=self.contest.id
        )
        self.redirect("/?signup_successful=true")
        return
