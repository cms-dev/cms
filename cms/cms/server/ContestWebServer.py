#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2011 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2011 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2011 Matteo Boscariol <boscarim@hotmail.com>
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

import simplejson
import tempfile
import traceback
import zipfile

import tornado.web
import tornado.locale

from cms.async.AsyncLibrary import logger
from cms.async.WebAsyncLibrary import WebService, rpc_callback
from cms.async import ServiceCoord

from cms.db.SQLAlchemyAll import Session, Contest, User, Question, \
     Submission, Token, Task, File

from cms.db.Utils import ask_for_contest

from cms import Config
import cms.util.WebConfig as WebConfig

from cms.server.Utils import file_handler_gen, catch_exceptions
from cms.util.Cryptographics import encrypt_number, decrypt_number, \
     get_encryption_alphabet


class BaseHandler(tornado.web.RequestHandler):
    """Base RequestHandler for this application.

    All the RequestHandler classes in this application should be a
    child of this class.

    """

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

    def get_current_user(self):
        """Gets the current user logged in from the cookies

        If a valid cookie is retrieved, return a User object with the
        username specified in the cookie. Otherwise, return None.

        """
        if self.get_secure_cookie("login") is None:
            return None
        try:
            username = str(pickle.loads(self.get_secure_cookie("login"))[0])
        except:
            self.clear_cookie("login")
            return None

        user = self.sql_session.query(User).filter_by(contest=self.contest).\
            filter_by(username=username).first()
        if user is None:
            self.clear_cookie("login")
            return None
        return user

    def render_params(self):
        """Return the default render params used by almost all handlers.

        return (dict): default render params

        """
        ret = {}
        ret["timestamp"] = int(time.time())
        ret["contest"] = self.contest
        if(self.contest is not None):
            ret["phase"] = self.contest.phase(ret["timestamp"])
        ret["contest_list"] = self.sql_session.query(Contest).all()
        ret["cookie"] = str(self.cookies)
        return ret

    def valid_phase(self, r_param):
        """Return True if the contest is running and redirect to home
        if not running.

        r_param (dict): the default render_params of the handler
        return (bool): True if contest is running

        """
        if r_param["phase"] != 0:
            self.redirect("/")
            return False
        return True

    def finish(self, *args, **kwds):
        """ Finishes this response, ending the HTTP request.

        We override this method in order to properly close the database.

        """
        if hasattr(self, "sql_session"):
            logger.debug("Closing SQL connection.")
            try:
                self.sql_session.close()
            except Exception as e:
                logger.warning("Couldn't close SQL connection: " + repr(e))
        tornado.web.RequestHandler.finish(self, *args, **kwds)


FileHandler = file_handler_gen(BaseHandler)


class ContestWebServer(WebService):
    """Service that runs the web server serving the contestants.

    """
    def __init__(self, shard, contest):
        logger.initialize(ServiceCoord("ContestWebServer", shard))
        logger.debug("ContestWebServer.__init__")
        self.contest = contest

        # This is a dictionary (indexed by username) of pending
        # notification. Things like "Yay, you're submission went
        # through.", not things like "Your question has been replied",
        # that are handled by the db. Each username points to a list
        # of tuples (timestamp, subject, text).
        self.notifications = {}

        parameters = WebConfig.contest_parameters
        parameters["template_path"] = os.path.join(os.path.dirname(__file__),
                                                   "templates", "contest")
        parameters["static_path"] = os.path.join(os.path.dirname(__file__),
                                                 "static")
        WebService.__init__(self,
            Config.contest_listen_port,
            handlers,
            parameters,
            shard=shard)
        self.FS = self.connect_to(ServiceCoord("FileStorage", 0))
        self.ES = self.connect_to(ServiceCoord("EvaluationServer", 0))

    def authorized_rpc(self, service, method, arguments):
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
        r_params = self.render_params()
        self.render("overview.html", **r_params)


class InstructionHandler(BaseHandler):
    """Displays the instruction (compilation lines, documentation,
    ...) of the contest.

    """
    @catch_exceptions
    def get(self):
        r_params = self.render_params()
        self.render("instructions.html", **r_params)


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
        if Config.ip_lock and user.ip != "0.0.0.0" \
                and user.ip != self.request.remote_ip:
            logger.info("Unexpected IP: user=%s pass=%s remote_ip=%s." %
                      (username, password, self.request.remote_ip))
            self.redirect("/?login_error=true")
            return
        if user.hidden and Config.block_hidden_users:
            logger.info("Hidden user login attempt: " +
                      "user=%s pass=%s remote_ip=%s." %
                      (username, password, self.request.remote_ip))
            self.redirect("/?login_error=true")
            return

        self.set_secure_cookie("login",
                               pickle.dumps((user.username, int(time.time()))))
        self.redirect(next_page)


class LogoutHandler(BaseHandler):
    """Logout handler.

    """
    @catch_exceptions
    def get(self):
        self.clear_cookie("login")
        self.redirect("/")


class TaskViewHandler(BaseHandler):
    """Shows the data of a task in the contest.

    """
    @catch_exceptions
    @tornado.web.authenticated
    def get(self, task_id):

        r_params = self.render_params()
        if not self.valid_phase(r_params):
            return

        # Decrypt task_id.
        try:
            task_id = decrypt_number(task_id)
        except ValueError:
            # We reply with Forbidden if the given ID cannot be
            # decrypted.
            raise tornado.web.HTTPError(403)

        r_params["task"] = Task.get_from_id(task_id, self.sql_session)
        if r_params["task"] == None or \
            r_params["task"].contest != self.contest:
            raise tornado.web.HTTPError(404)

        r_params["submissions"] = self.sql_session.query(Submission)\
            .filter_by(user=self.current_user)\
            .filter_by(task=r_params["task"]).all()

        self.render("task.html", **r_params)


class TaskStatementViewHandler(FileHandler):
    """Shows the statement file of a task in the contest.

    """
    @catch_exceptions
    @tornado.web.authenticated
    @tornado.web.asynchronous
    def get(self, task_id):

        r_params = self.render_params()
        if not self.valid_phase(r_params):
            return

        # Decrypt task_id.
        try:
            task_id = decrypt_number(task_id)
        except ValueError:
            # We reply with Forbidden if the given ID cannot be
            # decrypted.
            raise tornado.web.HTTPError(403)

        task = Task.get_from_id(task_id, self.sql_session)
        if task == None or task.contest != self.contest:
            raise tornado.web.HTTPError(404)

        self.fetch(task.statement, "application/pdf", task.name + ".pdf")


class SubmissionFileHandler(FileHandler):
    """Send back a submission file.

    """
    @catch_exceptions
    @tornado.web.authenticated
    @tornado.web.asynchronous
    def get(self, file_id):

        r_params = self.render_params()
        if not self.valid_phase(r_params):
            return

        # Decrypt file_id.
        try:
            file_id = decrypt_number(file_id)
        except ValueError:
            # We reply with Forbidden if the given ID cannot be
            # decrypted.
            raise tornado.web.HTTPError(403)

        sub_file = self.sql_session.query(File).join(Submission).join(Task)\
            .filter(File.id == file_id)\
            .filter(Submission.user_id == self.current_user.id)\
            .filter(Task.contest_id == self.contest.id)\
            .first()

        if sub_file is None:
            raise tornado.web.HTTPError(404)

        self.fetch(sub_file.digest, "text/plain", sub_file.filename)


class CommunicationHandler(BaseHandler):
    """Displays the private conversations between the logged in user
    and the contest managers..

    """
    @catch_exceptions
    @tornado.web.authenticated
    def get(self):
        r_params = self.render_params()
        self.render("communication.html", **r_params)


class NotificationsHandler(BaseHandler):
    """Displays notifications.

    """
    @catch_exceptions
    def get(self):
        if not self.current_user:
            raise tornado.web.HTTPError(403)
        timestamp = int(time.time())
        res = []
        last_notification = float(self.get_argument("last_notification", "0"))

        # Announcements
        for announcement in self.contest.announcements:
            if announcement.timestamp > last_notification \
                   and announcement.timestamp < timestamp:
                res.append({"type": "announcement",
                            "timestamp": announcement.timestamp,
                            "subject": announcement.subject,
                            "text": announcement.text})

        if self.current_user is not None:
            # Private messages
            for message in self.current_user.messages:
                if message.timestamp > last_notification \
                       and message.timestamp < timestamp:
                    res.append({"type": "message",
                                "timestamp": message.timestamp,
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
                                "timestamp": question.reply_timestamp,
                                "subject": subject,
                                "text": text})

        # Simple notifications
        notifications = self.application.service.notifications
        username = self.current_user.username
        if username in notifications:
            for notification in notifications[username]:
                res.append({"type": "notification",
                            "timestamp": notification[0],
                            "subject": notification[1],
                            "text": notification[2]})
            del notifications[username]

        self.write(simplejson.dumps(res))


class QuestionHandler(BaseHandler):
    """Called when the user submits a question.

    """
    @catch_exceptions
    @tornado.web.authenticated
    def post(self):

        timestamp = int(time.time())
        question = Question(timestamp,
                            self.get_argument("question_subject", ""),
                            self.get_argument("question_text", ""),
                            user=self.current_user)
        self.sql_session.add(question)
        self.sql_session.commit()

        logger.warning("Question submitted by user %s."
                       % self.current_user.username)

        # Add "All ok" notification
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
    @tornado.web.authenticated
    @tornado.web.asynchronous
    def post(self, task_id):

        self.r_params = self.render_params()
        if not self.valid_phase(self.r_params):
            return

        self.timestamp = self.r_params["timestamp"]

        # Decrypt task_id.
        try:
            task_id = decrypt_number(task_id)
        except ValueError:
            # We reply with Forbidden if the given ID cannot be
            # decrypted.
            raise tornado.web.HTTPError(403)

        self.task = Task.get_from_id(task_id, self.sql_session)

        if self.current_user is None or \
            self.task is None or \
            self.task.contest != self.contest:
            raise tornado.web.HTTPError(404)

        try:
            uploaded = self.request.files[self.task.name][0]
        except KeyError:
            self.application.service.add_notification(
                self.current_user.username,
                int(time.time()),
                self._("No file selected"),
                self._("Select a file to send your submission.")
            )
            return

        self.files = {}

        if uploaded["content_type"] == "application/zip":
            # Extract the files from the archive.
            temp_zip_file, temp_zip_filename = tempfile.mkstemp()
            # Note: this is just a binary copy, so no utf-8 wtf-ery here.
            with os.fdopen(temp_zip_file, "w") as temp_zip_file:
                temp_zip_file.write(uploaded["body"])

            zip_object = zipfile.ZipFile(temp_zip_filename, "r")
            for item in zip_object.infolist():
                self.files[item.filename] = zip_object.read(item)
        else:
            self.files[uploaded["filename"]] = uploaded["body"]

        # Check if submitted files are small enough.
        if any([len(content) > Config.max_submission_length
                for content in self.files.values()]):
            self.application.service.add_notification(
                self.current_user.username,
                int(time.time()),
                self._("Submission too big!"),
                self._("Each files must be at most %d bytes long.") %
                    Config.max_submission_length)
            return

        # Submit the files.

        # Attempt to store the submission locally to be able to recover
        # a failure.
        self.local_copy_saved = False

        if Config.submit_local_copy:
            try:
                path = os.path.join(Config.submit_local_copy_path,
                                    self.current_user.username)
                if not os.path.exists(path):
                    os.makedirs(path)
                with codecs.open(os.path.join(path, str(self.timestamp)),
                                 "w", "utf-8") as fd:
                    pickle.dump((self.contest.id,
                                 self.current_user.id,
                                 self.task,
                                 self.files), fd)
                self.local_copy_saved = True
            except Exception as e:
                logger.error("Submission local copy failed - " +
                             traceback.format_exc())

        # We now have to send all the files to the destination...
        self.file_digests = {}

        for filename, content in self.files.items():
            if self.application.service.FS.put_file(
                callback=SubmitHandler.storage_callback,
                plus=filename,
                binary_data=content,
                description="Submission file %s sent by %s at %d." % (
                    filename,
                    self.current_user.username,
                    self.timestamp),
                bind_obj=self) == False:
                self.storage_callback(None, None, error="Connection failed.")
                break

    @catch_exceptions
    @rpc_callback
    def storage_callback(self, data, plus, error=None):
        logger.debug("Storage callback")
        if error is None:
            self.file_digests[plus] = data
            if len(self.file_digests) == len(self.files):
                # All the files are stored, ready to submit!
                logger.info("I saved all the files")
                s = Submission(user=self.current_user,
                               task=self.task,
                               timestamp=self.timestamp,
                               files={})

                for filename, digest in self.file_digests.items():
                    self.sql_session.add(File(digest, filename, s))
                self.sql_session.add(s)
                self.sql_session.commit()
                self.submission_id = s.id
                self.r_params["submission"] = s
                self.r_params["warned"] = False
                if False == self.application.service.ES.new_submission(
                    submission_id=s.id,
                    callback=self.es_notify_callback):
                    self.es_notify_callback(None,
                                            None,
                                            error="Connection failed.")
        else:
            logger.error("Storage failed! " + error)
            if self.local_copy_saved:
                message = "In case of emergency, this server has a local copy."
            else:
                message = "No local copy stored! Your submission was ignored."
            self.application.service.add_notification(
                self.current_user.username,
                int(time.time()),
                self._("Submission storage failed!"),
                self._(message))
            self.redirect("/tasks/%s" % encrypt_number(self.task.id))

    @catch_exceptions
    @rpc_callback
    def es_notify_callback(self, data, plus, error=None):
        logger.debug("ES notify_callback")
        if error is not None:
            logger.error("Notification to ES failed! " + error)
            self.application.service.add_notification(
                self.current_user.username,
                int(time.time()),
                self._("Submission received, but..."),
                self._("Your submission has been received "
                       "but an error has occured and is NOT "
                       "currently being evaluated."))
        else:
            # Add "All ok" notification
            self.application.service.add_notification(
                self.current_user.username,
                int(time.time()),
                self._("Submission received"),
                self._("Your submission has been received "
                       "and is currently being evaluated."))

        self.redirect("/tasks/%s" % encrypt_number(self.task.id))


class UseTokenHandler(BaseHandler):
    """Called when the user try to use a token on a submission.

    """
    @catch_exceptions
    @tornado.web.authenticated
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
        timestamp = int(time.time())
        if self.contest.tokens_available(self.current_user.username,
                                         submission.task.name,
                                         timestamp)[0] <= 0:
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
            self.redirect("/tasks/%s" % encrypt_number(submission.task.id))
            return

        token = Token(timestamp, submission)
        self.sql_session.add(token)
        self.sql_session.commit()

        logger.info("Token played by user %s on task %s."
                    % (self.current_user.username, submission.task.name))

        # Add "All ok" notification
        self.application.service.add_notification(
            self.current_user.username,
            timestamp,
            self._("Token request received"),
            self._("Your request has been received "
                   "and applied to the submission."))

        self.redirect("/tasks/%s" % encrypt_number(submission.task.id))


handlers = [(r"/",
             MainHandler),
            (r"/login",
             LoginHandler),
            (r"/logout",
             LogoutHandler),
            (r"/submission_file/([%s]+)" % (get_encryption_alphabet()),
             SubmissionFileHandler),
            (r"/tasks/([%s]+)" % (get_encryption_alphabet()),
             TaskViewHandler),
            (r"/tasks/([%s]+)/statement" % (get_encryption_alphabet()),
             TaskStatementViewHandler),
            (r"/usetoken",
             UseTokenHandler),
            (r"/submit/([%s]+)" %  (get_encryption_alphabet()),
             SubmitHandler),
            (r"/communication",
             CommunicationHandler),
            (r"/instructions",
             InstructionHandler),
            (r"/notifications",
             NotificationsHandler),
            (r"/question",
             QuestionHandler),
            (r"/stl/(.*)",
             tornado.web.StaticFileHandler, {"path": Config.stl_path}),
            ]


def main():
    import sys
    if len(sys.argv) < 2:
        print sys.argv[0], "shard [contest]"
        exit(1)
    ContestWebServer(int(sys.argv[1]),
                     ask_for_contest(1)).run()


if __name__ == "__main__":
    main()
