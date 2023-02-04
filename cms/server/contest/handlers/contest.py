#!/usr/bin/env python3

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

import ipaddress
import logging

try:
    import tornado4.web as tornado_web
except ImportError:
    import tornado.web as tornado_web

from cms import config, TOKEN_MODE_MIXED
from cms.db import Contest, Submission, Task, UserTest
from cms.locale import filter_language_codes
from cms.server import FileHandlerMixin
from cms.server.contest.authentication import authenticate_request
from cmscommon.datetime import get_timezone
from .base import BaseHandler
from ..phase_management import compute_actual_phase


logger = logging.getLogger(__name__)


NOTIFICATION_ERROR = "error"
NOTIFICATION_WARNING = "warning"
NOTIFICATION_SUCCESS = "success"


class ContestHandler(BaseHandler):
    """A handler that has a contest attached.

    Most of the RequestHandler classes in this application will be a
    child of this class.

    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.contest_url = None

    def prepare(self):
        self.choose_contest()

        if self.contest.allowed_localizations:
            lang_codes = filter_language_codes(
                list(self.available_translations.keys()),
                self.contest.allowed_localizations)
            self.available_translations = dict(
                (k, v) for k, v in self.available_translations.items()
                if k in lang_codes)

        super().prepare()

        if self.is_multi_contest():
            self.contest_url = self.url[self.contest.name]
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
            self.contest = self.sql_session.query(Contest)\
                .filter(Contest.name == contest_name).first()
            if self.contest is None:
                self.contest = Contest(
                    name=contest_name, description=contest_name)
                # render_params in this class assumes the contest is loaded,
                # so we cannot call it without a fully defined contest. Luckily
                # the one from the base class is enough to display a 404 page.
                super().prepare()
                self.r_params = super().render_params()
                raise tornado_web.HTTPError(404)
        else:
            # Select the contest specified on the command line
            self.contest = Contest.get_from_id(
                self.service.contest_id, self.sql_session)

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
        cookie = self.get_secure_cookie(cookie_name)

        try:
            ip_address = ipaddress.ip_address(self.request.remote_ip)
        except ValueError:
            logger.warning("Invalid IP address provided by Tornado: %s",
                           self.request.remote_ip)
            return None

        participation, cookie = authenticate_request(
            self.sql_session, self.contest, self.timestamp, cookie, ip_address)

        if cookie is None:
            self.clear_cookie(cookie_name)
        elif self.refresh_cookie:
            self.set_secure_cookie(cookie_name, cookie, expires_days=None)

        return participation

    def render_params(self):
        ret = super().render_params()

        ret["contest"] = self.contest

        if self.contest_url is not None:
            ret["contest_url"] = self.contest_url

        ret["phase"] = self.contest.phase(self.timestamp)

        ret["printing_enabled"] = (config.printer is not None)
        ret["questions_enabled"] = self.contest.allow_questions
        ret["testing_enabled"] = self.contest.allow_user_tests

        if self.current_user is not None:
            participation = self.current_user
            ret["participation"] = participation
            ret["user"] = participation.user

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
        ret["tokens_contest"] = self.contest.token_mode

        t_tokens = set(t.token_mode for t in self.contest.tasks)
        if len(t_tokens) == 1:
            ret["tokens_tasks"] = next(iter(t_tokens))
        else:
            ret["tokens_tasks"] = TOKEN_MODE_MIXED

        return ret

    def get_login_url(self):
        """The login url depends on the contest name, so we can't just
        use the "login_url" application parameter.

        """
        return self.contest_url()

    def get_task(self, task_name):
        """Return the task in the contest with the given name.

        task_name (str): the name of the task we are interested in.

        return (Task|None): the corresponding task object, if found.

        """
        return self.sql_session.query(Task) \
            .filter(Task.contest == self.contest) \
            .filter(Task.name == task_name) \
            .one_or_none()

    def get_submission(self, task, submission_num):
        """Return the num-th contestant's submission on the given task.

        task (Task): a task for the contest that is being served.
        submission_num (str): a positive number, in decimal encoding.

        return (Submission|None): the submission_num-th submission
            (1-based), in chronological order, that was sent by the
            currently logged in contestant on the given task (None if
            not found).

        """
        return self.sql_session.query(Submission) \
            .filter(Submission.participation == self.current_user) \
            .filter(Submission.task == task) \
            .order_by(Submission.timestamp) \
            .offset(int(submission_num) - 1) \
            .first()

    def get_user_test(self, task, user_test_num):
        """Return the num-th contestant's test on the given task.

        task (Task): a task for the contest that is being served.
        user_test_num (str): a positive number, in decimal encoding.

        return (UserTest|None): the user_test_num-th user test, in
            chronological order, that was sent by the currently logged
            in contestant on the given task (None if not found).

        """
        return self.sql_session.query(UserTest) \
            .filter(UserTest.participation == self.current_user) \
            .filter(UserTest.task == task) \
            .order_by(UserTest.timestamp) \
            .offset(int(user_test_num) - 1) \
            .first()

    def add_notification(self, subject, text, level, text_params=None):
        subject = self._(subject)
        text = self._(text)
        if text_params is not None:
            text %= text_params
        self.service.add_notification(self.current_user.user.username,
                                      self.timestamp, subject, text, level)

    def notify_success(self, subject, text, text_params=None):
        self.add_notification(subject, text, NOTIFICATION_SUCCESS, text_params)

    def notify_warning(self, subject, text, text_params=None):
        self.add_notification(subject, text, NOTIFICATION_WARNING, text_params)

    def notify_error(self, subject, text, text_params=None):
        self.add_notification(subject, text, NOTIFICATION_ERROR, text_params)


class FileHandler(ContestHandler, FileHandlerMixin):
    pass
