#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright (C) 2010 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright (C) 2010 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright (C) 2010 Matteo Boscariol <boscarim@hotmail.com>
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
import time
from StringIO import StringIO

import Configuration
import WebConfig
import CouchObject
import Utils
from Submission import Submission
from FileStorageLib import FileStorageLib


def token_available(user, task, timestamp):
    """
    Returns True if the given user can use a token for the given task.
    """
    tokens_timestamp = [s.token_timestamp
                        for s in user.tokens]
    task_tokens_timestamp = [s.token_timestamp
                             for s in user.tokens
                             if s.task == task]
    # These should not be needed, but let's be safe
    tokens_timestamp.sort()
    task_tokens_timestamp.sort()

    def ensure(object_with_tokens_specs, timestamps):
        o = object_with_tokens_specs
        # Ensure min_interval
        if timestamps != [] and \
                timestamp - timestamps[-1] < 60 * o.token_min_interval:
            return False
        # Ensure total
        if len(timestamps) >= o.token_total:
            return False
        # Ensure availability
        available = o.token_initial
        remaining_before_gen = o.token_gen_time
        last_t = 0
        for t in timestamps + [timestamp]:
            interval = t - last_t
            interval += 60 * (o.token_gen_time - remaining_before_gen)
            int_interval = int(interval)
            gen_tokens = int_interval / (60 * o.token_gen_time)
            if available + gen_tokens >= o.token_max:
                remaining_before_gen = o.token_gen_time
                available = o.token_max - 1
            else:
                remaining_before_gen = interval % (60 * o.token_gen_time)
                available = available + gen_tokens - 1
            last_t = t
        if available < 0:
            return False
        return True

    if not ensure(c, tokens_timestamp):
        return False
    if not ensure(task, task_tokens_timestamp):
        return False
    return True

def update_submissions():
    """
    Updates all the submissions in the contest.

    Calls the refresh method for all the Submission objects in the
    current contest.
    """
    for s in c.submissions:
        s.refresh()

def update_users():
    """
    Updates all the users in the contest.

    Calls the refresh method for all the User objects in the current
    contest.
    """
    for u in c.users:
        u.refresh()

class BaseHandler(tornado.web.RequestHandler):
    """
    Base RequestHandler for this application.

    All the RequestHandler classes in this application should be a
    child of this class.
    """
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
        for user in c.users:
            if user.username == username:
                return user
        else:
            return None

class MainHandler(BaseHandler):
    """
    Home page handler.
    """
    def get(self):
        self.render("welcome.html", contest = c, cookie = str(self.cookies))

class LoginHandler(BaseHandler):
    """
    Login handler.
    """
    def post(self):
        username = self.get_argument("username", "")
        password = self.get_argument("password", "")
        next = self.get_argument("next","/")
        if [] != [user for user in c.users \
                      if user.username == username and \
                      user.password == password]:
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
        update_submissions()

        # get the task object
        try:
            task = c.get_task(task_name)
        except:
            self.write("Task %s not found." % (task_name))
            return

        # get the list of the submissions
        subm = [s for s in c.submissions
                if s.user.username == self.current_user.username and \
                    s.task.name == task.name]
        self.render("submission.html", submissions = subm, task = task, contest = c)
class SubmissionDetailHandler(BaseHandler):
    """
    Shows additional details for the specified submission.
    """
    @tornado.web.authenticated
    def get(self, submission_id):
        update_submissions()
        
        # search the submission in the contest
        for s in c.submissions:
            if s.user.username == self.current_user.username and \
                    s.couch_id == submission_id:
                submission = s
                break
        else:
            raise tornado.web.HTTPError(404)
        self.render("submission_detail.html", submission = s, task = s.task, contest = c)    
class SubmissionFileHandler(BaseHandler):
    """
    Shows a submission file.
    """
    @tornado.web.authenticated
    def get(self, submission_id, filename):
        update_submissions()

        # search the submission in the contest
        for s in c.submissions:
            if s.user.username == self.current_user.username and \
                    s.couch_id == submission_id:
                submission = s
                break
        else:
            raise tornado.web.HTTPError(404)

        for key, value in submission.files.items():
            if key == filename:
                submission_file = StringIO()
                FSL = FileStorageLib()
                FSL.get_file(value, submission_file)

                # FIXME - Set the right headers
                self.set_header("Content-Type","text/plain")
                self.set_header("Content-Disposition",
                                "attachment; filename=\"%s\"" % (filename))
                self.write(submission_file.getvalue())
                submission_file.close()
                break
        else:
            raise tornado.web.HTTPError(404)

class TaskViewHandler(BaseHandler):
    """
    Shows the data of a task in the contest.
    """
    @tornado.web.authenticated
    def get(self, task_name):
        try:
            task = c.get_task(task_name)
        except:
            self.write("Task %s not found." % (task_name))
            return
            #raise tornado.web.HTTPError(404)
        self.render("task.html", task = task, contest = c);

class TaskStatementViewHandler(BaseHandler):
    """
    Shows the statement file of a task in the contest.
    """
    @tornado.web.authenticated
    def get(self, task_name):
        try:
            task = c.get_task(task_name)
        except:
            self.write("Task %s not found." % (task_name))
        statement_file = StringIO()
        FSL = FileStorageLib()
        FSL.get_file(task.statement, statement_file)
        self.set_header("Content-Type", "application/pdf")
        self.set_header("Content-Disposition",
                        "attachment; filename=\"%s.pdf\"" % (task.name))
        self.write(statement_file.getvalue())
        statement_file.close()

class UseTokenHandler(BaseHandler):
    """
    Handles the detailed feedbaack requests.
    """
    @tornado.web.authenticated
    def post(self):
        timestamp = time.time()
        update_submissions()
        u = self.get_current_user()
        if(u == None):
            raise tornado.web.HTTPError(403)

        if self.get_arguments("id") == []:
            raise tornado.web.HTTPError(404)
        ident = self.get_argument("id")
        for s in c.submissions:
            if s.couch_id == ident:
                # If the user already used a token on this
                if s.tokened():
                    self.write("This submission is already marked for detailed feedback.")
                # Are there any tokens available?
                elif token_available(u, s.task, timestamp):
                    s.token_timestamp = timestamp
                    u.tokens.append(s)
                    # Save to CouchDB
                    s.to_couch()
                    u.to_couch()
                    # We have to warn Evaluation Server
                    try:
                        ES.use_token(s.couch_id)
                    except:
                        # FIXME - quali informazioni devono essere fornite?
                        Utils.log("Failed to warn the Evaluation Server about a detailed feedback request.",
                                  Utils.Logger.SEVERITY_IMPORTANT)
                    self.redirect("/submissions/%s" % (s.task.name))
                    return
                else:
                    self.write("No tokens available.")
                    return
        else:
            raise tornado.web.HTTPError(404)

class SubmitHandler(BaseHandler):
    """
    Handles the received submissions.
    """
    @tornado.web.authenticated
    def post(self, task_name):
        timestamp = time.time()
        try:
          uploaded = self.request.files[task_name][0]
        except KeyError:
          self.write("No file chosen.")
          return
        files = {}
        if uploaded["content_type"] == "application/zip":
            temp_zip_file, temp_zip_filename = tempfile.mkstemp()
            temp_zip_file = os.fdopen(temp_zip_file, "w")
            temp_zip_file.write(uploaded["body"])
            temp_zip_file.close()

            zip_object = zipfile.ZipFile(temp_zip_filename, "r")
            for item in zip_object.infolist():
                files[item.filename] = zip_object.read(item)
        else:
            files[uploaded["filename"]] = uploaded["body"]
        task = c.get_task(task_name)
        if not task.valid_submission(files.keys()):
            raise tornado.web.HTTPError(404)
        for filename, content in files.items():
            temp_file, temp_filename = tempfile.mkstemp()
            temp_file = os.fdopen(temp_file, "w")
            temp_file.write(content)
            temp_file.close()
            files[filename] = FSL.put(temp_filename)
        # QUESTION - does Submission accept a dictionary with
        # filenames as keys for files?
        s = Submission(self.current_user,
                       task,
                       timestamp,
                       files)
        c.submissions.append(s)
        c.to_couch()
        try:
            ES.add_job(s.couch_id)
        except:
            # FIXME - quali informazioni devono essere fornite?
            Utils.log("Failed to queue the submission to the Evaluation Server",
                      Utils.Logger.SEVERITY_IMPORTANT)
        self.redirect("/submissions/%s" % (task_name))

handlers = [
            (r"/", MainHandler),
            (r"/login", LoginHandler),
            (r"/logout", LogoutHandler),
            (r"/submissions/([a-zA-Z0-9_-]+)", SubmissionViewHandler),
            (r"/submissions/details/([a-zA-Z0-9_-]+)", SubmissionDetailHandler),
            (r"/submission_file/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)", SubmissionFileHandler),
            (r"/tasks/([a-zA-Z0-9_-]+)", TaskViewHandler),
            (r"/task_statement/([a-zA-Z0-9_-]+)", TaskStatementViewHandler),
            (r"/usetoken/", UseTokenHandler),
            (r"/submit/([a-zA-Z0-9_.-]+)", SubmitHandler)
           ]

application = tornado.web.Application(handlers, **WebConfig.parameters)
FSL = FileStorageLib()
ES = xmlrpclib.ServerProxy("http://%s:%d" % Configuration.evaluation_server)

if __name__ == "__main__":
    Utils.set_service("contest web server")
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(8888);
    c = Utils.ask_for_contest()
    Utils.log("Contest Web Server for contest %s started..." % (c.couch_id))
    upsince = time.time()
    try:
        tornado.ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        Utils.log("Contest Web Server for contest %s stopped." % (c.couch_id))
