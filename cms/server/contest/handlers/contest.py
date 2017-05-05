#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2016 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2017 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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

"""Contest handler classes for CWS.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import ipaddress
import logging
import pickle

from datetime import timedelta

import tornado.web

from sqlalchemy.orm import contains_eager
from werkzeug.datastructures import LanguageAccept
from werkzeug.http import parse_accept_header

from cms import config
from cms.db import Contest, Participation, User
from cms.server import compute_actual_phase, file_handler_gen, \
    create_url_builder
from cms.locale import filter_language_codes
from cmscommon.datetime import get_timezone, make_datetime, make_timestamp
from cmscommon.isocodes import translate_language_code, \
    translate_language_country_code

from .base import BaseHandler


logger = logging.getLogger(__name__)


NOTIFICATION_ERROR = "error"
NOTIFICATION_WARNING = "warning"
NOTIFICATION_SUCCESS = "success"


def check_ip(address, networks):
    """Return if client IP belongs to one of the accepted networks.

    address (bytes): IP address to verify.
    networks ([ipaddress.IPv4Network|ipaddress.IPv6Network]): IP
        networks (addresses w/ subnets) to check against.

    return (bool): whether the address belongs to one of the networks.

    """
    try:
        address = ipaddress.ip_address(unicode(address))
    except ValueError:
        return False

    for network in networks:
        if address in network:
            return True

    return False


class ContestHandler(BaseHandler):
    """A handler that has a contest attached.

    Most of the RequestHandler classes in this application will be a
    child of this class.

    """
    def prepare(self):
        super(ContestHandler, self).prepare()
        self.choose_contest()

        if self.is_multi_contest():
            self.contest_url = \
                create_url_builder(self.url(self.contest.name))
        else:
            self.contest_url = self.url

        # Run render_params() now, not at the beginning of the request,
        # because we need contest_name
        self.r_params = self.render_params()

    def choose_contest(self):
        """Fill self.contest using contest passed as argument or path.

        If a contest was specified as argument to CWS, fill
        self.contest with that; otherwise extract it from the URL path.

        """
        if self.is_multi_contest():
            # Choose the contest found in the path argument
            # see: https://github.com/tornadoweb/tornado/issues/1673
            contest_name = self.path_args[0]

            # Select the correct contest or return an error
            try:
                self.contest = self.contest_list[contest_name]
            except KeyError:
                self.contest = Contest(
                    name=contest_name, description=contest_name)
                self.r_params = self.render_params()
                raise tornado.web.HTTPError(404)
        else:
            # Select the contest specified on the command line
            self.contest = Contest.get_from_id(
                self.application.service.contest_id, self.sql_session)

    def get_current_user(self):
        """Return the currently logged in participation.

        The name is get_current_user because tornado requires that
        name.

        The participation is obtained from one of the possible sources:
        - if IP autologin is enabled, the remote IP address is matched
          with the participation IP address; if a match is found, that
          participation is returned; in case of errors, None is returned;
        - if username/password authentication is enabled, and the cookie
          is valid, the corresponding participation is returned, and the
          cookie is refreshed.

        After finding the participation, IP login and hidden users
        restrictions are checked.

        In case of any error, or of a login by other sources, the
        cookie is deleted.

        return (Participation|None): the participation object for the
            user logged in for the running contest.

        """
        cookie_name = self.contest.name + "_login"

        participation = None

        if self.contest.ip_autologin:
            try:
                participation = self._get_current_user_from_ip()
                # If the login is IP-based, we delete previous cookies.
                if participation is not None:
                    self.clear_cookie(cookie_name)
            except RuntimeError:
                return None

        if participation is None \
                and self.contest.allow_password_authentication:
            participation = self._get_current_user_from_cookie()

        if participation is None:
            self.clear_cookie(cookie_name)
            return None

        # Check if user is using the right IP (or is on the right subnet),
        # and that is not hidden if hidden users are blocked.
        ip_login_restricted = \
            self.contest.ip_restriction and participation.ip is not None \
            and not check_ip(self.request.remote_ip, participation.ip)
        hidden_user_restricted = \
            participation.hidden and self.contest.block_hidden_participations
        if ip_login_restricted or hidden_user_restricted:
            self.clear_cookie(cookie_name)
            participation = None

        return participation

    def _get_current_user_from_ip(self):
        """Return the current participation based on the IP address.

        return (Participation|None): the only participation matching
            the remote IP address, or None if no participations could
            be matched.

        raise (RuntimeError): if there is more than one participation
            matching the remote IP address.

        """
        try:
            # We encode it as a network (i.e., we assign it a /32 or
            # /128 mask) since we're comparing it for equality with
            # other networks.
            remote_ip = ipaddress.ip_network(unicode(self.request.remote_ip))
        except ValueError:
            return None
        participations = self.sql_session.query(Participation)\
            .filter(Participation.contest == self.contest)\
            .filter(Participation.ip.any(remote_ip))

        # If hidden users are blocked we ignore them completely.
        if self.contest.block_hidden_participations:
            participations = participations\
                .filter(Participation.hidden.is_(False))

        participations = participations.all()

        if len(participations) == 1:
            return participations[0]

        # Having more than participation with the same IP,
        # is a mistake and should not happen. In such case,
        # we disallow login for that IP completely, in order to
        # make sure the problem is noticed.
        if len(participations) > 1:
            logger.error("%d participants have IP %s while"
                         "auto-login feature is enabled." % (
                             len(participations), remote_ip))
            raise RuntimeError("More than one participants with the same IP.")

    def _get_current_user_from_cookie(self):
        """Return the current participation based on the cookie.

        If a participation can be extracted, the cookie is refreshed.

        return (Participation|None): the participation extracted from
            the cookie, or None if not possible.

        """
        cookie_name = self.contest.name + "_login"

        if self.get_secure_cookie(cookie_name) is None:
            return None

        # Parse cookie.
        try:
            cookie = pickle.loads(self.get_secure_cookie(cookie_name))
            username = cookie[0]
            password = cookie[1]
            last_update = make_datetime(cookie[2])
        except:
            return None

        # Check if the cookie is expired.
        if self.timestamp - last_update > \
                timedelta(seconds=config.cookie_duration):
            return None

        # Load participation from DB and make sure it exists.
        participation = self.sql_session.query(Participation)\
            .join(Participation.user)\
            .options(contains_eager(Participation.user))\
            .filter(Participation.contest == self.contest)\
            .filter(User.username == username)\
            .first()
        if participation is None:
            return None

        # Check that the password is correct (if a contest-specific
        # password is defined, use that instead of the user password).
        if participation.password is None:
            correct_password = participation.user.password
        else:
            correct_password = participation.password
        if password != correct_password:
            return None

        if self.refresh_cookie:
            self.set_secure_cookie(cookie_name,
                                   pickle.dumps((username,
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
        basic_lang = 'en'

        if self.contest and len(self.contest.allowed_localizations):
            basic_lang = lang_codes[0].replace("_", "-")

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

    def render_params(self):
        ret = super(ContestHandler, self).render_params()

        ret["contest"] = self.contest

        if hasattr(self, "contest_url"):
            ret["contest_url"] = self.contest_url

        ret["phase"] = self.contest.phase(self.timestamp)

        ret["printing_enabled"] = (config.printer is not None)
        ret["questions_enabled"] = self.contest.allow_questions
        ret["testing_enabled"] = self.contest.allow_user_tests

        if self.current_user is not None:
            participation = self.current_user

            res = compute_actual_phase(
                self.timestamp, self.contest.start, self.contest.stop,
                self.contest.analysis_start if self.contest.analysis_enabled
                else None,
                self.contest.analysis_stop if self.contest.analysis_enabled
                else None,
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

        # TODO Now all language names are shown in the active language.
        # It would be better to show them in the corresponding one.
        ret["lang_names"] = {}

        # Get language codes for allowed localizations
        lang_codes = self.langs.keys()
        if len(self.contest.allowed_localizations) > 0:
            lang_codes = filter_language_codes(
                lang_codes, self.contest.allowed_localizations)
        for lang_code, trans in self.langs.iteritems():
            language_name = None
            # Filter lang_codes with allowed localizations
            if lang_code not in lang_codes:
                continue
            try:
                language_name = translate_language_country_code(
                    lang_code, trans)
            except ValueError:
                language_name = translate_language_code(
                    lang_code, trans)
            ret["lang_names"][lang_code.replace("_", "-")] = language_name

        ret["cookie_lang"] = self.cookie_lang
        ret["browser_lang"] = self.browser_lang

        return ret

    def get_login_url(self):
        """The login url depends on the contest name, so we can't just
        use the "login_url" application parameter.

        """
        return self.contest_url()


FileHandler = file_handler_gen(ContestHandler)
