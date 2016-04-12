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

"""Contest handler classes for CWS.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import logging
import pickle
import socket
import struct

from datetime import timedelta

from werkzeug.datastructures import LanguageAccept
from werkzeug.http import parse_accept_header

from cms import config
from cms.db import Contest, Participation, User
from cms.server import compute_actual_phase, file_handler_gen
from cms.locale import filter_language_codes
from cmscommon.datetime import get_timezone, make_datetime, make_timestamp

from .base import BaseHandler

logger = logging.getLogger(__name__)


NOTIFICATION_ERROR = "error"
NOTIFICATION_WARNING = "warning"
NOTIFICATION_SUCCESS = "success"


def check_ip(client, wanted):
    """Return if client IP belongs to the wanted subnet.

    client (string): IP address to verify.
    wanted (string): IP address or subnet to check against.

    return (bool): whether client equals wanted (if the latter is an IP
        address) or client belongs to wanted (if it's a subnet).

    """
    wanted, sep, subnet = wanted.partition('/')
    subnet = 32 if sep == "" else int(subnet)
    snmask = 2 ** 32 - 2 ** (32 - subnet)
    wanted = struct.unpack(">I", socket.inet_aton(wanted))[0]
    client = struct.unpack(">I", socket.inet_aton(client))[0]
    return (wanted & snmask) == (client & snmask)


class ContestHandler(BaseHandler):
    """A handler that has a contest attached.

    Most of the RequestHandler classes in this application will be a
    child of this class.
    """
    def prepare(self):
        super(ContestHandler, self).prepare()

        self.choose_contest()

    def choose_contest(self, contest_name=None):
        if self.application.service.contest is None:
            if contest_name is None:
                # Choose the contest found in the path argument
                # see: https://github.com/tornadoweb/tornado/issues/1673
                contest_name = self.path_args[0]

            # Select the correct contest or return an error
            try:
                self.contest = self.contest_list[contest_name]
            except KeyError:
                # The right thing here would be:
                #    raise tornado.web.HTTPError(404)
                # however, that would make the "error.html" page fail because
                # there is no self.contest available

                # So, let's return to the contest list
                self.redirect("/")
                return
        else:
            # Select the contest specified on the command line
            self.contest = Contest.get_from_id(self.application.service.contest,
                                               self.sql_session)

        # Run render_params() now, not at the beginning of the request,
        # because we need contest_name
        self.r_params = self.render_params()

    def render_params(self):
        ret = super(ContestHandler, self).render_params()

        ret["contest"] = self.contest
        ret["contest_root"] = ret["url_root"]
        ret["real_contest_root"] = "/"
        if self.application.service.contest is None:
            ret["contest_root"] += "/" + self.contest.name
            ret["real_contest_root"] += self.contest.name
        ret["phase"] = self.contest.phase(self.timestamp)

        ret["printing_enabled"] = (config.printer is not None)
        ret["questions_enabled"] = self.contest.allow_questions
        ret["testing_enabled"] = self.contest.allow_user_tests

        if self.current_user is not None:
            participation = self.current_user

            res = compute_actual_phase(
                self.timestamp, self.contest.start, self.contest.stop,
                self.contest.per_user_time, participation.starting_time,
                participation.delay_time, participation.extra_time)

            ret["actual_phase"], ret["current_phase_begin"], \
                ret["current_phase_end"], ret["valid_phase_begin"], \
                ret["valid_phase_end"] = res

            if ret["actual_phase"] == 0:
                ret["phase"] = 0

            # set the timezone used to format timestamps
            ret["timezone"] = get_timezone(participation.user, self.contest)

        # some information about token configuration
        ret["tokens_contest"] = self._get_token_status(self.contest)

        t_tokens = sum(self._get_token_status(t) for t in self.contest.tasks)
        if t_tokens == 0:
            ret["tokens_tasks"] = 0  # all disabled
        elif t_tokens == 2 * len(self.contest.tasks):
            ret["tokens_tasks"] = 2  # all infinite
        else:
            ret["tokens_tasks"] = 1  # all finite or mixed

        return ret

    def get_login_url(self):
        """The login url depends on the contest name, so we can't just
        use the "login_url" application parameter.

        """
        return "/" + self.contest.name

    def get_current_user(self):
        """The name is get_current_user because tornado wants it that
        way, but this is really a get_current_participation.

        Gets the current participation from cookies.

        If a valid cookie is retrieved, return a Participation tuple
        (specifically: the Participation involving the username
        specified in the cookie and the current contest).

        Otherwise (e.g. the user exists but doesn't participate in the
        current contest), return None.

        """
        cookie_name = self.contest.name + "_login"

        remote_ip = self.request.remote_ip
        if self.contest.ip_autologin:
            self.clear_cookie(cookie_name)
            participations = self.sql_session.query(Participation)\
                .filter(Participation.contest == self.contest)\
                .filter(Participation.ip == remote_ip)\
                .all()
            if len(participations) == 1:
                return participations[0]

            if len(participations) > 1:
                logger.error("Multiple users have IP %s." % (remote_ip))
            else:
                logger.error("No user has IP %s" % (remote_ip))

            # If IP autologin is set, we do not allow password logins.
            return None

        if self.get_secure_cookie(cookie_name) is None:
            return None

        # Parse cookie.
        try:
            cookie = pickle.loads(self.get_secure_cookie(cookie_name))
            username = cookie[0]
            password = cookie[1]
            last_update = make_datetime(cookie[2])
        except:
            self.clear_cookie(cookie_name)
            return None

        # Check if the cookie is expired.
        if self.timestamp - last_update > \
                timedelta(seconds=config.cookie_duration):
            self.clear_cookie(cookie_name)
            return None

        # Load user from DB.
        user = self.sql_session.query(User)\
            .filter(User.username == username)\
            .first()

        # Check if user exists.
        if user is None:
            self.clear_cookie(cookie_name)
            return None

        # Load participation from DB.
        participation = self.sql_session.query(Participation)\
            .filter(Participation.contest == self.contest)\
            .filter(Participation.user == user)\
            .first()

        # Check if participaton exists.
        if participation is None:
            self.clear_cookie(cookie_name)
            return None

        # If a contest-specific password is defined, use that. If it's
        # not, use the user's main password.
        if participation.password is None:
            correct_password = user.password
        else:
            correct_password = participation.password

        # Check if user is allowed to login.
        if password != correct_password:
            self.clear_cookie(cookie_name)
            return None

        # Check if user is using the right IP (or is on the right subnet)
        if self.contest.ip_restriction and participation.ip is not None \
                and not check_ip(self.request.remote_ip, participation.ip):
            self.clear_cookie(cookie_name)
            return None

        # Check if user is hidden
        if participation.hidden and self.contest.block_hidden_participations:
            self.clear_cookie(cookie_name)
            return None

        if self.refresh_cookie:
            self.set_secure_cookie(cookie_name,
                                   pickle.dumps((user.username,
                                                 password,
                                                 make_timestamp())),
                                   expires_days=None)

        return participation

    def get_user_locale(self):
        self.langs = self.application.service.langs
        lang_codes = self.langs.keys()

        if self.contest and len(self.contest.allowed_localizations) > 0:
            lang_codes = filter_language_codes(
                lang_codes, self.contest.allowed_localizations)

        # Select the one the user likes most.
        basic_lang = lang_codes[0].replace("_", "-") \
            if self.contest and len(self.contest.allowed_localizations) else 'en'
        http_langs = [lang_code.replace("_", "-") for lang_code in lang_codes]
        self.browser_lang = parse_accept_header(
            self.request.headers.get("Accept-Language", ""),
            LanguageAccept).best_match(http_langs, basic_lang)

        self.cookie_lang = self.get_cookie("language", None)

        if self.cookie_lang in http_langs:
            lang_code = self.cookie_lang
        else:
            lang_code = self.browser_lang

        self.set_header("Content-Language", lang_code)
        return self.langs[lang_code.replace("-", "_")]

    @staticmethod
    def _get_token_status(obj):
        """Return the status of the tokens for the given object.

        obj (Contest or Task): an object that has the token_* attributes.
        return (int): one of 0 (disabled), 1 (enabled/finite) and 2
                      (enabled/infinite).

        """
        if obj.token_mode == "disabled":
            return 0
        elif obj.token_mode == "finite":
            return 1
        elif obj.token_mode == "infinite":
            return 2
        else:
            raise RuntimeError("Unknown token_mode value.")


FileHandler = file_handler_gen(ContestHandler)
