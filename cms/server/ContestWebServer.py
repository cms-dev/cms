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
import pickle
import time
import codecs

import base64
import mimetypes
import simplejson as json
import tempfile
import traceback
from datetime import datetime, timedelta

import tornado.web
import tornado.locale

from cms import config, default_argument_parser, logger
from cms.async.WebAsyncLibrary import WebService
from cms.async import ServiceCoord
from cms.db import ask_for_contest
from cms.db.FileCacher import FileCacher
from cms.db.SQLAlchemyAll import Session, Contest, User, Question, \
     Submission, Token, Task, File, Attachment
from cms.grading.tasktypes import get_task_type
from cms.server import file_handler_gen, catch_exceptions, extract_archive, \
     actual_phase_required, get_url_root, decrypt_arguments, \
     CommonRequestHandler
from cmscommon.Cryptographics import encrypt_number, decrypt_number, \
     get_encryption_alphabet
from cmscommon.DateTime import make_datetime, make_timestamp


class BaseHandler(CommonRequestHandler):
    """Base RequestHandler for this application.

    All the RequestHandler classes in this application should be a
    child of this class.

    """

    # Whether the login cookie duration has to be refreshed when
    # this handler is called. Useful to filter asynchronous
    # requests.
    refresh_cookie = True

    @catch_exceptions
    def prepare(self):
        """This method is executed at the beginning of each request.

        """
        self.set_header("Cache-Control", "no-cache, must-revalidate")

        self.sql_session = Session()
        self.contest = Contest.get_from_id(self.application.service.contest,
                                           self.sql_session)

        localization_dir = os.path.join(os.path.dirname(__file__), "mo")
        if os.path.exists(localization_dir):
            tornado.locale.load_gettext_translations(localization_dir, "cms")

        self._ = self.get_browser_locale().translate
        self.r_params = self.render_params()

    def get_current_user(self):
        """Gets the current user logged in from the cookies

        If a valid cookie is retrieved, return a User object with the
        username specified in the cookie. Otherwise, return None.

        """
        timestamp = make_datetime()

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
        if timestamp - last_update > timedelta(seconds=config.cookie_duration):
            self.clear_cookie("login")
            return None

        user = self.sql_session.query(User).filter_by(contest=self.contest).\
            filter_by(username=username).first()
        if user is None:
            self.clear_cookie("login")
            return None

        if self.refresh_cookie:
            self.set_secure_cookie("login",
                               pickle.dumps((user.username, int(time.time()))),
                               expires_days=None)

        return user

    @staticmethod
    def _get_token_status (obj):
        """Return the status of the tokens for the given object.

        obj (Contest or Task): an object that has the token_* attributes.
        return (int): one of 0 (disabled), 1 (enabled/finite) and 2
                      (enabled/infinite).

        """
        if obj.token_initial is None:
            return 0
        elif obj.token_gen_time == 0 and obj.token_gen_number > 0:
            return 2
        else:
            return 1

    def render_params(self):
        """Return the default render params used by almost all handlers.

        return (dict): default render params

        """
        ret = {}
        ret["timestamp"] = make_datetime()
        ret["contest"] = self.contest
        ret["url_root"] = get_url_root(self.request.path)
        ret["cookie"] = str(self.cookies)  # FIXME really needed?

        ret["phase"] = self.contest.phase(ret["timestamp"])

        if self.current_user is not None:
            # "correct" the phase, considering the per_user_time
            ret["actual_phase"] = 2 * ret["phase"]
            # If we have a user logged in, the contest may be ended
            # before contest.stop if the user has finished the time
            # allocated for him/her.
            ret["valid_phase_end"] = self.contest.stop
            if ret["phase"] == 0 and self.contest.per_user_time is not None:
                if self.current_user.starting_time is None:
                    ret["actual_phase"] = -1
                else:
                    user_end_time = (self.current_user.starting_time +
                                     self.contest.per_user_time)
                    if user_end_time < self.contest.stop:
                        ret["valid_phase_end"] = user_end_time
                    if user_end_time <= ret["timestamp"]:
                        ret["actual_phase"] = 1

        # some information about token configuration
        ret["tokens_contest"] = self._get_token_status(self.contest)
        if ret["tokens_contest"] == 2 and self.contest.token_min_interval == 0:
            ret["tokens_contest"] = 3  # infinite and no min_interval

        t_tokens = sum(self._get_token_status(t) for t in self.contest.tasks)
        if t_tokens == 0:
            ret["tokens_tasks"] = 0  # all disabled
        elif t_tokens == 2 * len(self.contest.tasks):
            ret["tokens_tasks"] = 2  # all infinite
        else:
            ret["tokens_tasks"] = 1  # all finite or mixed
        if ret["tokens_tasks"] == 2 and \
            not any(t.token_min_interval for t in self.contest.tasks):
            ret["tokens_tasks"] = 3  # all infinite and no min_intervals

        return ret

    def finish(self, *args, **kwds):
        """ Finishes this response, ending the HTTP request.

        We override this method in order to properly close the database.

        """
        if hasattr(self, "sql_session"):
            logger.debug("Closing SQL connection.")
            try:
                self.sql_session.close()
            except Exception as error:
                logger.warning("Couldn't close SQL connection: %r" % error)
        tornado.web.RequestHandler.finish(self, *args, **kwds)


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

    def add_notification(self, username, timestamp, subject, text):
        """Store a new notification to send to a user at the first
        opportunity (i.e., at the first request fot db notifications).

        username (string): the user to notify.
        timestamp (int): the time of the notification.
        subject (string): subject of the notification.
        text (string): body of the notification.

        """
        if username not in self.notifications:
            self.notifications[username] = []
        self.notifications[username].append((timestamp, subject, text))


class MainHandler(BaseHandler):
    """Home page handler.

    """
    @catch_exceptions
    def get(self):
        self.render("overview.html", **self.r_params)


class DocumentationHandler(BaseHandler):
    """Displays the instruction (compilation lines, documentation,
    ...) of the contest.

    """
    @catch_exceptions
    @tornado.web.authenticated
    def get(self):
        self.render("documentation.html", **self.r_params)


class LoginHandler(BaseHandler):
    """Login handler.

    """
    @catch_exceptions
    def post(self):
        username = self.get_argument("username", "")
        password = self.get_argument("password", "")
        next_page = self.get_argument("next", "/")
        user = self.sql_session.query(User).filter_by(contest=self.contest).\
               filter_by(username=username).first()

        if user is None or user.password != password:
            logger.info("Login error: user=%s pass=%s remote_ip=%s." %
                      (username, password, self.request.remote_ip))
            self.redirect("/?login_error=true")
            return
        if config.ip_lock and user.ip != "0.0.0.0" \
                and user.ip != self.request.remote_ip:
            logger.info("Unexpected IP: user=%s pass=%s remote_ip=%s." %
                      (username, password, self.request.remote_ip))
            self.redirect("/?login_error=true")
            return
        if user.hidden and config.block_hidden_users:
            logger.info("Hidden user login attempt: "
                        "user=%s pass=%s remote_ip=%s." %
                        (username, password, self.request.remote_ip))
            self.redirect("/?login_error=true")
            return

        self.set_secure_cookie("login",
                               pickle.dumps((user.username, int(time.time()))),
                               expires_days=None)
        self.redirect(next_page)


class StartHandler(BaseHandler):
    """Start handler.

    Used by a user who wants to start his per_user_time.

    """
    @catch_exceptions
    @tornado.web.authenticated
    @actual_phase_required(-1)
    def post(self):
        user = self.get_current_user()
        timestamp = make_datetime()

        logger.info("Starting now for user %s" % user.username)
        user.starting_time = timestamp
        self.sql_session.commit()

        self.redirect("/")


class LogoutHandler(BaseHandler):
    """Logout handler.

    """
    @catch_exceptions
    def get(self):
        self.clear_cookie("login")
        self.redirect("/")


class TaskDescriptionHandler(BaseHandler):
    """Shows the data of a task in the contest.

    """
    @catch_exceptions
    @decrypt_arguments
    @tornado.web.authenticated
    @actual_phase_required(0)
    def get(self, task_id):

        self.r_params["task"] = Task.get_from_id(task_id, self.sql_session)
        if self.r_params["task"] is None or \
            self.r_params["task"].contest != self.contest:
            raise tornado.web.HTTPError(404)

        self.r_params["submissions"] = self.sql_session.query(Submission)\
            .filter_by(user=self.current_user)\
            .filter_by(task=self.r_params["task"]).all()

        self.render("task_description.html", **self.r_params)


class TaskSubmissionsHandler(BaseHandler):
    """Shows the data of a task in the contest.

    """
    @catch_exceptions
    @decrypt_arguments
    @tornado.web.authenticated
    @actual_phase_required(0)
    def get(self, task_id):

        self.r_params["task"] = Task.get_from_id(task_id, self.sql_session)
        if self.r_params["task"] is None or \
            self.r_params["task"].contest != self.contest:
            raise tornado.web.HTTPError(404)

        self.r_params["submissions"] = self.sql_session.query(Submission)\
            .filter_by(user=self.current_user)\
            .filter_by(task=self.r_params["task"]).all()

        self.render("task_submissions.html", **self.r_params)


class TaskStatementViewHandler(FileHandler):
    """Shows the statement file of a task in the contest.

    """
    @catch_exceptions
    @tornado.web.authenticated
    @actual_phase_required(0)
    @tornado.web.asynchronous
    def get(self, task_id, lang_code):
        try:
            task_id = decrypt_number(task_id)
        except ValueError:
            raise tornado.web.HTTPError(404)

        task = Task.get_from_id(task_id, self.sql_session)
        if task is None or task.contest != self.contest:
            raise tornado.web.HTTPError(404)

        if lang_code not in task.statements:
            raise tornado.web.HTTPError(404)

        statement = task.statements[lang_code].digest
        self.sql_session.close()

        self.fetch(statement, "application/pdf", "%s.pdf" % task.name)


class TaskAttachmentViewHandler(FileHandler):
    """Shows an attachment file of a task in the contest.

    """
    @catch_exceptions
    @tornado.web.authenticated
    @actual_phase_required(0)
    @tornado.web.asynchronous
    def get(self, task_id, filename):
        try:
            task_id = decrypt_number(task_id)
        except ValueError:
            raise tornado.web.HTTPError(404)

        task = Task.get_from_id(task_id, self.sql_session)
        if task is None or task.contest != self.contest:
            raise tornado.web.HTTPError(404)

        if filename not in task.attachments:
            raise tornado.web.HTTPError(404)

        attachment = task.attachments[filename].digest
        self.sql_session.close()

        # FIXME: Returns (None, None) if it can't guess the type.
        # What shall we do in this situation?
        mimetype = mimetypes.guess_type(filename)[0]

        self.fetch(attachment, mimetype, filename)


class SubmissionFileHandler(FileHandler):
    """Send back a submission file.

    """
    @catch_exceptions
    @decrypt_arguments
    @tornado.web.authenticated
    @actual_phase_required(0)
    @tornado.web.asynchronous
    def get(self, file_id):

        sub_file = self.sql_session.query(File).join(Submission).join(Task)\
            .filter(File.id == file_id)\
            .filter(Submission.user_id == self.current_user.id)\
            .filter(Task.contest_id == self.contest.id)\
            .first()

        if sub_file is None:
            raise tornado.web.HTTPError(404)

        submission = sub_file.submission
        real_filename = sub_file.filename
        if submission.language is not None:
            real_filename = real_filename.replace("%l", submission.language)
        digest = sub_file.digest
        self.sql_session.close()

        self.fetch(digest, "text/plain", real_filename)


class CommunicationHandler(BaseHandler):
    """Displays the private conversations between the logged in user
    and the contest managers..

    """
    @catch_exceptions
    @tornado.web.authenticated
    def get(self):
        self.set_secure_cookie("unread_count", "0")
        self.render("communication.html", **self.r_params)


class NotificationsHandler(BaseHandler):
    """Displays notifications.

    """

    refresh_cookie = False

    @catch_exceptions
    @tornado.web.authenticated
    def get(self):
        if not self.current_user:
            raise tornado.web.HTTPError(403)
        timestamp = make_datetime()
        res = []
        last_notification = make_datetime(float(self.get_argument("last_notification", "0")))

        # Announcements
        for announcement in self.contest.announcements:
            if announcement.timestamp > last_notification \
                   and announcement.timestamp < timestamp:
                res.append({"type": "announcement",
                            "timestamp": make_timestamp(announcement.timestamp),
                            "subject": announcement.subject,
                            "text": announcement.text})

        if self.current_user is not None:
            # Private messages
            for message in self.current_user.messages:
                if message.timestamp > last_notification \
                       and message.timestamp < timestamp:
                    res.append({"type": "message",
                                "timestamp": make_timestamp(message.timestamp),
                                "subject": message.subject,
                                "text": message.text})

            # Answers to questions
            for question in self.current_user.questions:
                if question.reply_timestamp > last_notification \
                       and question.reply_timestamp < timestamp:
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
                            "text": notification[2]})
            del notifications[username]

        self.write(json.dumps(res))


class QuestionHandler(BaseHandler):
    """Called when the user submits a question.

    """
    @catch_exceptions
    @tornado.web.authenticated
    def post(self):
        # User can post only if we want.
        if not config.allow_questions:
            raise tornado.web.HTTPError(404)

        timestamp = make_datetime()
        question = Question(timestamp,
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
            timestamp,
            self._("Question received"),
            self._("Your question has been received, you will be "
                   "notified when the it will be answered."))

        self.redirect("/communication")


class SubmitHandler(BaseHandler):
    """Handles the received submissions.

    """
    @decrypt_arguments
    @tornado.web.authenticated
    @actual_phase_required(0)
    @tornado.web.asynchronous
    def post(self, task_id):

        self.timestamp = self.r_params["timestamp"]

        self.task_id = task_id
        self.task = Task.get_from_id(task_id, self.sql_session)

        if self.current_user is None or \
            self.task is None or \
            self.task.contest != self.contest:
            raise tornado.web.HTTPError(404)

        # Enforce minimum time between submissions for the same task.
        last_submission = self.sql_session.query(Submission)\
            .filter_by(task_id=self.task.id)\
            .filter_by(user_id=self.current_user.id)\
            .order_by(Submission.timestamp.desc()).first()
        if last_submission is not None and \
               self.timestamp - last_submission.timestamp < \
               timedelta(seconds=config.min_submission_interval):
            self.application.service.add_notification(
                self.current_user.username,
                make_datetime(),
                self._("Submissions too frequent!"),
                self._("For each task, you can submit "
                       "again after %s seconds from last submission.") %
                config.min_submission_interval)
            self.redirect("/tasks/%s/submissions" % encrypt_number(self.task.id))
            return

        # Ensure that the user did not submit multiple files with the
        # same name.
        if any(len(x) != 1 for x in self.request.files.values()):
            self.application.service.add_notification(
                self.current_user.username,
                make_datetime(),
                self._("Invalid submission format!"),
                self._("Please select the correct files."))
            self.redirect("/tasks/%s/submissions" % encrypt_number(self.task.id))
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
                    make_datetime(),
                    self._("Invalid archive format!"),
                    self._("The submitted archive could not be opened."))
                self.redirect("/tasks/%s/submissions" % encrypt_number(self.task.id))
                return

            for item in archive_contents:
                self.request.files[item["filename"]] = [item]

        # This ensure that the user sent one file for every name in
        # submission format and no more. Less is acceptable if task
        # type says so.
        task_type = get_task_type(task=self.task)
        required = set([x.filename for x in self.task.submission_format])
        provided = set(self.request.files.keys())
        if not (required == provided or (task_type.ALLOW_PARTIAL_SUBMISSION
                                         and required.issuperset(provided))):
            self.application.service.add_notification(
                self.current_user.username,
                make_datetime(),
                self._("Invalid submission format!"),
                self._("Please select the correct files."))
            self.redirect("/tasks/%s/submissions" % encrypt_number(self.task.id))
            return

        # Add submitted files. After this, self.files is a dictionary
        # indexed by *our* filenames (something like "output01.txt" or
        # "taskname.%l", and whose value is a couple
        # (user_assigned_filename, content).
        self.files = {}
        for uploaded, data in self.request.files.iteritems():
            self.files[uploaded] = (data[0]["filename"], data[0]["body"])

        # If we allow partial submissions, implicitly we recover the
        # non-submitted files from the previous submission. And put
        # them in self.file_digests (i.e., like they have already been
        # sent to FS).
        self.submission_lang = None
        self.file_digests = {}
        self.retrieved = 0
        if task_type.ALLOW_PARTIAL_SUBMISSION and last_submission is not None:
            for filename in required.difference(provided):
                if filename in last_submission.files:
                    # If we retrieve a language-dependent file from
                    # last submission, we take not that language must
                    # be the same.
                    if "%l" in filename:
                        self.submission_lang = last_submission.language
                    self.file_digests[filename] = \
                        last_submission.files[filename].digest
                    self.retrieved += 1

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
        for our_filename in self.files:
            user_filename = self.files[our_filename][0]
            if our_filename.find(".%l") != -1:
                lang = which_language(user_filename)
                if lang is None:
                    error = self._("Cannot recognize submission's language.")
                    break
                elif self.submission_lang is not None and \
                        self.submission_lang != lang:
                    error = self._("All sources must be in the same language.")
                    break
                else:
                    self.submission_lang = lang
        if error is not None:
            self.application.service.add_notification(
                self.current_user.username,
                make_datetime(),
                self._("Invalid submission!"),
                error)
            self.redirect("/tasks/%s/submissions" % encrypt_number(self.task.id))
            return

        # Check if submitted files are small enough.
        if any([len(f[1]) > config.max_submission_length
                for f in self.files.values()]):
            self.application.service.add_notification(
                self.current_user.username,
                make_datetime(),
                self._("Submission too big!"),
                self._("Each files must be at most %d bytes long.") %
                    config.max_submission_length)
            self.redirect("/tasks/%s/submissions" % encrypt_number(self.task.id))
            return

        # All checks done, submission accepted.

        # Attempt to store the submission locally to be able to
        # recover a failure.
        self.local_copy_saved = False

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
                                 self.task,
                                 self.files), file_)
                self.local_copy_saved = True
            except Exception as error:
                logger.error("Submission local copy failed - %s" %
                             traceback.format_exc())
        self.username = self.current_user.username
        self.sql_session.close()

        # We now have to send all the files to the destination...
        try:
            for filename in self.files:
                digest = self.application.service.file_cacher.put_file(
                    description="Submission file %s sent by %s at %d." % (
                        filename,
                        self.username,
                        make_timestamp(self.timestamp)),
                    binary_data=self.files[filename][1])
                self.file_digests[filename] = digest

        # In case of error, the server aborts the submission
        except Exception as error:
            logger.error("Storage failed! %s" % error)
            if self.local_copy_saved:
                message = "In case of emergency, this server has a local copy."
            else:
                message = "No local copy stored! Your submission was ignored."
            self.application.service.add_notification(
                self.username,
                make_datetime(),
                self._("Submission storage failed!"),
                self._(message))
            self.redirect("/tasks/%s/submissions" % encrypt_number(self.task_id))
            return

        # All the files are stored, ready to submit!
        self.sql_session = Session()
        current_user = self.get_current_user()
        self.task = Task.get_from_id(self.task_id, self.sql_session)
        logger.info("All files stored for submission sent by %s" %
                    self.username)
        submission = Submission(user=current_user,
                                task=self.task,
                                timestamp=self.timestamp,
                                files={},
                                language=self.submission_lang)

        for filename, digest in self.file_digests.items():
            self.sql_session.add(File(digest, filename, submission))
        self.sql_session.add(submission)
        self.sql_session.commit()
        self.r_params["submission"] = submission
        self.r_params["warned"] = False
        self.application.service.evaluation_service.new_submission(
            submission_id=submission.id)
        self.application.service.add_notification(
            self.username,
            make_datetime(),
            self._("Submission received"),
            self._("Your submission has been received "
                   "and is currently being evaluated."))
        # The argument (encripted submission id) is not used by CWS
        # (nor it discloses information to the user), but it is useful
        # for automatic testing to obtain the submission id).
        self.redirect("/tasks/%s/submissions?%s" % (
            encrypt_number(self.task.id),
            encrypt_number(submission.id)))


class UseTokenHandler(BaseHandler):
    """Called when the user try to use a token on a submission.

    """
    @catch_exceptions
    @tornado.web.authenticated
    @actual_phase_required(0)
    def post(self):

        submission_id = self.get_argument("submission_id", "")

        # Decrypt submission_id.
        try:
            submission_id = decrypt_number(submission_id)
        except ValueError:
            # We reply with Forbidden if the given ID cannot be
            # decrypted.
            logger.warning("User %s tried to play a token "
                           "on an undecryptable submission_id."
                           % self.current_user.username)
            raise tornado.web.HTTPError(403)

        # Find submission and check it is of the current user.
        submission = Submission.get_from_id(submission_id,
                                            self.sql_session)
        if submission is None or \
               submission.user != self.current_user:
            logger.warning("User %s tried to play a token "
                           "on an unexisting submission_id."
                           % self.current_user.username)
            raise tornado.web.HTTPError(404)

        # Don't trust the user, check again if (s)he can really play
        # the token.
        timestamp = make_datetime()
        tokens_available = self.contest.tokens_available(
                               self.current_user.username,
                               submission.task.name,
                               timestamp)
        if tokens_available[0] == 0 or tokens_available[2] is not None:
            logger.warning("User %s tried to play a token "
                           "when it shouldn't."
                           % self.current_user.username)
            # Add "no luck" notification
            self.application.service.add_notification(
                self.current_user.username,
                timestamp,
                self._("Token request discarded"),
                self._("Your request has been discarded because you have no "
                       "tokens available."))
            self.redirect("/tasks/%s/submissions" % encrypt_number(submission.task.id))
            return

        token = Token(timestamp, submission)
        self.sql_session.add(token)
        self.sql_session.commit()

        # Inform ScoringService and eventually the ranking that the
        # token has been played.
        self.application.service.scoring_service.submission_tokened(
            submission_id=submission_id, timestamp=timestamp)

        logger.info("Token played by user %s on task %s."
                    % (self.current_user.username, submission.task.name))

        # Add "All ok" notification
        self.application.service.add_notification(
            self.current_user.username,
            timestamp,
            self._("Token request received"),
            self._("Your request has been received "
                   "and applied to the submission."))

        self.redirect("/tasks/%s/submissions" %
                      encrypt_number(submission.task.id))


class SubmissionStatusHandler(BaseHandler):

    refresh_cookie = False

    @catch_exceptions
    @decrypt_arguments
    @tornado.web.authenticated
    @actual_phase_required(0)
    def get(self, sub_id):
        submission = Submission.get_from_id(sub_id, self.sql_session)
        if submission.user.id != self.current_user.id or \
               submission.task.contest.id != self.contest.id:
            raise tornado.web.HTTPError(403)
        self.render("submission_snippet.html", s=submission)


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


enc_alph = get_encryption_alphabet()
_cws_handlers = [
    (r"/",       MainHandler),
    (r"/login",  LoginHandler),
    (r"/logout", LogoutHandler),
    (r"/start",  StartHandler),
    (r"/tasks/([%s]+)/description" % enc_alph, TaskDescriptionHandler),
    (r"/tasks/([%s]+)/submissions" % enc_alph, TaskSubmissionsHandler),
    (r"/tasks/([%s]+)/statements/(.*)" % enc_alph, TaskStatementViewHandler),
    (r"/tasks/([%s]+)/attachments/(.*)" % enc_alph, TaskAttachmentViewHandler),
    (r"/submission_file/([%s]+)" % enc_alph,   SubmissionFileHandler),
    (r"/submission_status/([%s]+)" % enc_alph, SubmissionStatusHandler),
    (r"/submit/([%s]+)" % enc_alph,            SubmitHandler),
    (r"/usetoken",                             UseTokenHandler),
    (r"/communication", CommunicationHandler),
    (r"/documentation", DocumentationHandler),
    (r"/notifications", NotificationsHandler),
    (r"/question",      QuestionHandler),
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
