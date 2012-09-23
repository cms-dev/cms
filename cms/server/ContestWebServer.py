#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2012 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2012 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012 Luca Wehrstedt <luca.wehrstedt@gmail.com>
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
- query the test interface (to be implemented?).

"""

import os
import re
import pickle
import codecs

import base64
import simplejson as json
import tempfile
import traceback
from datetime import timedelta
from urllib import quote
import gettext

import tornado.web

from sqlalchemy import func

from cms import config, default_argument_parser, logger
from cms.async.WebAsyncLibrary import WebService
from cms.async import ServiceCoord
from cms.db import ask_for_contest
from cms.db.FileCacher import FileCacher
from cms.db.SQLAlchemyAll import Session, Contest, User, Task, \
     Question, Submission, Token, File, UserTest, UserTestFile, \
     UserTestManager
from cms.grading.tasktypes import get_task_type
from cms.grading.scoretypes import get_score_type
from cms.server import file_handler_gen, extract_archive, \
     actual_phase_required, get_url_root, filter_ascii, \
     CommonRequestHandler
from cmscommon import ISOCodes
from cmscommon.Cryptographics import encrypt_number
from cmscommon.DateTime import make_datetime, make_timestamp, get_timezone
from cmscommon.MimeTypes import get_type_for_file_name


class BaseHandler(CommonRequestHandler):
    """Base RequestHandler for this application.

    All the RequestHandler classes in this application should be a
    child of this class.

    """

    # Whether the login cookie duration has to be refreshed when
    # this handler is called. Useful to filter asynchronous
    # requests.
    refresh_cookie = True

    def prepare(self):
        """This method is executed at the beginning of each request.

        """
        self.timestamp = make_datetime()

        self.set_header("Cache-Control", "no-cache, must-revalidate")

        self.sql_session = Session()
        self.contest = Contest.get_from_id(self.application.service.contest,
                                           self.sql_session)

        self._ = self.locale.translate

        self.r_params = self.render_params()

    def get_current_user(self):
        """Gets the current user logged in from the cookies

        If a valid cookie is retrieved, return a User object with the
        username specified in the cookie. Otherwise, return None.

        """
        if self.get_secure_cookie("login") is None:
            return None
        try:
            cookie = pickle.loads(self.get_secure_cookie("login"))
            username = str(cookie[0])
            last_update = make_datetime(cookie[1])
        except:
            self.clear_cookie("login")
            return None

        # Check if the cookie is expired.
        if self.timestamp - last_update > timedelta(seconds=config.cookie_duration):
            self.clear_cookie("login")
            return None

        user = self.sql_session.query(User)\
            .filter(User.contest == self.contest)\
            .filter(User.username == username).first()
        if user is None:
            self.clear_cookie("login")
            return None

        if self.refresh_cookie:
            self.set_secure_cookie("login",
                               pickle.dumps((user.username, make_timestamp())),
                               expires_days=None)

        return user

    def get_user_locale(self):
        if config.installed:
            localization_dir = os.path.join("/", "usr", "local", "share", "locale")
        else:
            localization_dir = os.path.join(os.path.dirname(__file__), "mo")

        if self.current_user is not None:
            iso_639_locale = gettext.translation(
                "iso_639",
                os.path.join(config.iso_codes_prefix, "share", "locale"),
                ['en_US'],
                fallback=True)
            iso_3166_locale = gettext.translation(
                "iso_3166",
                os.path.join(config.iso_codes_prefix, "share", "locale"),
                ['en_US'],
                fallback=True)
            shared_mime_info_locale = gettext.translation(
                "shared-mime-info",
                os.path.join(config.shared_mime_info_prefix, "share", "locale"),
                ['en_US'],
                fallback=True)
            cms_locale = gettext.translation(
                "cms",
                localization_dir,
                ['en_US'],
                fallback=True)
            cms_locale.add_fallback(iso_639_locale)
            cms_locale.add_fallback(iso_3166_locale)
            cms_locale.add_fallback(shared_mime_info_locale)
        else:
            cms_locale = gettext.NullTranslations()

        # Add translate method to simulate tornado.Locale's interface
        def translate (message, plural_message=None, count=None):
            if plural_message is not None:
                assert count is not None
                return cms_locale.ungettext(message, plural_message, count)
            else:
                return cms_locale.ugettext(message)
        cms_locale.translate = translate

        return cms_locale

    @staticmethod
    def _get_token_status (obj):
        """Return the status of the tokens for the given object.

        obj (Contest or Task): an object that has the token_* attributes.
        return (int): one of 0 (disabled), 1 (enabled/finite) and 2
                      (enabled/infinite).

        """
        if obj.token_initial is None:
            return 0
        elif obj.token_gen_number and not obj.token_gen_time:
            return 2
        else:
            return 1

    def render_params(self):
        """Return the default render params used by almost all handlers.

        return (dict): default render params

        """
        ret = {}
        ret["timestamp"] = self.timestamp
        ret["contest"] = self.contest
        ret["url_root"] = get_url_root(self.request.path)
        ret["cookie"] = str(self.cookies)  # FIXME really needed?

        ret["phase"] = self.contest.phase(self.timestamp)

        if self.current_user is not None:
            # "adjust" the phase, considering the per_user_time
            ret["actual_phase"] = 2 * ret["phase"]

            if ret["phase"] == -1:
                # pre-contest phase
                ret["current_phase_begin"] = None
                ret["current_phase_end"] = self.contest.start
            elif ret["phase"] == 0:
                # contest phase
                if self.contest.per_user_time is None:
                    # "traditional" contest: every user can compete for
                    # the whole contest time
                    ret["current_phase_begin"] = self.contest.start
                    ret["current_phase_end"] = self.contest.stop
                else:
                    # "USACO-like" contest: every user can compete only
                    # for a limited time frame during the contest time
                    if self.current_user.starting_time is None:
                        ret["actual_phase"] = -1
                        ret["current_phase_begin"] = self.contest.start
                        ret["current_phase_end"] = self.contest.stop
                    else:
                        user_end_time = min(
                            self.current_user.starting_time + self.contest.per_user_time,
                            self.contest.stop)
                        if self.timestamp <= user_end_time:
                            ret["current_phase_begin"] = self.current_user.starting_time
                            ret["current_phase_end"] = user_end_time
                        else:
                            ret["actual_phase"] = +1
                            ret["current_phase_begin"] = user_end_time
                            ret["current_phase_end"] = self.contest.stop
            else:  # ret["phase"] == 1
                # post-contest phase
                ret["current_phase_begin"] = self.contest.stop
                ret["current_phase_end"] = None

            # compute valid_phase_begin and valid_phase_end (that is,
            # the time at which actual_phase started/will start and
            # stopped/will stop begin zero, or None if unknown).
            ret["valid_phase_begin"] = None
            ret["valid_phase_end"] = None
            if self.contest.per_user_time is None:
                ret["valid_phase_begin"] = self.contest.start
                ret["valid_phase_end"] = self.contest.stop
            elif self.current_user.starting_time is not None:
                ret["valid_phase_begin"] = self.current_user.starting_time
                ret["valid_phase_end"] = min(
                    self.current_user.starting_time + self.contest.per_user_time,
                    self.contest.stop)

            # consider the extra time
            if ret["valid_phase_end"] is not None:
                ret["valid_phase_end"] += self.current_user.extra_time
                if ret["valid_phase_begin"] <= self.timestamp <= ret["valid_phase_end"]:
                    ret["phase"] = 0
                    ret["actual_phase"] = 0
                    ret["current_phase_begin"] = ret["valid_phase_begin"]
                    ret["current_phase_end"] = ret["valid_phase_end"]

            # set the timezone used to format timestamps
            ret["timezone"] = get_timezone(self.current_user, self.contest)

        # some information about token configuration
        ret["tokens_contest"] = self._get_token_status(self.contest)
        if ret["tokens_contest"] == 2 and not self.contest.token_min_interval:
            ret["tokens_contest"] = 3  # infinite and no min_interval

        t_tokens = sum(self._get_token_status(t) for t in self.contest.tasks)
        if t_tokens == 0:
            ret["tokens_tasks"] = 0  # all disabled
        elif t_tokens == 2 * len(self.contest.tasks):
            ret["tokens_tasks"] = 2  # all infinite
        else:
            ret["tokens_tasks"] = 1  # all finite or mixed
        if ret["tokens_tasks"] == 2 and \
            all(t.token_min_interval <= self.contest.token_min_interval for t in self.contest.tasks):
            ret["tokens_tasks"] = 3  # all infinite and no min_intervals

        return ret

    def finish(self, *args, **kwds):
        """ Finishes this response, ending the HTTP request.

        We override this method in order to properly close the database.

        """
        if hasattr(self, "sql_session"):
            try:
                self.sql_session.close()
            except Exception as error:
                logger.warning("Couldn't close SQL connection: %r" % error)
        try:
            tornado.web.RequestHandler.finish(self, *args, **kwds)
        except IOError:
            # When the client closes the connection before we reply,
            # Tornado raises an IOError exception, that would pollute
            # our log with unnecessarily critical messages
            logger.debug("Connection closed before our reply.")

    def write_error(self, status_code, **kwargs):
        if "exc_info" in kwargs and \
                kwargs["exc_info"][0] != tornado.web.HTTPError:
            exc_info = kwargs["exc_info"]
            logger.critical(
                "Uncaught exception (%r) while processing a request: %s" %
                (exc_info[1], ''.join(traceback.format_exception(*exc_info))))

        # We assume that if r_params is defined then we have at least
        # the data we need to display a basic template with the error
        # information. If r_params is not defined (i.e. something went
        # *really* bad) we simply return a basic textual error notice.
        if hasattr(self, 'r_params'):
            self.render("error.html", status_code=status_code, **self.r_params)
        else:
            self.write("A critical error has occurred :-(")
            self.finish()


FileHandler = file_handler_gen(BaseHandler)


class ContestWebServer(WebService):
    """Service that runs the web server serving the contestants.

    """
    def __init__(self, shard, contest):
        logger.initialize(ServiceCoord("ContestWebServer", shard))
        self.contest = contest

        # This is a dictionary (indexed by username) of pending
        # notification. Things like "Yay, your submission went
        # through.", not things like "Your question has been replied",
        # that are handled by the db. Each username points to a list
        # of tuples (timestamp, subject, text).
        self.notifications = {}

        parameters = {
            "login_url": "/",
            "template_path": os.path.join(os.path.dirname(__file__),
                                          "templates", "contest"),
            "static_path": os.path.join(os.path.dirname(__file__),
                                        "static"),
            "cookie_secret": base64.b64encode(config.secret_key),
            "debug": config.tornado_debug,
            }
        parameters["is_proxy_used"] = config.is_proxy_used
        WebService.__init__(
            self,
            config.contest_listen_port[shard],
            _cws_handlers,
            parameters,
            shard=shard,
            listen_address=config.contest_listen_address[shard])
        self.file_cacher = FileCacher(self)
        self.evaluation_service = self.connect_to(
            ServiceCoord("EvaluationService", 0))
        self.scoring_service = self.connect_to(
            ServiceCoord("ScoringService", 0))

    @staticmethod
    def authorized_rpc(service, method, arguments):
        """Used by WebService to check if the browser can call a
        certain RPC method.

        service (ServiceCoord): the service called by the browser.
        method (string): the name of the method called.
        arguments (dict): the arguments of the call.
        return (bool): True if ok, False if not authorized.

        """
        # Default fallback: don't authorize.
        return False

    NOTIFICATION_ERROR = "error"
    NOTIFICATION_WARNING = "warning"
    NOTIFICATION_SUCCESS = "success"

    def add_notification(self, username, timestamp, subject, text, level):
        """Store a new notification to send to a user at the first
        opportunity (i.e., at the first request fot db notifications).

        username (string): the user to notify.
        timestamp (int): the time of the notification.
        subject (string): subject of the notification.
        text (string): body of the notification.
        level (string): one of NOTIFICATION_* (defined above)

        """
        if username not in self.notifications:
            self.notifications[username] = []
        self.notifications[username].append((timestamp, subject, text, level))


class MainHandler(BaseHandler):
    """Home page handler.

    """
    def get(self):
        self.render("overview.html", **self.r_params)


class DocumentationHandler(BaseHandler):
    """Displays the instruction (compilation lines, documentation,
    ...) of the contest.

    """
    @tornado.web.authenticated
    def get(self):
        self.render("documentation.html", **self.r_params)


class LoginHandler(BaseHandler):
    """Login handler.

    """
    def post(self):
        username = self.get_argument("username", "")
        password = self.get_argument("password", "")
        next_page = self.get_argument("next", "/")
        user = self.sql_session.query(User)\
            .filter(User.contest == self.contest)\
            .filter(User.username == username).first()

        filtered_user = filter_ascii(username)
        filtered_pass = filter_ascii(password)
        if user is None or user.password != password:
            logger.info("Login error: user=%s pass=%s remote_ip=%s." %
                      (filtered_user, filtered_pass, self.request.remote_ip))
            self.redirect("/?login_error=true")
            return
        if config.ip_lock and user.ip != "0.0.0.0" \
                and user.ip != self.request.remote_ip:
            logger.info("Unexpected IP: user=%s pass=%s remote_ip=%s." %
                      (filtered_user, filtered_pass, self.request.remote_ip))
            self.redirect("/?login_error=true")
            return
        if user.hidden and config.block_hidden_users:
            logger.info("Hidden user login attempt: "
                        "user=%s pass=%s remote_ip=%s." %
                        (filtered_user, filtered_pass, self.request.remote_ip))
            self.redirect("/?login_error=true")
            return

        self.set_secure_cookie("login",
                               pickle.dumps((user.username, make_timestamp())),
                               expires_days=None)
        self.redirect(next_page)


class StartHandler(BaseHandler):
    """Start handler.

    Used by a user who wants to start his per_user_time.

    """
    @tornado.web.authenticated
    @actual_phase_required(-1)
    def post(self):
        user = self.get_current_user()

        logger.info("Starting now for user %s" % user.username)
        user.starting_time = self.timestamp
        self.sql_session.commit()

        self.redirect("/")


class LogoutHandler(BaseHandler):
    """Logout handler.

    """
    def get(self):
        self.clear_cookie("login")
        self.redirect("/")


class TaskDescriptionHandler(BaseHandler):
    """Shows the data of a task in the contest.

    """
    @tornado.web.authenticated
    @actual_phase_required(0)
    def get(self, task_name):
        try:
            task = self.contest.get_task(task_name)
        except KeyError:
            raise tornado.web.HTTPError(404)

        # FIXME are submissions actually needed by this handler?
        submissions = self.sql_session.query(Submission)\
            .filter(Submission.user == self.current_user)\
            .filter(Submission.task == task).all()

        for statement in task.statements.itervalues():
            lang_code = statement.language
            if ISOCodes.is_language_country_code(lang_code):
                statement.language_name = ISOCodes.translate_language_country_code(lang_code, self.locale)
            elif ISOCodes.is_language_code(lang_code):
                statement.language_name = ISOCodes.translate_language_code(lang_code, self.locale)
            elif ISOCodes.is_country_code(lang_code):
                statement.language_name = ISOCodes.translate_country_code(lang_code, self.locale)
            else:
                statement.language_name = lang_code

        self.render("task_description.html", task=task, submissions=submissions, **self.r_params)


class TaskSubmissionsHandler(BaseHandler):
    """Shows the data of a task in the contest.

    """
    @tornado.web.authenticated
    @actual_phase_required(0)
    def get(self, task_name):
        try:
            task = self.contest.get_task(task_name)
        except KeyError:
            raise tornado.web.HTTPError(404)

        submissions = self.sql_session.query(Submission)\
            .filter(Submission.user == self.current_user)\
            .filter(Submission.task == task).all()

        self.render("task_submissions.html", task=task, submissions=submissions, **self.r_params)


class TaskStatementViewHandler(FileHandler):
    """Shows the statement file of a task in the contest.

    """
    @tornado.web.authenticated
    @actual_phase_required(0)
    @tornado.web.asynchronous
    def get(self, task_name, lang_code):
        try:
            task = self.contest.get_task(task_name)
        except KeyError:
            raise tornado.web.HTTPError(404)

        if lang_code not in task.statements:
            raise tornado.web.HTTPError(404)

        statement = task.statements[lang_code].digest
        self.sql_session.close()

        if lang_code != '':
            filename = "%s (%s).pdf" % (task.name, lang_code)
        else:
            filename = "%s.pdf" % task.name

        self.fetch(statement, "application/pdf", filename)


class TaskAttachmentViewHandler(FileHandler):
    """Shows an attachment file of a task in the contest.

    """
    @tornado.web.authenticated
    @actual_phase_required(0)
    @tornado.web.asynchronous
    def get(self, task_name, filename):
        try:
            task = self.contest.get_task(task_name)
        except KeyError:
            raise tornado.web.HTTPError(404)

        if filename not in task.attachments:
            raise tornado.web.HTTPError(404)

        attachment = task.attachments[filename].digest
        self.sql_session.close()

        mimetype = get_type_for_file_name(filename)
        if mimetype is None:
            mimetype = 'application/octet-stream'

        self.fetch(attachment, mimetype, filename)


class SubmissionFileHandler(FileHandler):
    """Send back a submission file.

    """
    @tornado.web.authenticated
    @actual_phase_required(0)
    @tornado.web.asynchronous
    def get(self, task_name, submission_num, filename):
        try:
            task = self.contest.get_task(task_name)
        except KeyError:
            raise tornado.web.HTTPError(404)

        submission = self.sql_session.query(Submission)\
            .filter(Submission.user == self.current_user)\
            .filter(Submission.task == task)\
            .order_by(Submission.timestamp)\
            .offset(int(submission_num) - 1).first()
        if submission is None:
            raise tornado.web.HTTPError(404)

        # The following code assumes that submission.files is a subset
        # of task.submission_format. CWS will always ensure that for new
        # submissions, yet, if the submission_format changes during the
        # competition, this may not hold anymore for old submissions.

        # filename follows our convention (e.g. 'foo.%l'), real_filename
        # follows the one we present to the user (e.g. 'foo.c').
        real_filename = filename
        if submission.language is not None:
            if filename in submission.files:
                real_filename = filename.replace("%l", submission.language)
            else:
                # We don't recognize this filename. Let's try to 'undo'
                # the '%l' -> 'c|cpp|pas' replacement before giving up.
                filename = re.sub('\.%s$' % submission.language, '.%l', filename)

        if filename not in submission.files:
            raise tornado.web.HTTPError(404)

        digest = submission.files[filename].digest
        self.sql_session.close()

        mimetype = get_type_for_file_name(real_filename)
        if mimetype is None:
            mimetype = 'application/octet-stream'

        self.fetch(digest, mimetype, real_filename)


class CommunicationHandler(BaseHandler):
    """Displays the private conversations between the logged in user
    and the contest managers..

    """
    @tornado.web.authenticated
    def get(self):
        self.set_secure_cookie("unread_count", "0")
        self.render("communication.html", **self.r_params)


class NotificationsHandler(BaseHandler):
    """Displays notifications.

    """

    refresh_cookie = False

    @tornado.web.authenticated
    def get(self):
        if not self.current_user:
            raise tornado.web.HTTPError(403)
        res = []
        last_notification = make_datetime(float(self.get_argument("last_notification", "0")))

        # Announcements
        for announcement in self.contest.announcements:
            if announcement.timestamp > last_notification \
                   and announcement.timestamp < self.timestamp:
                res.append({"type": "announcement",
                            "timestamp": make_timestamp(announcement.timestamp),
                            "subject": announcement.subject,
                            "text": announcement.text})

        if self.current_user is not None:
            # Private messages
            for message in self.current_user.messages:
                if message.timestamp > last_notification \
                       and message.timestamp < self.timestamp:
                    res.append({"type": "message",
                                "timestamp": make_timestamp(message.timestamp),
                                "subject": message.subject,
                                "text": message.text})

            # Answers to questions
            for question in self.current_user.questions:
                if question.reply_timestamp is not None \
                       and question.reply_timestamp > last_notification \
                       and question.reply_timestamp < self.timestamp:
                    subject = question.reply_subject
                    text = question.reply_text
                    if question.reply_subject is None:
                        subject = question.reply_text
                        text = ""
                    elif question.reply_text is None:
                        text = ""
                    res.append({"type": "question",
                                "timestamp": make_timestamp(question.reply_timestamp),
                                "subject": subject,
                                "text": text})

        # Update the unread_count cookie before taking notifications
        # into account because we don't want to count them.
        prev_unread_count = self.get_secure_cookie("unread_count")
        next_unread_count = len(res) + (int(prev_unread_count) \
                            if prev_unread_count is not None else 0)
        self.set_secure_cookie("unread_count", str(next_unread_count))

        # Simple notifications
        notifications = self.application.service.notifications
        username = self.current_user.username
        if username in notifications:
            for notification in notifications[username]:
                res.append({"type": "notification",
                            "timestamp": make_timestamp(notification[0]),
                            "subject": notification[1],
                            "text": notification[2],
                            "level": notification[3]})
            del notifications[username]

        self.write(json.dumps(res))


class QuestionHandler(BaseHandler):
    """Called when the user submits a question.

    """
    @tornado.web.authenticated
    def post(self):
        # User can post only if we want.
        if not config.allow_questions:
            raise tornado.web.HTTPError(404)

        question = Question(self.timestamp,
                            self.get_argument("question_subject", ""),
                            self.get_argument("question_text", ""),
                            user=self.current_user)
        self.sql_session.add(question)
        self.sql_session.commit()

        logger.warning("Question submitted by user %s."
                       % self.current_user.username)

        # Add "All ok" notification.
        self.application.service.add_notification(
            self.current_user.username,
            self.timestamp,
            self._("Question received"),
            self._("Your question has been received, you will be "
                   "notified when the it will be answered."),
            ContestWebServer.NOTIFICATION_SUCCESS)

        self.redirect("/communication")


class SubmitHandler(BaseHandler):
    """Handles the received submissions.

    """
    @tornado.web.authenticated
    @actual_phase_required(0)
    def post(self, task_name):
        try:
            task = self.contest.get_task(task_name)
        except KeyError:
            raise tornado.web.HTTPError(404)

        # Alias for easy access
        contest = self.contest

        # Enforce maximum number of submissions
        try:
            if contest.max_submission_number is not None:
                submission_c = self.sql_session.query(func.count(Submission.id))\
                    .join(Submission.task)\
                    .filter(Task.contest == contest)\
                    .filter(Submission.user == self.current_user).scalar()
                if submission_c >= contest.max_submission_number:
                    raise ValueError(
                        self._("You have reached the maximum limit of "
                               "at most %d submissions among all tasks.") %
                        contest.max_submission_number)
            if task.max_submission_number is not None:
                submission_t = self.sql_session.query(func.count(Submission.id))\
                    .filter(Submission.task == task)\
                    .filter(Submission.user == self.current_user).scalar()
                if submission_t >= task.max_submission_number:
                    raise ValueError(
                        self._("You have reached the maximum limit of "
                               "at most %d submissions on this task.") %
                        task.max_submission_number)
        except ValueError as error:
            self.application.service.add_notification(
                self.current_user.username,
                self.timestamp,
                self._("Too many submissions!"),
                str(error),
                ContestWebServer.NOTIFICATION_ERROR)
            self.redirect("/tasks/%s/submissions" % quote(task.name, safe=''))
            return

        # Enforce minimum time between submissions
        try:
            if contest.min_submission_interval is not None:
                last_submission_c = self.sql_session.query(Submission)\
                    .join(Submission.task)\
                    .filter(Task.contest == contest)\
                    .filter(Submission.user == self.current_user)\
                    .order_by(Submission.timestamp.desc()).first()
                if last_submission_c is not None and \
                        self.timestamp - last_submission_c.timestamp < \
                        contest.min_submission_interval:
                    raise ValueError(
                        self._("Among all tasks, you can submit again "
                               "after %d seconds from last submission.") %
                        contest.min_submission_interval.total_seconds())
            # We get the last submission even if we may not need it
            # for min_submission_interval because we may need it later,
            # in case this is a ALLOW_PARTIAL_SUBMISSION task.
            last_submission_t = self.sql_session.query(Submission)\
                .filter(Submission.task == task)\
                .filter(Submission.user == self.current_user)\
                .order_by(Submission.timestamp.desc()).first()
            if task.min_submission_interval is not None:
                if last_submission_t is not None and \
                        self.timestamp - last_submission_t.timestamp < \
                        task.min_submission_interval:
                    raise ValueError(
                        self._("For this task, you can submit again "
                               "after %d seconds from last submission.") %
                        task.min_submission_interval.total_seconds())
        except ValueError as error:
            self.application.service.add_notification(
                self.current_user.username,
                self.timestamp,
                self._("Submissions too frequent!"),
                str(error),
                ContestWebServer.NOTIFICATION_ERROR)
            self.redirect("/tasks/%s/submissions" % quote(task.name, safe=''))
            return

        # Ensure that the user did not submit multiple files with the
        # same name.
        if any(len(x) != 1 for x in self.request.files.values()):
            self.application.service.add_notification(
                self.current_user.username,
                self.timestamp,
                self._("Invalid submission format!"),
                self._("Please select the correct files."),
                ContestWebServer.NOTIFICATION_ERROR)
            self.redirect("/tasks/%s/submissions" % quote(task.name, safe=''))
            return

        # If the user submitted an archive, extract it and use content
        # as request.files.
        if len(self.request.files) == 1 and \
               self.request.files.keys()[0] == "submission":
            archive_data = self.request.files["submission"][0]
            del self.request.files["submission"]

            # Extract the files from the archive.
            temp_archive_file, temp_archive_filename = \
                tempfile.mkstemp(dir=config.temp_dir)
            with os.fdopen(temp_archive_file, "w") as temp_archive_file:
                temp_archive_file.write(archive_data["body"])

            archive_contents = extract_archive(temp_archive_filename,
                archive_data["filename"])

            if archive_contents is None:
                self.application.service.add_notification(
                    self.current_user.username,
                    self.timestamp,
                    self._("Invalid archive format!"),
                    self._("The submitted archive could not be opened."),
                    ContestWebServer.NOTIFICATION_ERROR)
                self.redirect("/tasks/%s/submissions" % quote(task.name, safe=''))
                return

            for item in archive_contents:
                self.request.files[item["filename"]] = [item]

        # This ensure that the user sent one file for every name in
        # submission format and no more. Less is acceptable if task
        # type says so.
        task_type = get_task_type(task=task)
        required = set([x.filename for x in task.submission_format])
        provided = set(self.request.files.keys())
        if not (required == provided or (task_type.ALLOW_PARTIAL_SUBMISSION
                                         and required.issuperset(provided))):
            self.application.service.add_notification(
                self.current_user.username,
                self.timestamp,
                self._("Invalid submission format!"),
                self._("Please select the correct files."),
                ContestWebServer.NOTIFICATION_ERROR)
            self.redirect("/tasks/%s/submissions" % quote(task.name, safe=''))
            return

        # Add submitted files. After this, files is a dictionary indexed
        # by *our* filenames (something like "output01.txt" or
        # "taskname.%l", and whose value is a couple
        # (user_assigned_filename, content).
        files = {}
        for uploaded, data in self.request.files.iteritems():
            files[uploaded] = (data[0]["filename"], data[0]["body"])

        # If we allow partial submissions, implicitly we recover the
        # non-submitted files from the previous submission. And put them
        # in file_digests (i.e. like they have already been sent to FS).
        submission_lang = None
        file_digests = {}
        retrieved = 0
        if task_type.ALLOW_PARTIAL_SUBMISSION and last_submission_t is not None:
            for filename in required.difference(provided):
                if filename in last_submission_t.files:
                    # If we retrieve a language-dependent file from
                    # last submission, we take not that language must
                    # be the same.
                    if "%l" in filename:
                        submission_lang = last_submission_t.language
                    file_digests[filename] = \
                        last_submission_t.files[filename].digest
                    retrieved += 1

        # We need to ensure that everytime we have a .%l in our
        # filenames, the user has one amongst ".cpp", ".c", or ".pas,
        # and that all these are the same (i.e., no mixed-language
        # submissions).
        def which_language(user_filename):
            """Determine the language of user_filename from its
            extension.

            user_filename (string): the file to test.
            return (string): the extension of user_filename, or None
                             if it is not a recognized language.

            """
            extension = os.path.splitext(user_filename)[1]
            try:
                return Submission.LANGUAGES_MAP[extension]
            except KeyError:
                return None

        error = None
        for our_filename in files:
            user_filename = files[our_filename][0]
            if our_filename.find(".%l") != -1:
                lang = which_language(user_filename)
                if lang is None:
                    error = self._("Cannot recognize submission's language.")
                    break
                elif submission_lang is not None and \
                        submission_lang != lang:
                    error = self._("All sources must be in the same language.")
                    break
                else:
                    submission_lang = lang
        if error is not None:
            self.application.service.add_notification(
                self.current_user.username,
                self.timestamp,
                self._("Invalid submission!"),
                error,
                ContestWebServer.NOTIFICATION_ERROR)
            self.redirect("/tasks/%s/submissions" % quote(task.name, safe=''))
            return

        # Check if submitted files are small enough.
        if any([len(f[1]) > config.max_submission_length
                for f in files.values()]):
            self.application.service.add_notification(
                self.current_user.username,
                self.timestamp,
                self._("Submission too big!"),
                self._("Each source file must be at most %d bytes long.") %
                    config.max_submission_length,
                ContestWebServer.NOTIFICATION_ERROR)
            self.redirect("/tasks/%s/submissions" % quote(task.name, safe=''))
            return

        # All checks done, submission accepted.

        # Attempt to store the submission locally to be able to
        # recover a failure.
        local_copy_saved = False

        if config.submit_local_copy:
            try:
                path = os.path.join(
                    config.submit_local_copy_path.replace("%s",
                                                          config.data_dir),
                    self.current_user.username)
                if not os.path.exists(path):
                    os.makedirs(path)
                with codecs.open(os.path.join(path, str(int(make_timestamp(self.timestamp)))),
                                 "w", "utf-8") as file_:
                    pickle.dump((self.contest.id,
                                 self.current_user.id,
                                 task.id,
                                 files), file_)
                local_copy_saved = True
            except Exception as error:
                logger.error("Submission local copy failed - %s" %
                             traceback.format_exc())

        # We now have to send all the files to the destination...
        try:
            for filename in files:
                digest = self.application.service.file_cacher.put_file(
                    description="Submission file %s sent by %s at %d." % (
                        filename,
                        self.current_user.username,
                        make_timestamp(self.timestamp)),
                    binary_data=files[filename][1])
                file_digests[filename] = digest

        # In case of error, the server aborts the submission
        except Exception as error:
            logger.error("Storage failed! %s" % error)
            if local_copy_saved:
                message = "In case of emergency, this server has a local copy."
            else:
                message = "No local copy stored! Your submission was ignored."
            self.application.service.add_notification(
                self.current_user.username,
                self.timestamp,
                self._("Submission storage failed!"),
                self._(message),
                ContestWebServer.NOTIFICATION_ERROR)
            self.redirect("/tasks/%s/submissions" % quote(task.name, safe=''))
            return

        # All the files are stored, ready to submit!
        logger.info("All files stored for submission sent by %s" %
                    self.current_user.username)
        submission = Submission(user=self.current_user,
                                task=task,
                                timestamp=self.timestamp,
                                files={},
                                language=submission_lang)

        for filename, digest in file_digests.items():
            self.sql_session.add(File(digest, filename, submission))
        self.sql_session.add(submission)
        self.sql_session.commit()
        self.application.service.evaluation_service.new_submission(
            submission_id=submission.id)
        self.application.service.add_notification(
            self.current_user.username,
            self.timestamp,
            self._("Submission received"),
            self._("Your submission has been received "
                   "and is currently being evaluated."),
            ContestWebServer.NOTIFICATION_SUCCESS)
        # The argument (encripted submission id) is not used by CWS
        # (nor it discloses information to the user), but it is useful
        # for automatic testing to obtain the submission id).
        # FIXME is it actually used by something?
        self.redirect("/tasks/%s/submissions?%s" % (
            quote(task.name, safe=''),
            encrypt_number(submission.id)))


class UseTokenHandler(BaseHandler):
    """Called when the user try to use a token on a submission.

    """
    @tornado.web.authenticated
    @actual_phase_required(0)
    def post(self, task_name, submission_num):
        try:
            task = self.contest.get_task(task_name)
        except KeyError:
            raise tornado.web.HTTPError(404)

        submission = self.sql_session.query(Submission)\
            .filter(Submission.user == self.current_user)\
            .filter(Submission.task == task)\
            .order_by(Submission.timestamp)\
            .offset(int(submission_num) - 1).first()
        if submission is None:
            raise tornado.web.HTTPError(404)

        # Don't trust the user, check again if (s)he can really play
        # the token.
        tokens_available = self.contest.tokens_available(
                               self.current_user.username,
                               task.name,
                               self.timestamp)
        if tokens_available[0] == 0 or tokens_available[2] is not None:
            logger.warning("User %s tried to play a token "
                           "when it shouldn't."
                           % self.current_user.username)
            # Add "no luck" notification
            self.application.service.add_notification(
                self.current_user.username,
                self.timestamp,
                self._("Token request discarded"),
                self._("Your request has been discarded because you have no "
                       "tokens available."),
                ContestWebServer.NOTIFICATION_ERROR)
            self.redirect("/tasks/%s/submissions" % quote(task.name, safe=''))
            return

        if submission.token is None:
            token = Token(self.timestamp, submission)
            self.sql_session.add(token)
            self.sql_session.commit()
        else:
            self.application.service.add_notification(
                self.current_user.username,
                self.timestamp,
                self._("Token request discarded"),
                self._("Your request has been discarded because you already "
                       "used a token on that submission."),
                ContestWebServer.NOTIFICATION_WARNING)
            self.redirect("/tasks/%s/submissions" % quote(task.name, safe=''))
            return

        # Inform ScoringService and eventually the ranking that the
        # token has been played.
        self.application.service.scoring_service.submission_tokened(
            submission_id=submission.id, timestamp=self.timestamp)

        logger.info("Token played by user %s on task %s."
                    % (self.current_user.username, task.name))

        # Add "All ok" notification
        self.application.service.add_notification(
            self.current_user.username,
            self.timestamp,
            self._("Token request received"),
            self._("Your request has been received "
                   "and applied to the submission."),
            ContestWebServer.NOTIFICATION_SUCCESS)

        self.redirect("/tasks/%s/submissions" % quote(task.name, safe=''))


class SubmissionStatusHandler(BaseHandler):

    refresh_cookie = False

    @tornado.web.authenticated
    @actual_phase_required(0)
    def get(self, task_name, submission_num):
        try:
            task = self.contest.get_task(task_name)
        except KeyError:
            raise tornado.web.HTTPError(404)

        submission = self.sql_session.query(Submission)\
            .filter(Submission.user == self.current_user)\
            .filter(Submission.task == task)\
            .order_by(Submission.timestamp)\
            .offset(int(submission_num) - 1).first()
        if submission is None:
            raise tornado.web.HTTPError(404)

        score_type = get_score_type(submission=submission)

        data = dict()
        if not submission.compiled():
            data["status"] = 1
            data["status_text"] = "Compiling..."
        elif submission.compilation_outcome == "fail":
            data["status"] = 2
            data["status_text"] = "Compilation failed <a class=\"details\">details</a>"
        elif not submission.evaluated():
            data["status"] = 3
            data["status_text"] = "Evaluating..."
        elif not submission.scored():
            data["status"] = 4
            data["status_text"] = "Scoring..."
        else:
            data["status"] = 5
            data["status_text"] = "Evaluated <a class=\"details\">details</a>"

            if score_type is not None and score_type.max_public_score != 0:
                data["max_public_score"] = "%g" % score_type.max_public_score
            data["public_score"] = "%g" % submission.public_score
            data["public_score_details"] = submission.public_score_details
            if submission.token is not None:
                if score_type is not None and score_type.max_score != 0:
                    data["max_score"] = "%g" % score_type.max_score
                data["score"] = "%g" % submission.score
                data["score_details"] = submission.score_details

        self.write(data)


class SubmissionDetailsHandler(BaseHandler):

    refresh_cookie = False

    @tornado.web.authenticated
    @actual_phase_required(0)
    def get(self, task_name, submission_num):
        try:
            task = self.contest.get_task(task_name)
        except KeyError:
            raise tornado.web.HTTPError(404)

        submission = self.sql_session.query(Submission)\
            .filter(Submission.user == self.current_user)\
            .filter(Submission.task == task)\
            .order_by(Submission.timestamp)\
            .offset(int(submission_num) - 1).first()
        if submission is None:
            raise tornado.web.HTTPError(404)

        self.render("submission_details.html", task=task, s=submission)


class UserTestInterfaceHandler(BaseHandler):
    """Serve the interface to test programs.

    """
    @tornado.web.authenticated
    @actual_phase_required(0)
    def get(self):
        usertests = dict()
        default_task = None

        for task in self.contest.tasks:
            if self.request.query == task.name:
                default_task = task
            usertests[task.id] = self.sql_session.query(UserTest)\
                .filter(UserTest.user == self.current_user)\
                .filter(UserTest.task == task).all()

        if default_task is None:
            default_task = self.contest.tasks[0]

        self.render("test_interface.html", default_task=default_task,
                    usertests=usertests, **self.r_params)


class UserTestHandler(BaseHandler):

    refresh_cookie = False

    # The following code has been taken from SubmitHandler and adapted
    # for UserTests.

    @tornado.web.authenticated
    @actual_phase_required(0)
    def post(self, task_name):
        try:
            task = self.contest.get_task(task_name)
        except KeyError:
            raise tornado.web.HTTPError(404)

        # Check that the task is testable
        task_type = get_task_type(task=task)
        if not task_type.testable:
            logger.warning("User %s tried to make test on task %s." %
                           (current_user.username, task_name))
            raise HTTPError(404)

        # Alias for easy access
        contest = self.contest

        # Enforce maximum number of usertests
        try:
            if contest.max_usertest_number is not None:
                usertest_c = self.sql_session.query(func.count(UserTest.id))\
                    .join(UserTest.task)\
                    .filter(Task.contest == contest)\
                    .filter(UserTest.user == self.current_user).scalar()
                if usertest_c >= contest.max_usertest_number:
                    raise ValueError(
                        self._("You have reached the maximum limit of "
                               "at most %d tests among all tasks.") %
                        contest.max_usertest_number)
            if task.max_usertest_number is not None:
                usertest_t = self.sql_session.query(func.count(UserTest.id))\
                    .filter(UserTest.task == task)\
                    .filter(UserTest.user == self.current_user).scalar()
                if usertest_t >= task.max_usertest_number:
                    raise ValueError(
                        self._("You have reached the maximum limit of "
                               "at most %d tests on this task.") %
                        task.max_usertest_number)
        except ValueError as error:
            self.application.service.add_notification(
                self.current_user.username,
                self.timestamp,
                self._("Too many tests!"),
                str(error),
                ContestWebServer.NOTIFICATION_ERROR)
            self.redirect("/testing?%s" % quote(task.name, safe=''))
            return

        # Enforce minimum time between usertests
        try:
            if contest.min_usertest_interval is not None:
                last_usertest_c = self.sql_session.query(UserTest)\
                    .join(UserTest.task)\
                    .filter(Task.contest == contest)\
                    .filter(UserTest.user == self.current_user)\
                    .order_by(UserTest.timestamp.desc()).first()
                if last_usertest_c is not None and \
                        self.timestamp - last_usertest_c.timestamp < \
                        contest.min_usertest_interval:
                    raise ValueError(
                        self._("Among all tasks, you can test again "
                               "after %d seconds from last test.") %
                        contest.min_usertest_interval.total_seconds())
            # We get the last usertest even if we may not need it
            # for min_usertest_interval because we may need it later,
            # in case this is a ALLOW_PARTIAL_SUBMISSION task.
            last_usertest_t = self.sql_session.query(UserTest)\
                .filter(UserTest.task == task)\
                .filter(UserTest.user == self.current_user)\
                .order_by(UserTest.timestamp.desc()).first()
            if task.min_usertest_interval is not None:
                if last_usertest_t is not None and \
                        self.timestamp - last_usertest_t.timestamp < \
                        task.min_usertest_interval:
                    raise ValueError(
                        self._("For this task, you can test again "
                               "after %d seconds from last test.") %
                        task.min_usertest_interval.total_seconds())
        except ValueError as error:
            self.application.service.add_notification(
                self.current_user.username,
                self.timestamp,
                self._("Tests too frequent!"),
                str(error),
                ContestWebServer.NOTIFICATION_ERROR)
            self.redirect("/testing?%s" % quote(task.name, safe=''))
            return

        # Ensure that the user did not submit multiple files with the
        # same name.
        if any(len(x) != 1 for x in self.request.files.values()):
            self.application.service.add_notification(
                self.current_user.username,
                self.timestamp,
                self._("Invalid test format!"),
                self._("Please select the correct files."),
                ContestWebServer.NOTIFICATION_ERROR)
            self.redirect("/testing?%s" % quote(task.name, safe=''))
            return

        # If the user submitted an archive, extract it and use content
        # as request.files.
        if len(self.request.files) == 1 and \
               self.request.files.keys()[0] == "submission":
            archive_data = self.request.files["submission"][0]
            del self.request.files["submission"]

            # Extract the files from the archive.
            temp_archive_file, temp_archive_filename = \
                tempfile.mkstemp(dir=config.temp_dir)
            with os.fdopen(temp_archive_file, "w") as temp_archive_file:
                temp_archive_file.write(archive_data["body"])

            archive_contents = extract_archive(temp_archive_filename,
                archive_data["filename"])

            if archive_contents is None:
                self.application.service.add_notification(
                    self.current_user.username,
                    self.timestamp,
                    self._("Invalid archive format!"),
                    self._("The submitted archive could not be opened."),
                    ContestWebServer.NOTIFICATION_ERROR)
                self.redirect("/testing?%s" % quote(task.name, safe=''))
                return

            for item in archive_contents:
                self.request.files[item["filename"]] = [item]

        # This ensure that the user sent one file for every name in
        # submission format and no more. Less is acceptable if task
        # type says so.
        required = set([x.filename for x in task.submission_format] + task_type.get_user_managers(task.submission_format) + ["input"])
        provided = set(self.request.files.keys())
        if not (required == provided or (task_type.ALLOW_PARTIAL_SUBMISSION
                                         and required.issuperset(provided))):
            self.application.service.add_notification(
                self.current_user.username,
                self.timestamp,
                self._("Invalid test format!"),
                self._("Please select the correct files."),
                ContestWebServer.NOTIFICATION_ERROR)
            self.redirect("/testing?%s" % quote(task.name, safe=''))
            return

        # Add submitted files. After this, files is a dictionary indexed
        # by *our* filenames (something like "output01.txt" or
        # "taskname.%l", and whose value is a couple
        # (user_assigned_filename, content).
        files = {}
        for uploaded, data in self.request.files.iteritems():
            files[uploaded] = (data[0]["filename"], data[0]["body"])

        # If we allow partial submissions, implicitly we recover the
        # non-submitted files from the previous submission. And put them
        # in file_digests (i.e. like they have already been sent to FS).
        submission_lang = None
        file_digests = {}
        retrieved = 0
        if task_type.ALLOW_PARTIAL_SUBMISSION and last_usertest_t is not None:
            for filename in required.difference(provided):
                if filename in last_usertest_t.files:
                    # If we retrieve a language-dependent file from
                    # last submission, we take not that language must
                    # be the same.
                    if "%l" in filename:
                        submission_lang = last_usertest_t.language
                    file_digests[filename] = \
                        last_usertest_t.files[filename].digest
                    retrieved += 1

        # We need to ensure that everytime we have a .%l in our
        # filenames, the user has one amongst ".cpp", ".c", or ".pas,
        # and that all these are the same (i.e., no mixed-language
        # submissions).
        def which_language(user_filename):
            """Determine the language of user_filename from its
            extension.

            user_filename (string): the file to test.
            return (string): the extension of user_filename, or None
                             if it is not a recognized language.

            """
            extension = os.path.splitext(user_filename)[1]
            try:
                return Submission.LANGUAGES_MAP[extension]
            except KeyError:
                return None

        error = None
        for our_filename in files:
            user_filename = files[our_filename][0]
            if our_filename.find(".%l") != -1:
                lang = which_language(user_filename)
                if lang is None:
                    error = self._("Cannot recognize test's language.")
                    break
                elif submission_lang is not None and \
                        submission_lang != lang:
                    error = self._("All sources must be in the same language.")
                    break
                else:
                    submission_lang = lang
        if error is not None:
            self.application.service.add_notification(
                self.current_user.username,
                self.timestamp,
                self._("Invalid test!"),
                error,
                ContestWebServer.NOTIFICATION_ERROR)
            self.redirect("/testing?%s" % quote(task.name, safe=''))
            return

        # Check if submitted files are small enough.
        if any([len(f[1]) > config.max_submission_length
                for n, f in files.items() if n != "input"]):
            self.application.service.add_notification(
                self.current_user.username,
                self.timestamp,
                self._("Test too big!"),
                self._("Each source file must be at most %d bytes long.") %
                    config.max_submission_length,
                ContestWebServer.NOTIFICATION_ERROR)
            self.redirect("/testing?%s" % quote(task.name, safe=''))
            return
        if len(files["input"][1]) > config.max_input_length:
            self.application.service.add_notification(
                self.current_user.username,
                self.timestamp,
                self._("Input too big!"),
                self._("The input file must be at most %d bytes long.") %
                    config.max_input_length,
                ContestWebServer.NOTIFICATION_ERROR)
            self.redirect("/testing?%s" % quote(task.name, safe=''))
            return

        # All checks done, submission accepted.

        # Attempt to store the submission locally to be able to
        # recover a failure.
        local_copy_saved = False

        if config.tests_local_copy:
            try:
                path = os.path.join(
                    config.tests_local_copy_path.replace("%s",
                                                         config.data_dir),
                    self.current_user.username)
                if not os.path.exists(path):
                    os.makedirs(path)
                with codecs.open(os.path.join(path, str(int(make_timestamp(self.timestamp)))),
                                 "w", "utf-8") as file_:
                    pickle.dump((self.contest.id,
                                 self.current_user.id,
                                 task.id,
                                 files), file_)
                local_copy_saved = True
            except Exception as error:
                logger.error("Test local copy failed - %s" %
                             traceback.format_exc())

        # We now have to send all the files to the destination...
        try:
            for filename in files:
                digest = self.application.service.file_cacher.put_file(
                    description="Test file %s sent by %s at %d." % (
                        filename,
                        self.current_user.username,
                        make_timestamp(self.timestamp)),
                    binary_data=files[filename][1])
                file_digests[filename] = digest

        # In case of error, the server aborts the submission
        except Exception as error:
            logger.error("Storage failed! %s" % error)
            if local_copy_saved:
                message = "In case of emergency, this server has a local copy."
            else:
                message = "No local copy stored! Your test was ignored."
            self.application.service.add_notification(
                self.current_user.username,
                self.timestamp,
                self._("Test storage failed!"),
                self._(message),
                ContestWebServer.NOTIFICATION_ERROR)
            self.redirect("/testing?%s" % quote(task.name, safe=''))
            return

        # All the files are stored, ready to submit!
        logger.info("All files stored for test sent by %s" %
                    self.current_user.username)
        usertest = UserTest(user=self.current_user,
                            task=task,
                            timestamp=self.timestamp,
                            files={},
                            managers={},
                            input=file_digests["input"],
                            language=submission_lang)

        for filename in [x.filename for x in task.submission_format]:
            digest = file_digests[filename]
            self.sql_session.add(UserTestFile(digest, filename, usertest))
        for filename in task_type.get_user_managers(task.submission_format):
            digest = file_digests[filename]
            if submission_lang is not None:
                filename = filename.replace("%l", submission_lang)
            self.sql_session.add(UserTestManager(digest, filename, usertest))

        self.sql_session.add(usertest)
        self.sql_session.commit()
        self.application.service.evaluation_service.new_user_test(
            user_test_id=usertest.id)
        self.application.service.add_notification(
            self.current_user.username,
            self.timestamp,
            self._("Test received"),
            self._("Your test has been received "
                   "and is currently being executed."),
            ContestWebServer.NOTIFICATION_SUCCESS)
        self.redirect("/testing?%s" % quote(task.name, safe=''))


class UserTestStatusHandler(BaseHandler):

    refresh_cookie = False

    @tornado.web.authenticated
    @actual_phase_required(0)
    def get(self, task_name, usertest_num):
        try:
            task = self.contest.get_task(task_name)
        except KeyError:
            raise tornado.web.HTTPError(404)

        usertest = self.sql_session.query(UserTest)\
            .filter(UserTest.user == self.current_user)\
            .filter(UserTest.task == task)\
            .order_by(UserTest.timestamp)\
            .offset(int(usertest_num) - 1).first()
        if usertest is None:
            raise tornado.web.HTTPError(404)

        data = dict()
        if not usertest.compiled():
            data["status"] = 1
            data["status_text"] = "Compiling..."
        elif usertest.compilation_outcome == "fail":
            data["status"] = 2
            data["status_text"] = "Compilation failed <a class=\"details\">details</a>"
        elif not usertest.evaluated():
            data["status"] = 3
            data["status_text"] = "Executing..."
        else:
            data["status"] = 4
            data["status_text"] = "Executed <a class=\"details\">details</a>"
            if usertest.execution_time is not None:
                data["time"] = "%(seconds)0.3f s" % {'seconds': usertest.execution_time}
            else:
                data["time"] = None
            if usertest.memory_used is not None:
                data["memory"] = "%(mb)0.2f MiB" % {'mb': usertest.memory_used / 1024. / 1024.}
            else:
                data["memory"] = None
            data["output"] = usertest.output is not None

        self.write(data)


class UserTestDetailsHandler(BaseHandler):

    refresh_cookie = False

    @tornado.web.authenticated
    @actual_phase_required(0)
    def get(self, task_name, usertest_num):
        try:
            task = self.contest.get_task(task_name)
        except KeyError:
            raise tornado.web.HTTPError(404)

        usertest = self.sql_session.query(UserTest)\
            .filter(UserTest.user == self.current_user)\
            .filter(UserTest.task == task)\
            .order_by(UserTest.timestamp)\
            .offset(int(usertest_num) - 1).first()
        if usertest is None:
            raise tornado.web.HTTPError(404)

        self.render("usertest_details.html", task=task, t=usertest)


class UserTestIOHandler(FileHandler):
    """Send back a submission file.

    """
    @tornado.web.authenticated
    @actual_phase_required(0)
    @tornado.web.asynchronous
    def get(self, task_name, usertest_num, io):
        try:
            task = self.contest.get_task(task_name)
        except KeyError:
            raise tornado.web.HTTPError(404)

        usertest = self.sql_session.query(UserTest)\
            .filter(UserTest.user == self.current_user)\
            .filter(UserTest.task == task)\
            .order_by(UserTest.timestamp)\
            .offset(int(usertest_num) - 1).first()
        if usertest is None:
            raise tornado.web.HTTPError(404)

        digest = getattr(usertest, io)
        self.sql_session.close()

        if digest is None:
            raise tornado.web.HTTPError(404)

        mimetype = 'text/plain'

        self.fetch(digest, mimetype, io)


class UserTestFileHandler(FileHandler):
    """Send back a submission file.

    """
    @tornado.web.authenticated
    @actual_phase_required(0)
    @tornado.web.asynchronous
    def get(self, task_name, usertest_num, filename):
        try:
            task = self.contest.get_task(task_name)
        except KeyError:
            raise tornado.web.HTTPError(404)

        usertest = self.sql_session.query(UserTest)\
            .filter(UserTest.user == self.current_user)\
            .filter(UserTest.task == task)\
            .order_by(UserTest.timestamp)\
            .offset(int(usertest_num) - 1).first()
        if usertest is None:
            raise tornado.web.HTTPError(404)

        # filename follows our convention (e.g. 'foo.%l'), real_filename
        # follows the one we present to the user (e.g. 'foo.c').
        real_filename = filename
        if usertest.language is not None:
            real_filename = filename.replace("%l", usertest.language)

        if filename in usertest.files:
            digest = usertest.files[filename].digest
        elif filename in usertest.managers:
            digest = usertest.managers[filename].digest
        else:
            raise tornado.web.HTTPError(404)
        self.sql_session.close()

        mimetype = get_type_for_file_name(real_filename)
        if mimetype is None:
            mimetype = 'application/octet-stream'

        self.fetch(digest, mimetype, real_filename)


class StaticFileGzHandler(tornado.web.StaticFileHandler):
    """Handle files which may be gzip-compressed on the filesystem."""
    def get(self, path, *args, **kwargs):
        # Unless told otherwise, default to text/plain.
        self.set_header("Content-Type", "text/plain")
        try:
            # Try an ordinary request.
            tornado.web.StaticFileHandler.get(self, path, *args, **kwargs)
        except tornado.web.HTTPError as error:
            if error.status_code == 404:
                # If that failed, try servicing it with a .gz extension.
                path = "%s.gz" % path

                tornado.web.StaticFileHandler.get(self, path, *args, **kwargs)

                # If it succeeded, then mark the encoding as gzip.
                self.set_header("Content-Encoding", "gzip")
            else:
                raise


_cws_handlers = [
    (r"/",       MainHandler),
    (r"/login",  LoginHandler),
    (r"/logout", LogoutHandler),
    (r"/start",  StartHandler),
    (r"/tasks/(.*)/description", TaskDescriptionHandler),
    (r"/tasks/(.*)/submissions", TaskSubmissionsHandler),
    (r"/tasks/(.*)/statements/(.*)", TaskStatementViewHandler),
    (r"/tasks/(.*)/attachments/(.*)", TaskAttachmentViewHandler),
    (r"/tasks/(.*)/submit", SubmitHandler),
    (r"/tasks/(.*)/submissions/([1-9][0-9]*)", SubmissionStatusHandler),
    (r"/tasks/(.*)/submissions/([1-9][0-9]*)/details", SubmissionDetailsHandler),
    (r"/tasks/(.*)/submissions/([1-9][0-9]*)/files/(.*)", SubmissionFileHandler),
    (r"/tasks/(.*)/submissions/([1-9][0-9]*)/token", UseTokenHandler),
    (r"/tasks/(.*)/test", UserTestHandler),
    (r"/tasks/(.*)/tests/([1-9][0-9]*)", UserTestStatusHandler),
    (r"/tasks/(.*)/tests/([1-9][0-9]*)/details", UserTestDetailsHandler),
    (r"/tasks/(.*)/tests/([1-9][0-9]*)/(input|output)", UserTestIOHandler),
    (r"/tasks/(.*)/tests/([1-9][0-9]*)/files/(.*)", UserTestFileHandler),
    (r"/communication", CommunicationHandler),
    (r"/documentation", DocumentationHandler),
    (r"/notifications", NotificationsHandler),
    (r"/question", QuestionHandler),
    (r"/testing", UserTestInterfaceHandler),
    (r"/stl/(.*)", StaticFileGzHandler, {"path": config.stl_path}),
    ]


def main():
    """Parse arguments and launch service.

    """
    default_argument_parser("Contestants' web server for CMS.",
                            ContestWebServer,
                            ask_contest=ask_for_contest).run()

if __name__ == "__main__":
    main()
