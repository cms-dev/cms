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

from functools import wraps
import os
import pickle
import time
import codecs

import tempfile
import zipfile

import tornado.web

from cms.async.AsyncLibrary import logger
from cms.async.WebAsyncLibrary import WebService, rpc_callback
from cms.async import ServiceCoord

from cms.db.SQLAlchemyAll import Session, Contest, User, Question, \
     Submission, Task, File

from cms.db.Utils import ask_for_contest

import cms.util.Configuration as Configuration
import cms.util.WebConfig as WebConfig
import cms.server.BusinessLayer as BusinessLayer


def contest_required(func):
    """Decorator to ensure that in the parameter list there is one
    named 'contest'. If not present, the browser shows a 404.

    """
    @wraps(func)
    def wrapper(*args, **kwds):
        """Wrap the function in something that check if in the
        parameter list there is a 'contest' argument and if it does
        not find it, raises a 404.

        args (list): positional arguments for func
        kwds (dict): named arguments for func
        returns (object): return value of func, or raises 404

        """
        if args[0].contest != None:
            return func(*args, **kwds)
        else:
            raise tornado.web.HTTPError(404)
    return wrapper


class BaseHandler(tornado.web.RequestHandler):
    """Base RequestHandler for this application.

    All the RequestHandler classes in this application should be a
    child of this class.

    """
    def prepare(self):
        """This method is executed at the beginning of each request.
        """
        self.set_header("Cache-Control", "no-cache, must-revalidate")

        self.sql_session = Session()
        self.contest = self.sql_session.query(Contest)\
            .filter_by(id=self.application.service.contest).first()

    def get_current_user(self):
        """Gets the current user logged in from the cookies

        If a valid cookie is retrieved, returns a User object with the
        username specified in the cookie. Otherwise, returns None.
        """
        if self.get_secure_cookie("login") == None:
            return None
        try:
            user_id, cookie_time = \
                pickle.loads(self.get_secure_cookie("login"))
        except:
            self.clear_cookie("login")
            return None

        # Uncomment to ignore old cookies
        # if cookie_time == None or cookie_time < upsince:
        #     return None

        current_user = self.sql_session.query(User)\
            .filter_by(id=user_id).first()
        if current_user == None:
            self.clear_cookie("login")
            return None
        return current_user

    def render_params(self):
        """Return the default render params used by almost all handlers.

        return (dict): default render params

        """
        ret = {}
        ret["timestamp"] = time.time()
        ret["contest"] = self.contest
        if(self.contest != None):
            ret["phase"] = BusinessLayer.contest_phase(**ret)
        ret["contest_list"] = self.sql_session.query(Contest).all()
        ret["cookie"] = str(self.cookies)
        return ret

    def valid_phase(self, r_param):
        """Return True if the contest is running.

        r_param (dict): the default render_params of the handler
        returns (bool): True if contest is running

        """
        if r_param["phase"] != 0:
            self.redirect("/")
            return False
        return True

    def finish(self, *args, **kwds):
        """ Finishes this response, ending the HTTP request.

        We override this method in order to properly close the database.
        """
        logger.debug("Closing SQL connection.")
        self.sql_session.close()
        tornado.web.RequestHandler.finish(self, *args, **kwds)


class FileHandler(BaseHandler):
    """Base class for handlers that need to serve a file to the user.

    """
    def fetch(self, digest, content_type, filename):
        """Sends the RPC to the FS.

        """
        service = ServiceCoord("FileStorage", 0)
        if service not in self.application.service.remote_services or \
               not self.application.service.remote_services[service].connected:
            # TODO: Signal the user

            self.finish()
            return

        self.application.service.remote_services[service].get_file(
            callback=self._fetch_callback,
            plus=[content_type, filename],
            digest=digest)

    @rpc_callback
    def _fetch_callback(self, caller, data, plus, error=None):
        """This is the callback for the RPC method called from a web
        page, that just collects the response.

        """
        if data == None:
            self.finish()
            return

        (content_type, filename) = plus

        self.set_header("Content-Type", content_type)
        self.set_header("Content-Disposition",
                        "attachment; filename=\"%s\"" % filename)
        self.write(data)
        self.finish()


class ContestWebServer(WebService):
    """Simple web service example.

    """
    def __init__(self, shard, contest):
        logger.initialize(ServiceCoord("ContestWebServer", shard))
        logger.debug("ContestWebServer.__init__")
        self.contest = contest
        parameters = WebConfig.contest_parameters
        parameters["template_path"] = os.path.join(os.path.dirname(__file__),
                                  "templates", "contest")
        parameters["static_path"] = os.path.join(os.path.dirname(__file__),
                                  "static", "contest")
        WebService.__init__(self,
            WebConfig.contest_listen_port,
            handlers,
            parameters,
            shard=shard)
        self.FS = self.connect_to(ServiceCoord("FileStorage", 0))
        self.ES = self.connect_to(ServiceCoord("EvaluationServer", 0))


class MainHandler(BaseHandler):
    """Home page handler.

    """
    def get(self):
        r_params = self.render_params()
        self.render("welcome.html", **r_params)


class InstructionHandler(BaseHandler):
    """Displays the instruction (compilation lines, documentation,
    ...) of the contest.

    """
    def get(self):
        r_params = self.render_params()
        self.render("instructions.html", **r_params)


class LoginHandler(BaseHandler):
    """Login handler.

    """
    def post(self):
        username = self.get_argument("username", "")
        password = self.get_argument("password", "")
        next_page = self.get_argument("next", "/")
        user = self.sql_session.query(User).filter_by(contest=self.contest).\
               filter_by(username=username).first()

        if user == None or user.password != password:
            logger.info("Login error: user=%s pass=%s remote_ip=%s." %
                      (username, password, self.request.remote_ip))
            self.redirect("/?login_error=true")
            return
        if WebConfig.ip_lock and user.ip != "0.0.0.0" \
                and user.ip != self.request.remote_ip:
            logger.info("Unexpected IP: user=%s pass=%s remote_ip=%s." %
                      (username, password, self.request.remote_ip))
            self.redirect("/?login_error=true")
            return
        if user.hidden and WebConfig.block_hidden_users:
            logger.info("Hidden user login attempt: " +
                      "user=%s pass=%s remote_ip=%s." %
                      (username, password, self.request.remote_ip))
            self.redirect("/?login_error=true")
            return

        self.set_secure_cookie("login",
                               pickle.dumps((user.id, time.time())))
        self.redirect(next_page)


class LogoutHandler(BaseHandler):
    """Logout handler.

    """
    def get(self):
        self.clear_cookie("login")
        self.redirect("/")


class TaskViewHandler(BaseHandler):
    """Shows the data of a task in the contest.

    """
    @tornado.web.authenticated
    def get(self, task_name):

        r_params = self.render_params()
        if not self.valid_phase(r_params):
            return
        try:
            r_params["task"] = [x for x in self.contest.tasks
                                if x.name == task_name][0]
        except:
            raise tornado.web.HTTPError(404)
        r_params["submissions"] = self.sql_session.query(Submission)\
            .filter_by(user=self.current_user)\
            .filter_by(task=r_params["task"]).all()

        self.render("task.html", **r_params)


class TaskStatementViewHandler(FileHandler):
    """Shows the statement file of a task in the contest.

    """
    @tornado.web.authenticated
    @tornado.web.asynchronous
    def get(self, task_name):
        r_params = self.render_params()
        if not self.valid_phase(r_params):
            return
        try:
            task = [x for x in self.contest.tasks if x.name == task_name][0]
        except:
            self.write("Task %s not found." % (task_name))

        self.fetch(task.statement, "application/pdf", task.name + ".pdf")


class SubmissionDetailHandler(BaseHandler):
    """Shows additional details for the specified submission.

    """
    @tornado.web.authenticated
    def get(self, submission_id):

        r_params = self.render_params()
        if not self.valid_phase(r_params):
            return
        # search the submission in the contest

        submission = self.sql_session.query(Submission).join(Task)\
            .filter(Submission.id == submission_id)\
            .filter(Submission.user_id == self.current_user.id)\
            .filter(Task.contest_id == self.contest.id).first()
        if submission == None:
            raise tornado.web.HTTPError(404)
        r_params["submission"] = submission
        r_params["task"] = submission.task
        self.render("submission_detail.html", **r_params)


class SubmissionFileHandler(FileHandler):
    """Shows a submission file.

    """
    @tornado.web.authenticated
    @tornado.web.asynchronous
    def get(self, file_id):

        r_params = self.render_params()
        if not self.valid_phase(r_params):
            return

        sub_file = self.sql_session.query(File).join(Submission).join(Task)\
            .filter(File.id == file_id)\
            .filter(Submission.user_id == self.current_user.id)\
            .filter(Task.contest_id == self.contest.id)\
            .first()

        if sub_file == None:
            raise tornado.web.HTTPError(404)

        self.fetch(sub_file.digest, "text/plain", sub_file.filename)


class UserHandler(BaseHandler):
    """Displays information about the current user, in particular
    messages and announcements.

    """
    @tornado.web.authenticated
    def get(self):
        r_params = self.render_params()
        self.render("user.html", **r_params)


class NotificationsHandler(BaseHandler):
    """Displays notifications.

    """
    def post(self):
        timestamp = time.time()
        last_request = self.get_argument("lastrequest", timestamp)
        messages = []
        announcements = []
        if last_request != "":
            announcements = [x for x in self.contest.announcements
                             if x.timestamp > float(last_request)
                             and x.timestamp < timestamp]
            if self.current_user != None:
                messages = [x for x in self.current_user.messages
                            if x.timestamp > float(last_request)
                            and x.timestamp < timestamp]
        self.set_header("Content-Type", "text/xml")
        self.render("notifications.xml",
                    announcements=announcements,
                    messages=messages,
                    timestamp=timestamp)


class QuestionHandler(BaseHandler):
    """Called when the user submit a question.

    """
    @tornado.web.authenticated
    def post(self):
        r_params = self.render_params()

        question = Question(time.time(),
                            self.get_argument("question_subject", ""),
                            self.get_argument("question_text", ""),
                            user=self.current_user)
        self.sql_session.add(question)
        self.sql_session.commit()

        logger.warning("Question submitted by user %s."
                       % self.current_user.username)
        self.render("successfulQuestion.html", **r_params)


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

        self.task = self.sql_session.query(Task).filter_by(name=task_id)\
            .filter_by(contest=self.contest).first()

        if self.current_user == None or self.task == None:
            self.send_error(404)
            self.finish()
            return

        try:
            uploaded = self.request.files[self.task.name][0]
        except KeyError:
            self.write("No file chosen.")
            self.finish()
            return

        self.files = {}

        if uploaded["content_type"] == "application/zip":
            #Extract the files from the archive
            temp_zip_file, temp_zip_filename = tempfile.mkstemp()
            # Note: this is just a binary copy, so no utf-8 wtf-ery here.
            with os.fdopen(temp_zip_file, "w") as temp_zip_file:
                temp_zip_file.write(uploaded["body"])

            zip_object = zipfile.ZipFile(temp_zip_filename, "r")
            for item in zip_object.infolist():
                self.files[item.filename] = zip_object.read(item)
        else:
            self.files[uploaded["filename"]] = uploaded["body"]

        # Submit the files.

        # Attempt to store the submission locally to be able to recover
        # a failure.
        # TODO: Determine when the submission is to be considered accepted
        # and pre-emptively stored.
        if Configuration.submit_local_copy:
            try:
                path = os.path.join(Configuration.submit_local_copy_path,
                                    self.current_user.username)
                if not os.path.exists(path):
                    os.mkdir(path)
                with codecs.open(os.path.join(path, str(int(self.timestamp))),
                                 "w", "utf-8") as fd:
                    pickle.dump((self.contest.id,
                                 self.current_user.id,
                                 self.task,
                                 self.files), fd)
            except Exception as e:
                logger.warning("submit: local copy failed - " + repr(e))

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
                    int(self.timestamp)),
                bind_obj=self) == False:
                self.storage_callback(None,None,error = "Connection failed.")
                break

    @rpc_callback
    def storage_callback(self, data, plus, error=None):
        logger.debug("Storage callback")
        if error == None:
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
                self.r_params["submission"] = s
                self.r_params["warned"] = False
                if self.application.service.ES.new_submission(
                    submission_id=s.id,
                    callback=self.es_notify_callback)== False:
                    self.es_notify_callback(None, None, error="Connection failed.")
        else:
            logger.error("Storage failed! " + error)
            self.finish()

    @rpc_callback
    def es_notify_callback(self, data, plus, error=None):
        logger.debug("ES notify_callback")
        if error == None:
            self.render("successfulSub.html", **self.r_params)
        else:
            logger.error("Notification to ES failed! " + error)
            self.finish()

handlers = [(r"/",
             MainHandler),
            (r"/login",
             LoginHandler),
            (r"/logout",
             LogoutHandler),
            (r"/submissions/details/([a-zA-Z0-9_-]+)",
             SubmissionDetailHandler),
            (r"/submission_file/([a-zA-Z0-9_.-]+)",
             SubmissionFileHandler),
            (r"/tasks/([a-zA-Z0-9_-]+)",
             TaskViewHandler),
            (r"/tasks/([a-zA-Z0-9_-]+)/statement",
             TaskStatementViewHandler),
            # (r"/usetoken/",
            #  UseTokenHandler),
            (r"/submit/([a-zA-Z0-9_.-]+)",
             SubmitHandler),
            (r"/user",
             UserHandler),
            (r"/instructions",
             InstructionHandler),
            (r"/notifications",
             NotificationsHandler),
            (r"/question",
             QuestionHandler),
            (r"/stl/(.*)",
             tornado.web.StaticFileHandler, {"path": WebConfig.stl_path}),
            ]

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print sys.argv[0], "shard [contest]"
        exit(1)
    ContestWebServer(int(sys.argv[1]),
                     ask_for_contest(1)).run()
