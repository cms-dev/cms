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

import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.escape

import couchdb
import os
import pickle
import sys
import tempfile
import xmlrpclib
import zipfile
import threading
import time

import BusinessLayer
import Configuration
import WebConfig
import CouchObject
import Utils
from Submission import Submission
from FileStorageLib import FileStorageLib

class BaseHandler(tornado.web.RequestHandler):
    """
    Base RequestHandler for this application.

    All the RequestHandler classes in this application should be a
    child of this class.
    """
    def prepare(self):
        """
        This method is executed at the beginning of each request.
        """
        # Attempt to update the contest and all its references
        # If this fails, the request terminates.
        self.set_header("Cache-Control", "no-cache, must-revalidate")
        try:
            c.refresh()
            BusinessLayer.update_submissions(c)
            BusinessLayer.update_users(c)
        except Exception as e:
            Utils.log("CouchDB exception:"+repr(e),Utils.Logger.SEVERITY_CRITICAL)
            self.write("Can't connect to CouchDB Server")
            self.finish()

    def get_current_user(self):
        """
        Gets the current user logged in from the cookies

        If a valid cookie is retrieved, returns a User object with the
        username specified in the cookie. Otherwise, returns None.
        """
        if self.get_secure_cookie("login") == None:
            return None
        try:
            username, cookie_time = pickle.loads(self.get_secure_cookie("login"))
        except:
            return None
        if cookie_time == None or cookie_time < upsince:
            return None
        return BusinessLayer.get_user_by_username(c, username)

    def render_params(self):
        r = {}
        r["timestamp"] = time.time();
        r["contest"] = c;
        r["phase"] = BusinessLayer.contest_phase(**r)
        r["cookie"] = str(self.cookies)
        return r

    def valid_phase(self,r_param):
        if r_param["phase"] != 0:
            self.redirect("/")
            return False
        return True



class MainHandler(BaseHandler):
    """
    Home page handler.
    """
    def get(self):
        r_params = self.render_params()
        self.render("welcome.html", **r_params)

class LoginHandler(BaseHandler):
    """
    Login handler.
    """
    def post(self):
        username = self.get_argument("username", "")
        password = self.get_argument("password", "")
        next = self.get_argument("next","/")
        user = BusinessLayer.get_user_by_username(c, username)
        if user != None and user.password == password:
            self.set_secure_cookie("login", pickle.dumps(
                    (self.get_argument("username"), time.time())
                    ))
            self.redirect(next)
        else:
            Utils.log("Login error: user=%s pass=%s." %
                      (username, password))
            self.redirect("/?login_error=true")

class LogoutHandler(BaseHandler):
    """
    Logout handler.
    """
    def get(self):
        self.clear_cookie("login")
        self.redirect("/")

class SubmissionViewHandler(BaseHandler):
    """
    Shows the submissions stored in the contest.
    """
    @tornado.web.authenticated
    def get(self, task_name):

        r_params = self.render_params()
        if not self.valid_phase(r_params):
            return
        # get the task object
        try:
            r_params["task"] = c.get_task(task_name)
        except:
            self.write("Task %s not found." % (task_name))
            return

        # get the list of the submissions
        r_params["submissions"] = BusinessLayer.get_submissions_by_username(c, self.current_user.username, task_name)
        self.render("submission.html", **r_params)

class SubmissionDetailHandler(BaseHandler):
    """
    Shows additional details for the specified submission.
    """
    @tornado.web.authenticated
    def get(self, submission_id):

        r_params = self.render_params()
        if not self.valid_phase(r_params):
            return
        # search the submission in the contest
        s = BusinessLayer.get_submission(c, submission_id, self.current_user.username)
        if s == None:
            raise tornado.web.HTTPError(404)
        r_params["submission"] = s;
        r_params["task"] = s.task;
        self.render("submission_detail.html", **r_params)

class SubmissionFileHandler(BaseHandler):
    """
    Shows a submission file.
    """
    @tornado.web.authenticated
    def get(self, submission_id, filename):

        r_params = self.render_params()
        if not self.valid_phase(r_params):
            return
        # search the submission in the contest
        file_content = BusinessLayer.get_file_from_submission( \
                        BusinessLayer.get_submission(c, submission_id, self.current_user.username), \
                        filename )
        if file_content == None:
            raise tornado.web.HTTPError(404)

        # FIXME - Set the right headers
        self.set_header("Content-Type","text/plain")
        self.set_header("Content-Disposition",
                        "attachment; filename=\"%s\"" % (filename))
        self.write(file_content)

class TaskViewHandler(BaseHandler):
    """
    Shows the data of a task in the contest.
    """
    @tornado.web.authenticated
    def get(self, task_name):

        r_params = self.render_params()
        if not self.valid_phase(r_params):
            return
        try:
            r_params["task"] = c.get_task(task_name)
        except:
            raise tornado.web.HTTPError(404)
        r_params["submissions"] = BusinessLayer.get_submissions_by_username(c, self.current_user.username, task_name)
        self.render("task.html", **r_params);

class TaskStatementViewHandler(BaseHandler):
    """
    Shows the statement file of a task in the contest.
    """
    @tornado.web.authenticated
    def get(self, task_name):

        r_params = self.render_params()
        if not self.valid_phase(r_params):
            return
        try:
            task = c.get_task(task_name)
        except:
            self.write("Task %s not found." % (task_name))

        statement = BusinessLayer.get_task_statement(task)

        if statement == None:
            raise tornado.web.HTTPError(404)

        self.set_header("Content-Type", "application/pdf")
        self.set_header("Content-Disposition",
                        "attachment; filename=\"%s.pdf\"" % (task.name))
        self.write(statement)


class UseTokenHandler(BaseHandler):
    """
    Handles the detailed feedbaack requests.
    """
    @tornado.web.authenticated
    def post(self):
        r_params = self.render_params()
        if not self.valid_phase(r_params):
            return
        timestamp = r_params["timestamp"]

        u = self.get_current_user()
        if(u == None):
            raise tornado.web.HTTPError(403)

        sub_id = self.get_argument("id","")
        if sub_id == "":
            raise tornado.web.HTTPError(404)


        s = BusinessLayer.get_submission(c, sub_id, u.username)
        if s == None:
            raise tornado.web.HTTPError(404)

        try:
            warned = BusinessLayer.enable_detailed_feedback(c, s, timestamp, self.current_user)
            r_params["submission"] = s
            self.render("successfulToken.html", **r_params)
        except BusinessLayer.FeedbackAlreadyRequested:
            # Either warn the user about the issue or simply
            # redirect him to the detail page.
            self.redirect("/submissions/details/"+sub_id)
            return
        except BusinessLayer.TokenUnavailableException:
            # Redirect the user to the detail page
            # warning him about the unavailable tokens.
            self.redirect("/submissions/details/"+sub_id+"?notokens=true")
            return
        except BusinessLayer.ConnectionFailure:
            self.render("errors/connectionFailure.html")
        except couchdb.ResourceConflict:
            self.render("errors/conflictError.html")
            return


class SubmitHandler(BaseHandler):
    """
    Handles the received submissions.
    """
    @tornado.web.authenticated
    def post(self, task_name):

        r_params = self.render_params()
        if not self.valid_phase(r_params):
            return
        timestamp = r_params["timestamp"]

        task = c.get_task(task_name)

        try:
          uploaded = self.request.files[task_name][0]
        except KeyError:
          self.write("No file chosen.")
          return
        files = {}

        if uploaded["content_type"] == "application/zip":
            #Extract the files from the archive
            temp_zip_file, temp_zip_filename = tempfile.mkstemp()
            with os.fdopen(temp_zip_file, "w") as temp_zip_file:
                temp_zip_file.write(uploaded["body"])

            zip_object = zipfile.ZipFile(temp_zip_filename, "r")
            for item in zip_object.infolist():
                files[item.filename] = zip_object.read(item)
        else:
            files[uploaded["filename"]] = uploaded["body"]

        try:
            s, warned = BusinessLayer.submit( c, task, self.current_user, files, timestamp)
            r_params["submission"] = s
            r_params["warned"] = warned
            self.render("successfulSub.html", **r_params)
        except couchdb.ResourceConflict:
            self.render("errors/conflictError.html", **r_params)
        except BusinessLayer.ConnectionFailure:
            self.render("errors/connectionFailure.html", **r_params)
        except BusinessLayer.StorageFailure:
            self.render("errors/storageFailure.html", **r_params)
        except BusinessLayer.InvalidSubmission:
            self.render("errors/invalidSubmission.html", **r_params)

class UserHandler(BaseHandler):
    
    @tornado.web.authenticated
    def get(self):
        r_params = self.render_params()
        self.render("user.html",**r_params)

class InstructionHandler(BaseHandler):
    def get(self):
        r_params = self.render_params()
        self.render("instructions.html",**r_params)

class NotificationsHandler(BaseHandler):
    def post(self):
        timestamp = time.time();
        last_request = self.get_argument("lastrequest",timestamp)
        messages = []
        announcements = []
        if last_request != "":
            announcements = [x for x in c.announcements if x["date"] > float(last_request) and x["date"] < timestamp]
            if self.current_user != None:
                messages = [x for x in self.current_user.messages if x["date"] > float(last_request) and x["date"] < timestamp]
        self.set_header("Content-Type", "text/xml")
        self.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>")
        self.write("<root>")
        self.write("<announcements>"+str(len(announcements))+"</announcements>")
        self.write("<messages>"+str(len(messages))+"</messages>")
        self.write("<requestdate>"+str(timestamp)+"</requestdate>");
        self.write("</root>")

handlers = [
            (r"/", MainHandler),
            (r"/login", LoginHandler),
            (r"/logout", LogoutHandler),
            (r"/submissions/([a-zA-Z0-9_-]+)", SubmissionViewHandler),
            (r"/submissions/details/([a-zA-Z0-9_-]+)", SubmissionDetailHandler),
            (r"/submission_file/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)", SubmissionFileHandler),
            (r"/tasks/([a-zA-Z0-9_-]+)", TaskViewHandler),
            (r"/tasks/([a-zA-Z0-9_-]+)/statement", TaskStatementViewHandler),
            (r"/usetoken/", UseTokenHandler),
            (r"/submit/([a-zA-Z0-9_.-]+)", SubmitHandler),
            (r"/user", UserHandler),
            (r"/instructions",InstructionHandler),
            (r"/notifications",NotificationsHandler),
           ]

application = tornado.web.Application(handlers, **WebConfig.parameters)

if __name__ == "__main__":
    Utils.set_service("contest web server")
    http_server = tornado.httpserver.HTTPServer(application, ssl_options = WebConfig.ssl_options)
    http_server.listen(WebConfig.listen_port);
    try:
        c = Utils.ask_for_contest()
    except AttributeError as e:
        Utils.log("CouchDB server unavailable: "+repr(e), Utils.Logger.SEVERITY_CRITICAL)
        exit(1)
    Utils.log("Contest Web Server for contest %s started..." % (c.couch_id))
    upsince = time.time()
    try:
        tornado.ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        Utils.log("Contest Web Server for contest %s stopped. %d threads alive" % (c.couch_id, threading.activeCount()))
        exit(0)
