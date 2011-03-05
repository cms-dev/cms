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
import datetime
import os
import pickle
import sys
import xmlrpclib
import time

import BusinessLayer
import Configuration
import WebConfig
import CouchObject
import Utils
from Submission import Submission
from FileStorageLib import FileStorageLib
from Contest import Contest


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
    """Home page handler.
    """
    def get(self):
        #Retrieve the contest list
        r_params = self.render_params()
        try:
            r_params["workers_status"] = BusinessLayer.get_workers_status()
        except Exception as e:
            Utils.log("Worker status unavailable: %s" % e,
                Utils.logger.SEVERITY_IMPORTANT)
            r_params["workers_status"] = None
        self.render("welcome.html", **r_params)

class ContestViewHandler(BaseHandler):
    def get(self,contest_id):
      try:
        c = CouchObject.from_couch(contest_id)
      except couchdb.client.ResourceNotFound:
        self.write("Cannot load contest %s." % (contest_id))
        return
      self.render("contest.html", contest = c, cookie = str(self.cookies))

class SubmissionReevaluateHandler(BaseHandler):
    """
    Re-evaluate the specified submission and go back to the details of
    the user.
    """
    def get(self, submission_id):

        r_params = self.render_params()

        # search the submission in the contest
        s = BusinessLayer.get_submission(c, submission_id)
        if s == None:
            raise tornado.web.HTTPError(404)
        BusinessLayer.reevaluate_submission(s)
        self.redirect("/user/%s" % s.user.username)


class UserReevaluateHandler(BaseHandler):
    """
    Re-evaluate the submissions of the specified user and go back to
    the details of the user.
    """
    def get(self, user_id):

        r_params = self.render_params()

        u = BusinessLayer.get_user_by_username(c, user_id)
        if u == None:
            raise tornado.web.HTTPError(404)
        submissions = BusinessLayer.get_submissions_by_username(c, user_id)
        for submission in submissions:
            BusinessLayer.reevaluate_submission(submission)
        self.redirect("/user/%s" % user_id)


#class EditContestHandler(BaseHandler):
#    def post(self,contest_id):
#        try:
#          c = CouchObject.from_couch(contest_id)
#        except couchdb.client.ResourceNotFound:
#          self.write("Cannot load contest %s." % (contest_id))
#        if self.get_arguments("name") == []:
#          self.write("No contest name specified")
#          return
#        name = self.get_argument("name")
#        description = self.get_argument("description","")
#
#        try:
#          token_initial = int(self.get_argument("token_initial","0"))
#          token_max = int(self.get_argument("token_max","0"))
#          token_total = int(self.get_argument("token_total","0"))
#        except:
#          self.write("Invalid token number field(s).")
#          return;
#        timearguments = ["_hour","_minute"]
#
#        token_min_interval = int(self.get_argument("min_interval_hour","0")) * 60 + \
#                             int(self.get_argument("min_interval_minute","0"))
#        token_gen_time = int(self.get_argument("token_gen_hour","0")) * 60 + \
#                             int(self.get_argument("token_gen_minute","0"))
#
#        datetimearguments = ["_year","_month","_day","_hour","_minute"]
#        try:
#          start = datetime.datetime(*[int(self.get_argument("start"+x)) for x in datetimearguments] )
#          end = datetime.datetime(*[int(self.get_argument("end"+x)) for x in datetimearguments] )
#        except:
#          self.write("Invalid date(s).")
#          return
#        if start > end :
#          self.write("Contest ends before it starts")
#          return
#        c.name = name
#        c.description = description
#        c.token_initial = token_initial
#        c.token_max = token_max
#        c.token_total = token_total
#        c.token_min_interval = token_min_interval
#        c.token_gen_time = token_gen_time
#        c.start = start
#        c.stop = end
#        # FIXME - Shouldn't just fail if to_couch() fails; instead, it
#        # should update the document and try again
#        try:
#          c.to_couch()
#        except:
#          self.write("Contest storage in CouchDB failed!")
#        self.redirect("/")
#        return

#class AddContestHandler(BaseHandler):
#    def get(self):
#        self.render("addcontest.html", cookie = str(self.cookies))
#    def post(self):
#        from Contest import Contest
#        if self.get_arguments("name") == []:
#          self.write("No contest name specified")
#          return
#        name = self.get_argument("name")
#        description = self.get_argument("description","")
#
#        try:
#          token_initial = int(self.get_argument("token_initial","0"))
#          token_max = int(self.get_argument("token_max","0"))
#          token_total = int(self.get_argument("token_total","0"))
#        except:
#          self.write("Invalid token number field(s).")
#          return;
#        timearguments = ["_hour","_minute"]
#
#        token_min_interval = int(self.get_argument("min_interval_hour","0")) * 60 + \
#                             int(self.get_argument("min_interval_minute","0"))
#        token_gen_time = int(self.get_argument("token_gen_hour","0")) * 60 + \
#                             int(self.get_argument("token_gen_minute","0"))
#
#        datetimearguments = ["_year","_month","_day","_hour","_minute"]
#        try:
#          time_start = time.mktime(time.strptime(" ".join([self.get_argument("start"+x,"0") for x in datetimearguments]) ,  "%Y %m %d %H %M"))
#          time_stop = time.mktime(time.strptime(" ".join([self.get_argument("end"+x,"0") for x in datetimearguments]) , "%Y %m %d %H %M" ))
#        except Exception as e:
#          self.write("Invalid date(s)." + repr(e))
#          return
#        if time_start > time_stop :
#          self.write("Contest ends before it starts")
#          return
#        try:
#          c = Contest(name,description,[],[],
#                      token_initial, token_max, token_total,
#                      token_min_interval, token_gen_time,
#                      start = time_start, stop = time_stop )
#        except:
#          self.write("Contest creation failed!")
#          return
#        if c == None:
#          self.write("Contest creation failed!")
#          return
#        # FIXME - Shouldn't just fail if to_couch() fails; instead, it
#        # should update the document and try again
#        try:
#          print c
#          c.to_couch()
#        except:
#          self.write("Contest storage in CouchDB failed!")
#        self.redirect("/")
#        return

class SubmissionDetailHandler(BaseHandler):
    """
    Shows additional details for the specified submission.
    """
    def get(self, submission_id):

        r_params = self.render_params()

        # search the submission in the contest
        s = BusinessLayer.get_submission(c, submission_id)
        if s == None:
            raise tornado.web.HTTPError(404)
        r_params["submission"] = s;
        r_params["task"] = s.task;
        self.render("submission_detail.html", **r_params)


class SubmissionFileHandler(BaseHandler):
    """
    Shows a submission file.
    """
    def get(self, submission_id, filename):

        r_params = self.render_params()
        submission = BusinessLayer.get_submission(c, submission_id)
        # search the submission in the contest
        file_content = BusinessLayer.get_file_from_submission(submission, filename)
        if file_content == None:
            raise tornado.web.HTTPError(404)

        # FIXME - Set the right headers
        self.set_header("Content-Type","text/plain")
        self.set_header("Content-Disposition",
                        "attachment; filename=\"%s-%s\"" % (submission.couch_id,filename))
        self.write(file_content)


class AddAnnouncementHandler(BaseHandler):
    def post(self):
        subject = self.get_argument("subject", "")
        text = self.get_argument("text", "")
        if subject != "":
            BusinessLayer.add_announcement(c, subject, text)
        self.redirect("/")


class RemoveAnnouncementHandler(BaseHandler):
    def post(self):
        index = self.get_argument("index", "-1")
        subject = self.get_argument("subject", "")
        text = self.get_argument("text", "")
        try:
            index = int(index)
            announcement = c.announcements[index]
        except:
            raise tornado.web.HTTPError(404)
        if announcement['subject'] == subject and \
                announcement['text'] == text:
            BusinessLayer.remove_announcement(c, index)
        self.redirect("/")


class UserViewHandler(BaseHandler):
    def get(self, user_id):
        r_params = self.render_params()
        user = BusinessLayer.get_user_by_username(c, user_id)
        submissions = BusinessLayer.get_submissions_by_username(c,user_id)
        if user == None:
            raise tornado.web.HTTPError(404)
        r_params["selected_user"] = user
        r_params["submissions"] = submissions
        self.render("user.html", **r_params)


class UserListHandler(BaseHandler):
    def get(self):
        r_params = self.render_params()
        self.render("userlist.html", **r_params)

class MessageHandler(BaseHandler):

    def post(self, user_name):
        r_params = self.render_params()

        user = BusinessLayer.get_user_by_username(c, user_name)
        if user == None:
            raise tornado.web.HTTPError(404)
        r_params["selected_user"] = user

        message_subject = self.get_argument("send_message_subject","")
        message_quick_answer = self.get_argument("send_message_quick_answer","")
        message_text = self.get_argument("send_message_text","")

        # Ignore invalid answers
        if message_quick_answer not in WebConfig.quick_answers:
            message_quick_answer = None

        # Abort if the subject is empty
        if message_subject == "" :
            self.redirect("/user/%s?notext=true" % user_name)
            return

        BusinessLayer.add_user_message(user,time.time(),\
                message_subject, message_quick_answer, message_text)
        Utils.log("Message submitted to user %s." 
                  % user_name,
                  Utils.logger.SEVERITY_NORMAL)
        self.render("successfulMessage.html", **r_params)


class QuestionReplyHandler(BaseHandler):

    def post(self, user_name):
        r_params = self.render_params()

        user = BusinessLayer.get_user_by_username(c, user_name)
        if user == None:
            raise tornado.web.HTTPError(404)
        r_params["selected_user"] = user

        message_index = self.get_argument("reply_question_index",None)
        message_quick_answer = self.get_argument("reply_question_quick_answer","")
        message_text = self.get_argument("reply_question_text","")

        if message_index == None:
            raise tornado.web.HTTPError(404)
        message_index = int(message_index)

        # Ignore invalid answers
        if message_quick_answer not in WebConfig.quick_answers:
            message_quick_answer = None

        BusinessLayer.reply_question(user,message_index, time.time(),\
                 message_quick_answer, message_text)
        Utils.log("Reply sent to user %s for question '%s'." 
                  % (user_name,user.questions[message_index]["subject"]) ,
                  Utils.logger.SEVERITY_NORMAL)
        self.render("successfulMessage.html", **r_params)

handlers = [
            (r"/",MainHandler),
#            (r"/addcontest",AddContestHandler),
#            (r"/contest/([a-zA-Z0-9_-]+)",ContestViewHandler),
#            (r"/contest/([a-zA-Z0-9_-]+)/edit",EditContestHandler),
            (r"/submissions/details/([a-zA-Z0-9_-]+)", SubmissionDetailHandler),
            (r"/reevaluate/submission/([a-zA-Z0-9_-]+)", SubmissionReevaluateHandler),
            (r"/reevaluate/user/([a-zA-Z0-9_-]+)", UserReevaluateHandler),
            (r"/add_announcement", AddAnnouncementHandler),
            (r"/remove_announcement", RemoveAnnouncementHandler),
            (r"/submission_file/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)", SubmissionFileHandler),
            (r"/user/([a-zA-Z0-9_-]+)", UserViewHandler),
            (r"/user", UserListHandler),
            (r"/message/([a-zA-Z0-9_-]+)", MessageHandler),
            (r"/question/([a-zA-Z0-9_-]+)", QuestionReplyHandler),
           ]

admin_parameters={
            "login_url": "/" ,
            "template_path": "./templates/admin",
            "cookie_secret": "DsEwRxZER06etXcqgfowEJuM6rZjwk1JvknlbngmNck=",
            "static_path": os.path.join(os.path.dirname(__file__), "static"),
            "debug": True,
           }

application = tornado.web.Application( handlers, **admin_parameters)
ES = xmlrpclib.ServerProxy("http://%s:%d" % Configuration.evaluation_server)

if __name__ == "__main__":
    Utils.set_service("administration web server")
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(8889);
    try:
        c = Utils.ask_for_contest()
    except AttributeError as e:
        Utils.log("CouchDB server unavailable: "+repr(e), Utils.Logger.SEVERITY_CRITICAL)
        exit(1)
    Utils.log("Administration Web Server for contest %s started..." % (c.couch_id))

    upsince = time.time()
    try:
        tornado.ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        Utils.log("Administration Web Server stopped.")
