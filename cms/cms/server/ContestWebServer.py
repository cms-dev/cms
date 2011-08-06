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

"""Simple web service example.

"""

from functools import wraps
import os
import pickle
import time

import tornado.web

from cms.async.AsyncLibrary import logger
from cms.async.WebAsyncLibrary import WebService
from cms.async import ServiceCoord

from cms.db.SQLAlchemyAll import Session, metadata, Contest, User, Announcement, Question

import cms.util.WebConfig as WebConfig
import cms.util.Utils as Utils
import cms.server.BusinessLayer as BusinessLayer

def contestRequired(f):
    @wraps(f)
    def wrapper(*args, **kwds):
        if args[0].contest != None:
          return f(*args, **kwds)
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
        self.contest = self.sql_session.query(Contest).filter_by(id=\
        self.application.service.contest).first()

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

        ##### Uncomment to ignore old cookies

        #if cookie_time == None or cookie_time < upsince:
        #    return None

        current_user = self.sql_session.query(User).filter_by(id=user_id).first()
        if current_user == None:
            self.clear_cookie("login")
            return None
        return current_user

    def render_params(self):
        r = {}
        r["timestamp"] = time.time()
        r["contest"] = self.contest
        if(self.contest != None):
          r["phase"] = BusinessLayer.contest_phase(**r)
        r["contest_list"] = self.sql_session.query(Contest).all()
        r["cookie"] = str(self.cookies)
        return r

    def valid_phase(self, r_param):
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

class MainHandler(BaseHandler):
    """Home page handler.
    """

    def get(self):
        r_params = self.render_params()
        self.render("welcome.html", **r_params)


class InstructionHandler(BaseHandler):

    def get(self):
        r_params = self.render_params()
        self.render("instructions.html", **r_params)

class LoginHandler(BaseHandler):
    """Login handler.
    """

    def post(self):
        username = self.get_argument("username", "")
        password = self.get_argument("password", "")
        next = self.get_argument("next", "/")
        user = self.sql_session.query(User).filter_by(contest = self.contest)\
          .filter_by(username=username).first()

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
        self.redirect(next)

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
            r_params["task"] = [ x for x in self.contest.tasks if x.name == task_name][0]
        except:
            raise tornado.web.HTTPError(404)
        r_params["submissions"] = [ x for x in self.get_current_user().tokens if x.task == r_params["task"]]

        self.render("task.html", **r_params)

class UserHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        r_params = self.render_params()
        self.render("user.html", **r_params)

class NotificationsHandler(BaseHandler):

    def post(self):
        timestamp = time.time()
        last_request = self.get_argument("lastrequest", timestamp)
        messages = []
        announcements = []
        if last_request != "":
            announcements = [x for x in self.contest.announcements
                             if x.timestamp > float(last_request) \
                                 and x.timestamp < timestamp]
            if self.current_user != None:
                messages = [x for x in self.current_user.messages
                            if x.timestamp > float(last_request) \
                                and x.timestamp < timestamp]
        self.set_header("Content-Type", "text/xml")
        self.render("notifications.xml", announcements = announcements, \
                    messages = messages, timestamp = timestamp)

class QuestionHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self):
        r_params = self.render_params()

        q = Question(time.time(), \
                self.get_argument("question_subject",""), \
                self.get_argument("question_text",""),
                user = self.get_current_user())
        self.sql_session.add(q)
        self.sql_session.commit()

        logger.warning("Question submitted by user %s."
                  % self.current_user.username)
        self.render("successfulQuestion.html", **r_params)


handlers = [
            (r"/", \
                 MainHandler),
            (r"/login", \
                 LoginHandler),
            (r"/logout", \
                 LogoutHandler),
#            (r"/submissions/([a-zA-Z0-9_-]+)", \
#                 SubmissionViewHandler),
#            (r"/submissions/details/([a-zA-Z0-9_-]+)", \
#                 SubmissionDetailHandler),
#            (r"/submission_file/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)", \
#                 SubmissionFileHandler),
            (r"/tasks/([a-zA-Z0-9_-]+)", \
                 TaskViewHandler),
#            (r"/tasks/([a-zA-Z0-9_-]+)/statement", \
#                 TaskStatementViewHandler),
#            (r"/usetoken/", \
#                 UseTokenHandler),
#            (r"/submit/([a-zA-Z0-9_.-]+)", \
#                 SubmitHandler),
            (r"/user", \
                 UserHandler),
            (r"/instructions", \
                 InstructionHandler),
            (r"/notifications", \
                 NotificationsHandler),
            (r"/question", \
                 QuestionHandler),
            (r"/stl/(.*)", \
                 tornado.web.StaticFileHandler, {"path": WebConfig.stl_path}),
           ]

if __name__ == "__main__":

    import sys
    if len(sys.argv) < 2:
        print sys.argv[0], "shard [contest]"
        exit(1)
    shard = int(sys.argv[1])
    c = Utils.ask_for_contest(1)
    ContestWebServer(shard, c).run()

